from __future__ import annotations

import os
import tempfile
import unittest
from datetime import UTC
from datetime import datetime
from pathlib import Path

from nexus_backend.tools.downloads import scan_downloads


class DownloadsToolTests(unittest.TestCase):
    def test_scan_downloads_detects_duplicates_and_recommendations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            first = root / "copy-a.zip"
            second = root / "copy-b.zip"
            first.write_bytes(b"same payload")
            second.write_bytes(b"same payload")

            old_time = datetime(2020, 1, 1, tzinfo=UTC).timestamp()
            os.utime(first, (old_time, old_time))
            os.utime(second, (old_time, old_time))

            report = scan_downloads(root)

            self.assertEqual(report.scanned_files, 2)
            self.assertEqual(len(report.duplicate_groups), 1)
            self.assertEqual({item.name for item in report.duplicate_groups[0]}, {"copy-a.zip", "copy-b.zip"})
            self.assertTrue(any(item.action == "review-delete" for item in report.recommendations))

    def test_missing_downloads_root_returns_empty_report(self) -> None:
        report = scan_downloads(Path("/tmp/nexus-downloads-path-that-does-not-exist"))

        self.assertEqual(report.scanned_files, 0)
        self.assertEqual(report.total_size_bytes, 0)
        self.assertEqual(report.recommendations, [])


if __name__ == "__main__":
    unittest.main()
