from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nexus_backend.memory.store import append_message
from nexus_backend.memory.store import create_thread
from nexus_backend.memory.store import get_messages
from nexus_backend.memory.store import initialize_database
from nexus_backend.memory.store import list_threads
from nexus_backend.memory.store import log_event
from nexus_backend.memory.store import log_task_run


class MemoryStoreTests(unittest.TestCase):
    def test_threads_messages_and_logs_persist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "nexus.sqlite3"
            status = initialize_database(database_path)

            thread = create_thread(database_path, "Test thread")
            append_message(database_path, thread.id, "user", "Hi", {"source": "unit"})
            append_message(database_path, thread.id, "assistant", "Hello")
            log_event(database_path, "unit", "event")
            log_task_run(database_path, "/unit", "ok", "summary")

            messages = get_messages(database_path, thread.id)

            self.assertTrue(status.ready)
            self.assertEqual(list_threads(database_path)[0].title, "Test thread")
            self.assertEqual([message.role for message in messages], ["user", "assistant"])
            self.assertEqual(messages[0].metadata, {"source": "unit"})


if __name__ == "__main__":
    unittest.main()
