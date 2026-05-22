from __future__ import annotations

from pathlib import Path

from nexus_backend.api.schemas import CommandRequest
from nexus_backend.api.schemas import CommandResponse
from nexus_backend.memory.store import create_thread
from nexus_backend.memory.store import get_messages
from nexus_backend.memory.store import list_threads
from nexus_backend.models import discover_model_registry
from nexus_backend.models import LlamaCppRuntimeManager
from nexus_backend.tasks.agent import AgentEngine
from nexus_backend.tools.downloads import scan_downloads


def route_command(
    command_request: CommandRequest,
    model_root: Path,
    downloads_root: Path,
    database_path: Path,
    runtime_manager: LlamaCppRuntimeManager | None = None,
) -> CommandResponse:
    command = command_request.command.strip()

    if command == "/models":
        registry = discover_model_registry(model_root)
        payload = {
            "artifacts": [
                {
                    "name": artifact.name,
                    "path": str(artifact.path),
                    "launch_path": str(artifact.launch_path),
                    "runtime": artifact.runtime,
                    "kind": artifact.kind,
                    "supports_thinking": artifact.supports_thinking,
                    "recommended_context_length": artifact.recommended_context_length,
                }
                for artifact in registry.artifacts
            ],
            "defaults": {
                "router": registry.defaults.router,
                "planner": registry.defaults.planner,
                "ocr": registry.defaults.ocr,
                "vlm": registry.defaults.vlm,
            },
        }
        return CommandResponse(ok=True, command=command, payload=payload)

    if command == "/downloads":
        report = scan_downloads(downloads_root)
        return CommandResponse(ok=True, command=command, payload=report.to_dict())

    if command == "/runtime/status":
        if runtime_manager is None:
            return CommandResponse(ok=False, command=command, payload={"error": "Runtime manager is not configured."})
        return CommandResponse(ok=True, command=command, payload=runtime_manager.status().to_dict())

    if command == "/runtime/load":
        if runtime_manager is None:
            return CommandResponse(ok=False, command=command, payload={"error": "Runtime manager is not configured."})
        model_name = str(command_request.arguments.get("model_name", "")).strip()
        if not model_name:
            return CommandResponse(ok=False, command=command, payload={"error": "model_name is required."})
        try:
            context_length = command_request.arguments.get("context_length")
            temperature = float(command_request.arguments.get("temperature", 0.2))
            thinking_enabled = _parse_bool(command_request.arguments.get("thinking_enabled", True))
            state = runtime_manager.load(
                model_name=model_name,
                context_length=int(context_length) if context_length is not None else None,
                temperature=temperature,
                thinking_enabled=thinking_enabled,
            )
        except (OSError, RuntimeError, ValueError) as exc:
            return _command_error(command, exc)
        return CommandResponse(ok=True, command=command, payload=state.to_dict())

    if command == "/runtime/unload":
        if runtime_manager is None:
            return CommandResponse(ok=False, command=command, payload={"error": "Runtime manager is not configured."})
        try:
            state = runtime_manager.unload()
        except (OSError, RuntimeError, ValueError) as exc:
            return _command_error(command, exc)
        return CommandResponse(ok=True, command=command, payload=state.to_dict())

    if command == "/chat":
        if runtime_manager is None:
            return CommandResponse(ok=False, command=command, payload={"error": "Runtime manager is not configured."})
        try:
            messages = _parse_chat_messages(command_request.arguments.get("messages"))
            if messages is None:
                prompt = str(command_request.arguments.get("prompt", "")).strip()
                if not prompt:
                    return CommandResponse(ok=False, command=command, payload={"error": "prompt is required."})
                messages = [{"role": "user", "content": prompt}]
            result = runtime_manager.chat(
                model_name=str(command_request.arguments.get("model_name", "")).strip() or None,
                messages=messages,
                temperature=float(command_request.arguments.get("temperature", 0.2)),
                thinking_enabled=_parse_bool(command_request.arguments.get("thinking_enabled", True)),
                max_tokens=int(command_request.arguments.get("max_tokens", 512)),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            return _command_error(command, exc)
        return CommandResponse(ok=True, command=command, payload=result)

    if command == "/threads":
        return CommandResponse(
            ok=True,
            command=command,
            payload={"threads": [thread.to_dict() for thread in list_threads(database_path)]},
        )

    if command == "/thread/create":
        title = str(command_request.arguments.get("title", "Nexus thread")).strip() or "Nexus thread"
        thread = create_thread(database_path, title=title)
        return CommandResponse(ok=True, command=command, payload={"thread": thread.to_dict()})

    if command == "/thread/messages":
        thread_id = str(command_request.arguments.get("thread_id", "")).strip()
        if not thread_id:
            return CommandResponse(ok=False, command=command, payload={"error": "thread_id is required."})
        return CommandResponse(
            ok=True,
            command=command,
            payload={"messages": [message.to_dict() for message in get_messages(database_path, thread_id, limit=100)]},
        )

    if command == "/agent":
        if runtime_manager is None:
            return CommandResponse(ok=False, command=command, payload={"error": "Runtime manager is not configured."})
        try:
            user_message = str(command_request.arguments.get("message", "")).strip()
            if not user_message:
                return CommandResponse(ok=False, command=command, payload={"error": "message is required."})
            agent = AgentEngine(
                database_path=database_path,
                model_root=model_root,
                downloads_root=downloads_root,
                runtime_manager=runtime_manager,
            )
            turn = agent.run_turn(
                user_message=user_message,
                thread_id=str(command_request.arguments.get("thread_id", "")).strip() or None,
                model_name=str(command_request.arguments.get("model_name", "")).strip() or None,
                temperature=float(command_request.arguments.get("temperature", 0.2)),
                thinking_enabled=_parse_bool(command_request.arguments.get("thinking_enabled", True)),
                max_tokens=int(command_request.arguments.get("max_tokens", 900)),
            )
        except (OSError, RuntimeError, ValueError) as exc:
            return _command_error(command, exc)
        return CommandResponse(ok=True, command=command, payload=turn.to_dict())

    return CommandResponse(
        ok=False,
        command=command,
        payload={
            "error": f"Unknown command: {command}",
            "supported_commands": [
                "/models",
                "/downloads",
                "/runtime/status",
                "/runtime/load",
                "/runtime/unload",
                "/chat",
                "/agent",
                "/threads",
                "/thread/create",
                "/thread/messages",
            ],
        },
    )


def _parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _parse_chat_messages(value: object) -> list[dict[str, str]] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        raise ValueError("messages must be a list of chat messages.")

    messages: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"messages[{index}] must be an object.")

        role_value = item.get("role")
        content_value = item.get("content")
        if not isinstance(role_value, str):
            raise ValueError(f"messages[{index}].role must be a string.")
        if not isinstance(content_value, str):
            raise ValueError(f"messages[{index}].content must be a string.")

        role = role_value.strip()
        content = content_value.strip()
        if role not in {"system", "user", "assistant"}:
            raise ValueError(f"messages[{index}].role must be system, user, or assistant.")
        if not content:
            raise ValueError(f"messages[{index}].content is required.")

        messages.append({"role": role, "content": content})

    if not messages:
        raise ValueError("messages must include at least one message.")
    return messages


def _command_error(command: str, error: Exception) -> CommandResponse:
    message = str(error).strip() or error.__class__.__name__
    return CommandResponse(ok=False, command=command, payload={"error": message})
