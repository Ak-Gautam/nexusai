from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from dataclasses import field
from typing import Any


@dataclass(frozen=True)
class HealthResponse:
    ok: bool
    service: str
    database_ready: bool
    model_count: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CommandRequest:
    command: str
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CommandResponse:
    ok: bool
    command: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
