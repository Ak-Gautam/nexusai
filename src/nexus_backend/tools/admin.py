from __future__ import annotations

from dataclasses import asdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from nexus_backend.models import LlamaCppRuntimeManager
from nexus_backend.models import discover_model_registry
from nexus_backend.tools.downloads import scan_downloads


@dataclass(frozen=True)
class ToolResult:
    name: str
    ok: bool
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdminToolbox:
    def __init__(self, model_root: Path, downloads_root: Path, runtime_manager: LlamaCppRuntimeManager) -> None:
        self.model_root = model_root
        self.downloads_root = downloads_root
        self.runtime_manager = runtime_manager

    def specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "downloads_scan",
                "description": "Scan the user's Downloads folder and return inventory, duplicates, stale files, large files, and dry-run recommendations.",
                "arguments": {},
            },
            {
                "name": "model_registry",
                "description": "List local models, launch paths, runtime families, context hints, and default model roles.",
                "arguments": {},
            },
            {
                "name": "runtime_status",
                "description": "Return the currently loaded llama.cpp runtime state.",
                "arguments": {},
            },
        ]

    def run(self, name: str, arguments: dict[str, Any] | None = None) -> ToolResult:
        _ = arguments or {}
        if name == "downloads_scan":
            report = scan_downloads(self.downloads_root)
            return ToolResult(name=name, ok=True, payload=_compact_downloads_report(report.to_dict()))

        if name == "model_registry":
            registry = discover_model_registry(self.model_root)
            return ToolResult(
                name=name,
                ok=True,
                payload={
                    "artifacts": [
                        {
                            "name": artifact.name,
                            "path": str(artifact.path),
                            "launch_path": str(artifact.launch_path),
                            "runtime": artifact.runtime,
                            "kind": artifact.kind,
                            "supports_thinking": artifact.supports_thinking,
                            "recommended_context_length": artifact.recommended_context_length,
                        }
                        for artifact in registry.artifacts
                    ],
                    "defaults": {
                        "router": registry.defaults.router,
                        "planner": registry.defaults.planner,
                        "ocr": registry.defaults.ocr,
                        "vlm": registry.defaults.vlm,
                    },
                },
            )

        if name == "runtime_status":
            return ToolResult(name=name, ok=True, payload=self.runtime_manager.status().to_dict())

        return ToolResult(name=name, ok=False, payload={"error": f"Unknown tool: {name}"})


def _compact_downloads_report(report: dict[str, Any]) -> dict[str, Any]:
    return {
        "root": report["root"],
        "scanned_files": report["scanned_files"],
        "total_size_bytes": report["total_size_bytes"],
        "large_files": report["large_files"][:8],
        "stale_files": report["stale_files"][:8],
        "duplicate_groups": [
            [
                {
                    "path": item["path"],
                    "name": item["name"],
                    "size_bytes": item["size_bytes"],
                    "modified_at": item["modified_at"],
                    "category": item["category"],
                }
                for item in group[:3]
            ]
            for group in report["duplicate_groups"][:8]
        ],
        "recommendations": report["recommendations"][:12],
    }
