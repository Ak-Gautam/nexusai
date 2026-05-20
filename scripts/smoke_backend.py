from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib import request


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    port = _free_port()
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")

    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "nexus_backend.main",
            "serve",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:
        base_url = f"http://127.0.0.1:{port}"
        _wait_for_health(base_url, process)
        health = _get_json(f"{base_url}/health")
        models = _post_command(base_url, "/models")
        runtime = _post_command(base_url, "/runtime/status")

        print("Backend smoke check passed")
        print(f"health.ok={health.get('ok')}")
        print(f"models.count={len(models.get('payload', {}).get('artifacts', []))}")
        print(f"runtime.loaded={runtime.get('payload', {}).get('loaded')}")
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_for_health(base_url: str, process: subprocess.Popen[str]) -> None:
    deadline = time.time() + 15
    last_error: Exception | None = None
    while time.time() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout is not None else ""
            raise RuntimeError(f"Backend exited early with code {process.returncode}.\n{output}")
        try:
            _get_json(f"{base_url}/health")
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            time.sleep(0.2)
    raise RuntimeError(f"Timed out waiting for backend health: {last_error}")


def _get_json(url: str) -> dict[str, object]:
    with request.urlopen(url, timeout=5) as response:
        payload = response.read().decode("utf-8")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Expected object response from {url}")
    return parsed


def _post_command(base_url: str, command: str) -> dict[str, object]:
    body = json.dumps({"command": command, "arguments": {}}).encode("utf-8")
    req = request.Request(
        f"{base_url}/commands",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=5) as response:
        payload = response.read().decode("utf-8")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise RuntimeError(f"Expected object command response for {command}")
    if not parsed.get("ok"):
        raise RuntimeError(f"Command failed for {command}: {payload}")
    return parsed


if __name__ == "__main__":
    main()
