from __future__ import annotations

import argparse
import json

from nexus_backend.api.schemas import CommandRequest
from nexus_backend.api.server import NexusApiServer
from nexus_backend.config import load_config
from nexus_backend.config import NexusConfig
from nexus_backend.memory.store import initialize_database
from nexus_backend.models import discover_model_registry
from nexus_backend.tasks.router import route_command


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    config = load_config()
    initialize_database(config.database_path)

    if args.command == "serve":
        server = NexusApiServer(
            (args.host, args.port),
            model_root=config.model_root,
            database_path=config.database_path,
            downloads_root=config.downloads_root,
        )
        print(f"Nexus backend listening on http://{args.host}:{args.port}")
        server.serve_forever()
        return

    if args.command == "models":
        registry = discover_model_registry(config.model_root)
        print(
            json.dumps(
                {
                    "artifacts": [
                        {
                            "name": artifact.name,
                            "path": str(artifact.path),
                            "runtime": artifact.runtime,
                            "kind": artifact.kind,
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
                ensure_ascii=True,
                indent=2,
            )
        )
        return

    if args.command == "run":
        response = route_command(
            CommandRequest(command=args.nexus_command),
            model_root=config.model_root,
            downloads_root=config.downloads_root,
        )
        print(json.dumps(response.to_dict(), ensure_ascii=True, indent=2))
        return

    _print_bootstrap(config)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="nexus-backend")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Run the local Nexus HTTP API")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)

    subparsers.add_parser("models", help="Print discovered local model inventory")

    run_parser = subparsers.add_parser("run", help="Run a Nexus command through the task router")
    run_parser.add_argument("nexus_command", choices=["/models", "/downloads"])

    return parser


def _print_bootstrap(config: NexusConfig) -> None:
    registry = discover_model_registry(config.model_root)
    print("Nexus backend bootstrap")
    print(f"project_root={config.project_root}")
    print(f"model_root={config.model_root}")
    print(f"database_path={config.database_path}")
    print(f"downloads_root={config.downloads_root}")
    print(f"discovered_models={len(registry.artifacts)}")
    print(
        "model_defaults="
        f"router:{registry.defaults.router},"
        f"planner:{registry.defaults.planner},"
        f"ocr:{registry.defaults.ocr},"
        f"vlm:{registry.defaults.vlm}"
    )


if __name__ == "__main__":
    main()
