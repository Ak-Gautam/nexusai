from __future__ import annotations

import argparse
import json

from nexus_backend.api.schemas import CommandRequest
from nexus_backend.api.server import NexusApiServer
from nexus_backend.config import load_config
from nexus_backend.config import NexusConfig
from nexus_backend.memory.store import initialize_database
from nexus_backend.models import discover_model_registry
from nexus_backend.models import LlamaCppRuntimeManager
from nexus_backend.tasks.router import route_command


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    config = load_config()
    initialize_database(config.database_path)
    runtime_manager = LlamaCppRuntimeManager(
        model_root=config.model_root,
        data_root=config.data_root,
        llama_server_path=config.llama_server_path,
    )

    if args.command == "serve":
        server = NexusApiServer(
            (args.host, args.port),
            model_root=config.model_root,
            database_path=config.database_path,
            downloads_root=config.downloads_root,
            data_root=config.data_root,
            llama_server_path=config.llama_server_path,
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
            runtime_manager=runtime_manager,
        )
        print(json.dumps(response.to_dict(), ensure_ascii=True, indent=2))
        return

    if args.command == "runtime-load":
        state = runtime_manager.load(
            model_name=args.model_name,
            context_length=args.context_length,
            temperature=args.temperature,
            thinking_enabled=args.thinking == "on",
        )
        print(json.dumps(state.to_dict(), ensure_ascii=True, indent=2))
        return

    if args.command == "runtime-status":
        print(json.dumps(runtime_manager.status().to_dict(), ensure_ascii=True, indent=2))
        return

    if args.command == "runtime-unload":
        print(json.dumps(runtime_manager.unload().to_dict(), ensure_ascii=True, indent=2))
        return

    if args.command == "chat":
        result = runtime_manager.chat(
            model_name=args.model_name,
            messages=[{"role": "user", "content": args.prompt}],
            temperature=args.temperature,
            thinking_enabled=args.thinking == "on",
            max_tokens=args.max_tokens,
        )
        print(json.dumps(result, ensure_ascii=True, indent=2))
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
    run_parser.add_argument("nexus_command", choices=["/models", "/downloads", "/runtime/status"])

    load_parser = subparsers.add_parser("runtime-load", help="Load a llama.cpp model into llama-server")
    load_parser.add_argument("model_name")
    load_parser.add_argument("--context-length", type=int)
    load_parser.add_argument("--temperature", type=float, default=0.2)
    load_parser.add_argument("--thinking", choices=["on", "off"], default="on")

    subparsers.add_parser("runtime-status", help="Show active llama.cpp runtime state")
    subparsers.add_parser("runtime-unload", help="Stop the active llama.cpp runtime")

    chat_parser = subparsers.add_parser("chat", help="Send a single prompt to the active llama.cpp runtime")
    chat_parser.add_argument("prompt")
    chat_parser.add_argument("--model-name")
    chat_parser.add_argument("--temperature", type=float, default=0.2)
    chat_parser.add_argument("--thinking", choices=["on", "off"], default="on")
    chat_parser.add_argument("--max-tokens", type=int, default=512)

    return parser


def _print_bootstrap(config: NexusConfig) -> None:
    registry = discover_model_registry(config.model_root)
    print("Nexus backend bootstrap")
    print(f"project_root={config.project_root}")
    print(f"model_root={config.model_root}")
    print(f"database_path={config.database_path}")
    print(f"downloads_root={config.downloads_root}")
    print(f"llama_server_path={config.llama_server_path}")
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
