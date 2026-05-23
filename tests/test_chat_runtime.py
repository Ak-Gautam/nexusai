from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from nexus_backend.api.schemas import CommandRequest
from nexus_backend.models.runtime import LlamaCppRuntimeManager
from nexus_backend.models.runtime import RuntimeState
from nexus_backend.tasks.router import route_command


class FakeRuntimeManager:
    def __init__(self) -> None:
        self.thinking_enabled: bool | None = None

    def chat(
        self,
        model_name: str | None,
        messages: list[dict[str, str]],
        temperature: float | None,
        thinking_enabled: bool | None,
        max_tokens: int = 512,
    ) -> dict[str, object]:
        self.thinking_enabled = thinking_enabled
        return {
            "runtime": {},
            "response": {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "Hello",
                        }
                    }
                ]
            },
        }


class LoadedRuntimeManager(LlamaCppRuntimeManager):
    def status(self) -> RuntimeState:
        return RuntimeState(
            loaded=True,
            model_name="thinking-model",
            model_path="/tmp/thinking-model.gguf",
            server_url="http://127.0.0.1:12345",
            process_id=123,
            context_length=8192,
            temperature=0.2,
            thinking_enabled=True,
            supports_thinking=True,
        )


class ChatRuntimeTests(unittest.TestCase):
    def test_chat_command_defaults_thinking_off(self) -> None:
        runtime_manager = FakeRuntimeManager()

        response = route_command(
            CommandRequest(command="/chat", arguments={"prompt": "Hi"}),
            model_root=Path("/tmp/models"),
            downloads_root=Path("/tmp/downloads"),
            database_path=Path("/tmp/nexus.sqlite3"),
            runtime_manager=runtime_manager,  # type: ignore[arg-type]
        )

        self.assertTrue(response.ok)
        self.assertIs(runtime_manager.thinking_enabled, False)

    def test_thinking_request_sets_llama_chat_template_kwargs(self) -> None:
        captured_payload: dict[str, Any] | None = None

        def fake_post_json(url: str, payload: dict[str, object]) -> dict[str, object]:
            nonlocal captured_payload
            captured_payload = payload
            return {"choices": [{"message": {"role": "assistant", "content": "Hello"}}]}

        import nexus_backend.models.runtime as runtime_module

        original_post_json = runtime_module._post_json
        runtime_module._post_json = fake_post_json
        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                manager = LoadedRuntimeManager(
                    model_root=Path(temp_dir) / "models",
                    data_root=Path(temp_dir) / "data",
                    llama_server_path=Path("/bin/false"),
                )
                manager.chat(
                    model_name=None,
                    messages=[{"role": "user", "content": "Hi"}],
                    temperature=None,
                    thinking_enabled=False,
                    max_tokens=80,
                )
        finally:
            runtime_module._post_json = original_post_json

        self.assertIsNotNone(captured_payload)
        assert captured_payload is not None
        self.assertEqual(captured_payload["chat_template_kwargs"], {"enable_thinking": False})


if __name__ == "__main__":
    unittest.main()
