from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import asdict
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from pathlib import Path


INSTALLER_SUFFIXES = {".dmg", ".pkg", ".app", ".msi"}
ARCHIVE_SUFFIXES = {".zip", ".tar", ".gz", ".bz2", ".xz", ".7z", ".rar"}
DOCUMENT_SUFFIXES = {".pdf", ".doc", ".docx", ".txt", ".md", ".rtf"}
MEDIA_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov", ".m4a"}
CODE_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".json", ".yaml", ".yml", ".toml"}
TEMPORARY_SUFFIXES = {".crdownload", ".download", ".part", ".tmp"}
LARGE_FILE_BYTES = 100 * 1024 * 1024
STALE_DAYS = 30
HASH_CHUNK_SIZE = 1024 * 1024


@dataclass(frozen=True)
class FileRecord:
    path: str
    name: str
    size_bytes: int
    modified_at: str
    category: str
    mime_type: str | None
    is_duplicate_candidate: bool


@dataclass(frozen=True)
class Recommendation:
    action: str
    target: str
    reason: str


@dataclass(frozen=True)
class DownloadsReport:
    root: str
    scanned_files: int
    total_size_bytes: int
    large_files: list[FileRecord]
    stale_files: list[FileRecord]
    duplicate_groups: list[list[FileRecord]]
    recommendations: list[Recommendation]

    def to_dict(self) -> dict[str, object]:
        return {
            "root": self.root,
            "scanned_files": self.scanned_files,
            "total_size_bytes": self.total_size_bytes,
            "large_files": [asdict(item) for item in self.large_files],
            "stale_files": [asdict(item) for item in self.stale_files],
            "duplicate_groups": [[asdict(item) for item in group] for group in self.duplicate_groups],
            "recommendations": [asdict(item) for item in self.recommendations],
        }


def scan_downloads(root: Path) -> DownloadsReport:
    if not root.exists():
        return DownloadsReport(
            root=str(root),
            scanned_files=0,
            total_size_bytes=0,
            large_files=[],
            stale_files=[],
            duplicate_groups=[],
            recommendations=[],
        )

    records: list[FileRecord] = []
    total_size = 0
    paths_by_size: dict[int, list[Path]] = {}
    now = datetime.now(UTC)

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        stat = path.stat()
        total_size += stat.st_size
        category = _categorize(path)
        mime_type, _ = mimetypes.guess_type(path.name)
        modified_at = datetime.fromtimestamp(stat.st_mtime, UTC)
        record = FileRecord(
            path=str(path),
            name=path.name,
            size_bytes=stat.st_size,
            modified_at=modified_at.isoformat(),
            category=category,
            mime_type=mime_type,
            is_duplicate_candidate=False,
        )
        records.append(record)
        paths_by_size.setdefault(stat.st_size, []).append(path)

    duplicate_groups = _find_duplicates(paths_by_size)
    duplicate_paths = {item.path for group in duplicate_groups for item in group}
    refreshed_records = [
        FileRecord(**(asdict(record) | {"is_duplicate_candidate": record.path in duplicate_paths}))
        for record in records
    ]
    large_files = sorted(
        (record for record in refreshed_records if record.size_bytes >= LARGE_FILE_BYTES),
        key=lambda item: item.size_bytes,
        reverse=True,
    )[:10]
    stale_files = sorted(
        (
            record
            for record in refreshed_records
            if (now - datetime.fromisoformat(record.modified_at)).days >= STALE_DAYS
        ),
        key=lambda item: item.modified_at,
    )[:20]
    recommendations = _build_recommendations(large_files, stale_files, duplicate_groups)

    return DownloadsReport(
        root=str(root),
        scanned_files=len(refreshed_records),
        total_size_bytes=total_size,
        large_files=large_files,
        stale_files=stale_files,
        duplicate_groups=duplicate_groups,
        recommendations=recommendations,
    )


def _find_duplicates(paths_by_size: dict[int, list[Path]]) -> list[list[FileRecord]]:
    groups: list[list[FileRecord]] = []
    for size, paths in paths_by_size.items():
        if size == 0 or len(paths) < 2:
            continue
        grouped_by_hash: dict[str, list[Path]] = {}
        for path in paths:
            grouped_by_hash.setdefault(_hash_file(path), []).append(path)
        for hash_paths in grouped_by_hash.values():
            if len(hash_paths) < 2:
                continue
            group = []
            for path in sorted(hash_paths):
                stat = path.stat()
                modified_at = datetime.fromtimestamp(stat.st_mtime, UTC).isoformat()
                mime_type, _ = mimetypes.guess_type(path.name)
                group.append(
                    FileRecord(
                        path=str(path),
                        name=path.name,
                        size_bytes=stat.st_size,
                        modified_at=modified_at,
                        category=_categorize(path),
                        mime_type=mime_type,
                        is_duplicate_candidate=True,
                    )
                )
            groups.append(group)
    return groups


def _build_recommendations(
    large_files: list[FileRecord],
    stale_files: list[FileRecord],
    duplicate_groups: list[list[FileRecord]],
) -> list[Recommendation]:
    recommendations: list[Recommendation] = []
    for group in duplicate_groups[:10]:
        keep = max(group, key=lambda item: item.modified_at)
        for record in group:
            if record.path == keep.path:
                continue
            recommendations.append(
                Recommendation(
                    action="review-delete",
                    target=record.path,
                    reason=f"Exact duplicate of {keep.name}; keep the newest copy and review older copies.",
                )
            )

    for record in large_files[:5]:
        recommendations.append(
            Recommendation(
                action="review-move",
                target=record.path,
                reason="Large file in Downloads; consider moving it to a project, archive, or media folder.",
            )
        )

    for record in stale_files[:5]:
        if record.category in {"installer", "archive", "temporary"}:
            recommendations.append(
                Recommendation(
                    action="review-delete",
                    target=record.path,
                    reason=f"Old {record.category} artifact in Downloads with no recent activity.",
                )
            )
    return recommendations


def _categorize(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in INSTALLER_SUFFIXES:
        return "installer"
    if suffix in ARCHIVE_SUFFIXES:
        return "archive"
    if suffix in TEMPORARY_SUFFIXES:
        return "temporary"
    if suffix in DOCUMENT_SUFFIXES:
        return "document"
    if suffix in MEDIA_SUFFIXES:
        return "media"
    if suffix in CODE_SUFFIXES:
        return "code"
    return "other"


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(HASH_CHUNK_SIZE):
            digest.update(chunk)
    return digest.hexdigest()
