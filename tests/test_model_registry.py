from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nexus_backend.models.registry import discover_model_registry


class ModelRegistryTests(unittest.TestCase):
    def test_discovers_text_and_mlx_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            qwen_dir = root / "Qwen3.5-2B-UD-Q4_K_XL"
            qwen_dir.mkdir()
            (qwen_dir / "model.gguf").write_text("", encoding="utf-8")
            (root / "glm-ocr-model.safetensors").write_text("", encoding="utf-8")

            registry = discover_model_registry(root)
            artifacts = {artifact.name: artifact for artifact in registry.artifacts}

            self.assertEqual(len(registry.artifacts), 2)
            self.assertEqual(artifacts["Qwen3.5-2B-UD-Q4_K_XL"].runtime, "llama.cpp")
            self.assertTrue(artifacts["Qwen3.5-2B-UD-Q4_K_XL"].supports_thinking)
            self.assertEqual(artifacts["glm-ocr-model"].kind, "ocr")
            self.assertEqual(registry.defaults.router, "Qwen3.5-2B-UD-Q4_K_XL")
            self.assertEqual(registry.defaults.ocr, "glm-ocr-model")

    def test_missing_model_root_returns_empty_registry(self) -> None:
        registry = discover_model_registry(Path("/tmp/nexus-model-root-that-does-not-exist"))

        self.assertEqual(registry.artifacts, ())
        self.assertIsNone(registry.defaults.router)


if __name__ == "__main__":
    unittest.main()
