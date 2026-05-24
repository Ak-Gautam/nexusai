from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nexus_backend.api.schemas import CommandRequest
from nexus_backend.app_logging import configure_backend_logging
from nexus_backend.memory.store import initialize_database
from nexus_backend.models.runtime import RuntimeState
from nexus_backend.tasks.router import route_command


class FakeRuntimeManager:
    def status(self) -> RuntimeState:
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

    def load(self, model_name: str, context_length: int | None, temperature: float, thinking_enabled: bool) -> RuntimeState:
        return RuntimeState(
            loaded=True,
            model_name=model_name,
            model_path="/tmp/model.gguf",
            server_url="http://127.0.0.1:12345",
            process_id=123,
            context_length=context_length,
            temperature=temperature,
            thinking_enabled=thinking_enabled,
            supports_thinking=False,
        )

    def unload(self) -> RuntimeState:
        return self.status()


class RouterTests(unittest.TestCase):
    def test_runtime_status_uses_runtime_manager(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            response = route_command(
                CommandRequest(command="/runtime/status"),
                model_root=Path(temp_dir) / "models",
                downloads_root=Path(temp_dir) / "downloads",
                database_path=Path(temp_dir) / "nexus.sqlite3",
                runtime_manager=FakeRuntimeManager(),  # type: ignore[arg-type]
            )

            self.assertTrue(response.ok)
            self.assertFalse(response.payload["loaded"])

    def test_logs_command_returns_backend_log_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir)
            database_path = data_root / "nexus.sqlite3"
            initialize_database(database_path)
            configure_backend_logging(data_root)
            (data_root / "logs" / "backend.log").write_text("line-one\nline-two\n", encoding="utf-8")

            response = route_command(
                CommandRequest(command="/logs", arguments={"source": "backend", "limit": 1}),
                model_root=data_root / "models",
                downloads_root=data_root / "downloads",
                database_path=database_path,
                runtime_manager=FakeRuntimeManager(),  # type: ignore[arg-type]
            )

            self.assertTrue(response.ok)
            self.assertEqual(response.payload["logs"]["backend.log"], ["line-two"])

    def test_unknown_command_lists_supported_commands(self) -> None:
        response = route_command(
            CommandRequest(command="/unknown"),
            model_root=Path("/tmp/models"),
            downloads_root=Path("/tmp/downloads"),
            database_path=Path("/tmp/nexus.sqlite3"),
            runtime_manager=None,
        )

        self.assertFalse(response.ok)
        self.assertIn("/logs", response.payload["supported_commands"])


if __name__ == "__main__":
    unittest.main()
