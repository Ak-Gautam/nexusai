from __future__ import annotations

import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import Any

from nexus_backend.api.schemas import CommandRequest
from nexus_backend.api.schemas import HealthResponse
from nexus_backend.memory.store import initialize_database
from nexus_backend.memory.store import log_event
from nexus_backend.memory.store import log_task_run
from nexus_backend.models import discover_model_registry
from nexus_backend.models import LlamaCppRuntimeManager
from nexus_backend.tasks.router import route_command


class NexusApiServer(ThreadingHTTPServer):
    def __init__(
        self,
        server_address: tuple[str, int],
        model_root: Path,
        database_path: Path,
        downloads_root: Path,
        data_root: Path,
        llama_server_path: Path | None,
    ):
        super().__init__(server_address, NexusRequestHandler)
        self.model_root = model_root
        self.database_path = database_path
        self.downloads_root = downloads_root
        self.database_status = initialize_database(database_path)
        self.runtime_manager = LlamaCppRuntimeManager(
            model_root=model_root,
            data_root=data_root,
            llama_server_path=llama_server_path,
        )


class NexusRequestHandler(BaseHTTPRequestHandler):
    server: NexusApiServer

    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/health":
            registry = discover_model_registry(self.server.model_root)
            payload = HealthResponse(
                ok=True,
                service="nexus-backend",
                database_ready=self.server.database_status.ready,
                model_count=len(registry.artifacts),
                runtime_loaded=self.server.runtime_manager.status().loaded,
            ).to_dict()
            self._write_json(HTTPStatus.OK, payload)
            return

        if self.path == "/models":
            response = route_command(
                CommandRequest(command="/models"),
                model_root=self.server.model_root,
                downloads_root=self.server.downloads_root,
                database_path=self.server.database_path,
                runtime_manager=self.server.runtime_manager,
            )
            self._write_json(HTTPStatus.OK, response.to_dict())
            return

        if self.path == "/runtime":
            payload = self.server.runtime_manager.status().to_dict()
            self._write_json(HTTPStatus.OK, payload)
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found"})

    def do_POST(self) -> None:  # noqa: N802
        if self.path != "/commands":
            self._write_json(HTTPStatus.NOT_FOUND, {"ok": False, "error": "Not found"})
            return

        body = self._read_json()
        command = str(body.get("command", "")).strip()
        arguments = body.get("arguments", {})
        request = CommandRequest(command=command, arguments=arguments if isinstance(arguments, dict) else {})
        response = route_command(
            request,
            model_root=self.server.model_root,
            downloads_root=self.server.downloads_root,
            database_path=self.server.database_path,
            runtime_manager=self.server.runtime_manager,
        )
        log_task_run(
            self.server.database_path,
            command=command or "<empty>",
            status="ok" if response.ok else "error",
            summary=json.dumps(response.payload, ensure_ascii=True)[:500],
        )
        self._write_json(HTTPStatus.OK if response.ok else HTTPStatus.BAD_REQUEST, response.to_dict())

    def log_message(self, format: str, *args: Any) -> None:
        log_event(self.server.database_path, "http", format % args)

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(content_length) if content_length > 0 else b"{}"
        try:
            parsed = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=True, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)
