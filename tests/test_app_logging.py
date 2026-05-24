from __future__ import annotations

import logging
import tempfile
import unittest
from pathlib import Path

from nexus_backend.app_logging import configure_backend_logging
from nexus_backend.app_logging import get_logger
from nexus_backend.app_logging import list_log_files
from nexus_backend.app_logging import read_recent_logs


class AppLoggingTests(unittest.TestCase):
    def test_backend_log_file_is_written_and_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            data_root = Path(temp_dir)
            log_path = configure_backend_logging(data_root)

            logger = get_logger("test")
            logger.info("unit_test_log_message")
            for handler in logging.getLogger("nexus_backend").handlers:
                handler.flush()

            self.assertEqual(log_path, data_root / "logs" / "backend.log")
            self.assertIn("backend.log", {item["name"] for item in list_log_files(data_root)})

            logs = read_recent_logs(data_root, source="backend", limit=5)
            self.assertIn("backend.log", logs)
            self.assertTrue(any("unit_test_log_message" in line for line in logs["backend.log"]))

    def test_log_source_filters_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            logs_dir.mkdir()
            (logs_dir / "backend.log").write_text("backend\n", encoding="utf-8")
            (logs_dir / "llama-server.stderr.log").write_text("runtime\n", encoding="utf-8")

            logs = read_recent_logs(Path(temp_dir), source="runtime", limit=10)

            self.assertEqual(set(logs), {"llama-server.stderr.log"})
            self.assertEqual(logs["llama-server.stderr.log"], ["runtime"])


if __name__ == "__main__":
    unittest.main()
