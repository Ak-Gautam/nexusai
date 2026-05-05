import AppKit
import SwiftUI

@main
struct NexusMacApp: App {
    @StateObject private var state = AppState()

    var body: some Scene {
        WindowGroup {
            CommandBarView(state: state)
                .frame(minWidth: 720, idealWidth: 760)
        }
        .windowStyle(.hiddenTitleBar)
        .windowToolbarStyle(.unified(showsTitle: false))
        .commands {
            CommandGroup(after: .appInfo) {
                Button("Focus Command Bar") {
                    NSApp.activate(ignoringOtherApps: true)
                }
                .keyboardShortcut(" ", modifiers: [.control])
            }
        }
    }
}
