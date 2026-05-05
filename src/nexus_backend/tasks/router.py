from __future__ import annotations

from pathlib import Path

from nexus_backend.api.schemas import CommandRequest
from nexus_backend.api.schemas import CommandResponse
from nexus_backend.models import discover_model_registry
from nexus_backend.tools.downloads import scan_downloads


def route_command(command_request: CommandRequest, model_root: Path, downloads_root: Path) -> CommandResponse:
    command = command_request.command.strip()

    if command == "/models":
        registry = discover_model_registry(model_root)
        payload = {
            "artifacts": [
                {
                    "name": artifact.name,
                    "path": str(artifact.path),
                    "runtime": artifact.runtime,
                    "kind": artifact.kind,
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

    return CommandResponse(
        ok=False,
        command=command,
        payload={"error": f"Unknown command: {command}", "supported_commands": ["/models", "/downloads"]},
    )
