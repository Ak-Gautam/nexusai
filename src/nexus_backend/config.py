from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class NexusConfig:
    project_root: Path
    model_root: Path
    database_path: Path
    downloads_root: Path


def load_config(project_root: Path | None = None) -> NexusConfig:
    root = project_root or Path(__file__).resolve().parents[2]
    model_root = Path.home() / "model_storage" / "open"
    database_path = root / "data" / "nexus.sqlite3"
    downloads_root = Path.home() / "Downloads"
    return NexusConfig(
        project_root=root,
        model_root=model_root,
        database_path=database_path,
        downloads_root=downloads_root,
    )
