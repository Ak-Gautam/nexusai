import Foundation

@MainActor
final class AppState: ObservableObject {
    @Published var commandText = ""
    @Published var isExpanded = false
    @Published var isBusy = false
    @Published var statusText = "Ready"
    @Published var responseBody = ""
    @Published var focusTrigger = UUID()
    @Published var supportedCommands = ["/models", "/downloads", "/runtime/status"]

    let backend = BackendClient()

    func submitCommand() async {
        let command = commandText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !command.isEmpty else { return }

        isBusy = true
        isExpanded = true
        statusText = "Running \(command)…"

        // Tell the AppDelegate to expand the panel.
        NotificationCenter.default.post(name: .nexusPanelExpand, object: nil)

        do {
            let result = try await backend.run(command: command)
            responseBody = result
            statusText = "Completed \(command)"
        } catch {
            responseBody = "Backend error: \(error.localizedDescription)"
            statusText = "Request failed"
        }

        isBusy = false
    }

    func reset() {
        commandText = ""
        isExpanded = false
        responseBody = ""
        statusText = "Ready"
        focusTrigger = UUID()   // Triggers onChange → re-focus text field
    }
}
