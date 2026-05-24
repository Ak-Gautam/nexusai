from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


LOGGER_NAMESPACE = "nexus_backend"
BACKEND_LOG_NAME = "backend.log"
MAX_LOG_BYTES = 2_000_000
BACKUP_COUNT = 3


def configure_backend_logging(data_root: Path) -> Path:
    logs_dir = data_root / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_path = logs_dir / BACKEND_LOG_NAME

    logger = logging.getLogger(LOGGER_NAMESPACE)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not _has_file_handler(logger, log_path):
        handler = RotatingFileHandler(
            log_path,
            maxBytes=MAX_LOG_BYTES,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        logger.addHandler(handler)

    return log_path


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{LOGGER_NAMESPACE}.{name}")


def list_log_files(data_root: Path) -> list[dict[str, object]]:
    logs_dir = data_root / "logs"
    if not logs_dir.exists():
        return []

    files = []
    for path in sorted(logs_dir.glob("*.log")):
        stat = path.stat()
        files.append(
            {
                "name": path.name,
                "path": str(path),
                "size_bytes": stat.st_size,
                "modified_at": stat.st_mtime,
            }
        )
    return files


def read_recent_logs(data_root: Path, source: str = "all", limit: int = 200) -> dict[str, list[str]]:
    logs_dir = data_root / "logs"
    if not logs_dir.exists():
        return {}

    log_names = _source_log_names(source)
    output: dict[str, list[str]] = {}
    for path in sorted(logs_dir.glob("*.log")):
        if log_names is not None and path.name not in log_names:
            continue
        output[path.name] = _tail_lines(path, limit)
    return output


def _source_log_names(source: str) -> set[str] | None:
    normalized = source.strip().lower()
    if normalized in {"", "all"}:
        return None
    if normalized == "backend":
        return {BACKEND_LOG_NAME}
    if normalized == "runtime":
        return {"llama-server.stdout.log", "llama-server.stderr.log"}
    return {normalized if normalized.endswith(".log") else f"{normalized}.log"}


def _tail_lines(path: Path, limit: int) -> list[str]:
    if limit <= 0:
        return []

    try:
        with path.open("r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except OSError as exc:
        return [f"Unable to read {path}: {exc}"]

    return [line.rstrip("\n") for line in lines[-limit:]]


def _has_file_handler(logger: logging.Logger, log_path: Path) -> bool:
    resolved_path = log_path.resolve()
    for handler in logger.handlers:
        if isinstance(handler, RotatingFileHandler) and Path(handler.baseFilename).resolve() == resolved_path:
            return True
    return False
