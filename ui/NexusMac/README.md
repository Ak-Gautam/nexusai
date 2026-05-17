# NexusMac UI

This directory is reserved for the native macOS UI.

Planned responsibilities:

- global hotkey registration
- Apple Spotlight-style floating bar
- expanded floating results panel
- `Esc` to close
- click-outside to dismiss
- communication with the local Python backend

Interaction contract:

- default state is a single command-entry text bar
- the UI should not open into a chat transcript
- slash commands such as `/logs` and `/history` progressively reveal richer views
- when Nexus is running work or presenting structured output, the bar can expand into a floating results window
- when the interaction is complete, the UI should be able to collapse back to the compact bar

Implementation constraint:

- Swift owns only the native UI, hotkey, panel/window behavior, and app lifecycle
- Python owns orchestration, model control, tools, memory, and the local API contract

The initial UI implementation should use SwiftUI for view composition and AppKit where native window behavior requires it, likely centered around an `NSPanel`-based shell.

Current implementation status:

- a native Swift package executable exists under `ui/NexusMac`
- the app opens a compact command bar with an expandable output area
- the app talks to the local Python backend over HTTP at `http://127.0.0.1:8765`
- command input supports backend arguments such as `/runtime/load model_name=...`
- the app can fetch the typed model catalog and runtime status
- the app can load and unload llama.cpp text models
- chat displays a compact local transcript and sends bounded conversation context
- quick actions for `/models`, `/downloads`, `/runtime/status`, `/runtime/unload`, and `/chat/new` are present in the view

Run locally:

```bash
# Terminal 1, from the repository root
bash scripts/run_backend.sh

# Terminal 2, from the repository root
bash scripts/run_mac_ui.sh
```

Smoke-check the backend without opening the UI:

```bash
python3 scripts/smoke_backend.py
```

Current limitations:

- the current keyboard shortcut is app-local, not a true global hotkey yet
- the app assumes the backend is already running on `http://127.0.0.1:8765`
- loading and chatting require `llama-server` to be installed and discoverable on `PATH`
