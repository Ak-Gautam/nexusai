from __future__ import annotations

import json
import os
import signal
import shutil
import subprocess
import threading
import time
from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from urllib import error
from urllib import request

from nexus_backend.models.registry import ModelArtifact
from nexus_backend.models.registry import discover_model_registry


@dataclass(frozen=True)
class RuntimeSettings:
    context_length: int
    temperature: float
    thinking_enabled: bool


@dataclass(frozen=True)
class RuntimeState:
    loaded: bool
    model_name: str | None
    model_path: str | None
    server_url: str | None
    process_id: int | None
    context_length: int | None
    temperature: float | None
    thinking_enabled: bool | None
    supports_thinking: bool | None

    def to_dict(self) -> dict[str, object | None]:
        return asdict(self)


class LlamaCppRuntimeManager:
    def __init__(self, model_root: Path, data_root: Path, llama_server_path: Path | None = None) -> None:
        self.model_root = model_root
        self.data_root = data_root
        self.logs_dir = data_root / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.state_path = data_root / "runtime_state.json"
        self.llama_server_path = llama_server_path or _resolve_llama_server_path()
        self._lock = threading.RLock()
        self._process: subprocess.Popen[bytes] | None = None
        self._active_artifact: ModelArtifact | None = None
        self._active_settings: RuntimeSettings | None = None
        self._active_port: int | None = None
        self._stdout_handle = None
        self._stderr_handle = None

    def status(self) -> RuntimeState:
        with self._lock:
            persisted = self._read_persisted_state()
            if persisted is not None and _pid_is_alive(int(persisted["process_id"])) and _runtime_is_healthy(str(persisted["server_url"])):
                return RuntimeState(
                    loaded=True,
                    model_name=str(persisted["model_name"]),
                    model_path=str(persisted["model_path"]),
                    server_url=str(persisted["server_url"]),
                    process_id=int(persisted["process_id"]),
                    context_length=int(persisted["context_length"]),
                    temperature=float(persisted["temperature"]),
                    thinking_enabled=bool(persisted["thinking_enabled"]),
                    supports_thinking=bool(persisted["supports_thinking"]),
                )

            loaded = self._process is not None and self._process.poll() is None
            if not loaded:
                return RuntimeState(
                    loaded=False,
                    model_name=None,
                    model_path=None,
                    server_url=None,
                    process_id=None,
                    context_length=None,
                    temperature=None,
                    thinking_enabled=None,
                    supports_thinking=None,
                )
            assert self._active_artifact is not None
            assert self._active_settings is not None
            assert self._active_port is not None
            return RuntimeState(
                loaded=True,
                model_name=self._active_artifact.name,
                model_path=str(self._active_artifact.launch_path),
                server_url=f"http://127.0.0.1:{self._active_port}",
                process_id=self._process.pid,
                context_length=self._active_settings.context_length,
                temperature=self._active_settings.temperature,
                thinking_enabled=self._active_settings.thinking_enabled,
                supports_thinking=self._active_artifact.supports_thinking,
            )

    def load(self, model_name: str, context_length: int | None, temperature: float, thinking_enabled: bool) -> RuntimeState:
        with self._lock:
            artifact = self._resolve_text_model(model_name)
            effective_context = context_length or artifact.recommended_context_length
            settings = RuntimeSettings(
                context_length=effective_context,
                temperature=temperature,
                thinking_enabled=thinking_enabled,
            )

            current = self.status()
            if current.loaded and current.model_name == artifact.name:
                if current.context_length == settings.context_length and current.temperature == settings.temperature and current.thinking_enabled == settings.thinking_enabled:
                    return current
                self._terminate_locked()

            elif current.loaded:
                self._terminate_locked()

            port = _find_available_port()
            stdout_path = self.logs_dir / "llama-server.stdout.log"
            stderr_path = self.logs_dir / "llama-server.stderr.log"
            self._stdout_handle = stdout_path.open("ab")
            self._stderr_handle = stderr_path.open("ab")
            env = os.environ.copy()
            env.setdefault("LLAMA_ARG_HOST", "127.0.0.1")

            command = [
                str(self.llama_server_path),
                "--model",
                str(artifact.launch_path),
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--ctx-size",
                str(settings.context_length),
                "--threads",
                "-1",
                "--flash-attn",
                "on",
                "--no-context-shift",
                "--jinja",
            ]

            self._process = subprocess.Popen(
                command,
                stdout=self._stdout_handle,
                stderr=self._stderr_handle,
                env=env,
                start_new_session=True,
            )
            self._active_artifact = artifact
            self._active_settings = settings
            self._active_port = port
            self._wait_until_healthy_locked()
            state = self.status()
            self._write_persisted_state(state)
            return state

    def unload(self) -> RuntimeState:
        with self._lock:
            self._terminate_locked()
            return self.status()

    def chat(self, model_name: str | None, messages: list[dict[str, str]], temperature: float | None, thinking_enabled: bool | None, max_tokens: int = 512) -> dict[str, object]:
        with self._lock:
            loaded = self.status()
            target_model_name = model_name or loaded.model_name
            if target_model_name is None:
                raise RuntimeError("No model is loaded. Load a model before chat.")

            if not loaded.loaded or loaded.model_name != target_model_name:
                artifact = self._resolve_text_model(target_model_name)
                self.load(
                    model_name=artifact.name,
                    context_length=artifact.recommended_context_length,
                    temperature=temperature if temperature is not None else 0.2,
                    thinking_enabled=thinking_enabled if thinking_enabled is not None else artifact.supports_thinking,
                )
                loaded = self.status()

            assert loaded.server_url is not None
            effective_temperature = temperature if temperature is not None else loaded.temperature or 0.2
            effective_thinking = thinking_enabled if thinking_enabled is not None else bool(loaded.thinking_enabled)
            payload = {
                "model": loaded.model_name,
                "messages": _prepare_messages(messages, effective_thinking, bool(loaded.supports_thinking)),
                "temperature": effective_temperature,
                "max_tokens": max_tokens,
                "stream": False,
            }
            if loaded.supports_thinking:
                payload["chat_template_kwargs"] = {"enable_thinking": effective_thinking}
            raw_response = _post_json(f"{loaded.server_url}/v1/chat/completions", payload)
            return {
                "runtime": loaded.to_dict(),
                "request": payload,
                "response": raw_response,
            }

    def _resolve_text_model(self, model_name: str) -> ModelArtifact:
        registry = discover_model_registry(self.model_root)
        for artifact in registry.artifacts:
            if artifact.name == model_name and artifact.runtime == "llama.cpp" and artifact.kind == "text":
                return artifact
        raise RuntimeError(f"Unknown text model: {model_name}")

    def _wait_until_healthy_locked(self) -> None:
        assert self._process is not None
        assert self._active_port is not None
        deadline = time.time() + 120
        url = f"http://127.0.0.1:{self._active_port}/health"
        while time.time() < deadline:
            if self._process.poll() is not None:
                raise RuntimeError("llama-server exited before it became healthy.")
            try:
                _get_json(url)
                return
            except RuntimeError:
                time.sleep(0.5)
        raise RuntimeError("Timed out while waiting for llama-server to become healthy.")

    def _terminate_locked(self) -> None:
        persisted = self._read_persisted_state()
        if persisted is not None:
            pid = int(persisted["process_id"])
            if _pid_is_alive(pid):
                try:
                    os.kill(pid, signal.SIGTERM)
                    for _ in range(20):
                        if not _pid_is_alive(pid):
                            break
                        time.sleep(0.2)
                    if _pid_is_alive(pid):
                        os.kill(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass

        if self._process is not None and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=5)
        self._process = None
        self._active_artifact = None
        self._active_settings = None
        self._active_port = None
        if self._stdout_handle is not None:
            self._stdout_handle.close()
            self._stdout_handle = None
        if self._stderr_handle is not None:
            self._stderr_handle.close()
            self._stderr_handle = None
        if self.state_path.exists():
            self.state_path.unlink()

    def _write_persisted_state(self, state: RuntimeState) -> None:
        self.state_path.write_text(json.dumps(state.to_dict(), ensure_ascii=True, indent=2), encoding="utf-8")

    def _read_persisted_state(self) -> dict[str, object] | None:
        if not self.state_path.exists():
            return None
        try:
            payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None


def _resolve_llama_server_path() -> Path:
    found = shutil.which("llama-server")
    if found is None:
        raise RuntimeError("llama-server was not found on PATH.")
    return Path(found)


def _find_available_port() -> int:
    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _prepare_messages(messages: list[dict[str, str]], thinking_enabled: bool, supports_thinking: bool) -> list[dict[str, str]]:
    prelude = None
    if supports_thinking and thinking_enabled:
        prelude = "Reason carefully before answering. You may use hidden reasoning if the model supports it, but return a clean final answer."
    elif supports_thinking and not thinking_enabled:
        prelude = "Do not expose chain-of-thought or thinking tags. Return only the final answer succinctly."

    if prelude is None:
        return messages

    if messages and messages[0].get("role") == "system":
        return [
            {
                "role": "system",
                "content": f"{prelude}\n\n{messages[0].get('content', '')}",
            },
            *messages[1:],
        ]

    return [{"role": "system", "content": prelude}, *messages]


def _get_json(url: str) -> dict[str, object]:
    try:
        with request.urlopen(url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except (error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Request failed for {url}") from exc


def _post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
    body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
    req = request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with request.urlopen(req, timeout=180) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"llama-server request failed: {details}") from exc
    except (error.URLError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Request failed for {url}") from exc


def _pid_is_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _runtime_is_healthy(server_url: str) -> bool:
    try:
        _get_json(f"{server_url}/health")
        return True
    except RuntimeError:
        return False
