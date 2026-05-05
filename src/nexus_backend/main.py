from __future__ import annotations

from nexus_backend.config import load_config
from nexus_backend.models import discover_model_registry


def main() -> None:
    config = load_config()
    registry = discover_model_registry(config.model_root)

    print("Nexus backend bootstrap")
    print(f"project_root={config.project_root}")
    print(f"model_root={config.model_root}")
    print(f"database_path={config.database_path}")
    print(f"discovered_models={len(registry.artifacts)}")
    print(
        "model_defaults="
        f"router:{registry.defaults.router},"
        f"planner:{registry.defaults.planner},"
        f"ocr:{registry.defaults.ocr},"
        f"vlm:{registry.defaults.vlm}"
    )

    for artifact in registry.artifacts:
        print(
            "model="
            f"name:{artifact.name},"
            f"runtime:{artifact.runtime},"
            f"kind:{artifact.kind},"
            f"path:{artifact.path}"
        )


if __name__ == "__main__":
    main()
