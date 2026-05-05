from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


GGUF_SUFFIXES = {".gguf"}
MLX_SUFFIXES = {".safetensors"}


@dataclass(frozen=True)
class ModelArtifact:
    name: str
    path: Path
    runtime: str
    kind: str


@dataclass(frozen=True)
class ModelRoleDefaults:
    router: str | None
    planner: str | None
    ocr: str | None
    vlm: str | None


@dataclass(frozen=True)
class ModelRegistry:
    artifacts: tuple[ModelArtifact, ...]
    defaults: ModelRoleDefaults


def discover_model_registry(model_root: Path) -> ModelRegistry:
    artifacts = tuple(sorted(_discover_artifacts(model_root), key=lambda item: item.name.lower()))
    defaults = ModelRoleDefaults(
        router=_pick_default(artifacts, ("qwen3.5-2b", "gemma-4-e4b")),
        planner=_pick_default(artifacts, ("qwen3.6-27b", "gemma4-31b", "gemma-4-31b")),
        ocr=_pick_default(artifacts, ("glm-ocr",)),
        vlm=_pick_default(artifacts, ("lfm2.5-vl",)),
    )
    return ModelRegistry(artifacts=artifacts, defaults=defaults)


def _discover_artifacts(model_root: Path) -> list[ModelArtifact]:
    if not model_root.exists():
        return []

    artifacts: list[ModelArtifact] = []
    for path in sorted(model_root.iterdir(), key=lambda item: item.name.lower()):
        artifact = _classify_path(path)
        if artifact is not None:
            artifacts.append(artifact)
    return artifacts


def _classify_path(path: Path) -> ModelArtifact | None:
    if path.is_file():
        suffix = path.suffix.lower()
        if suffix in GGUF_SUFFIXES:
            return ModelArtifact(name=path.stem, path=path, runtime="llama.cpp", kind="text")
        if suffix in MLX_SUFFIXES:
            return _classify_mlx_artifact(path.stem, path)
        return None

    if path.is_dir():
        lower_name = path.name.lower()
        if "mlx" in lower_name:
            return _classify_mlx_artifact(path.name, path)
        return ModelArtifact(name=path.name, path=path, runtime="llama.cpp", kind="text")

    return None


def _classify_mlx_artifact(name: str, path: Path) -> ModelArtifact:
    lower_name = name.lower()
    kind = "ocr" if "ocr" in lower_name else "vlm" if "vl" in lower_name else "multimodal"
    return ModelArtifact(name=name, path=path, runtime="mlx", kind=kind)


def _pick_default(artifacts: tuple[ModelArtifact, ...], preferred_terms: tuple[str, ...]) -> str | None:
    for term in preferred_terms:
        for artifact in artifacts:
            if term in artifact.name.lower():
                return artifact.name
    return None
