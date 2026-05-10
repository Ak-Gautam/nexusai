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
        let input = commandText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else { return }

        let request: BackendCommandRequest
        do {
            request = try CommandInputParser.parse(input)
        } catch {
            isExpanded = true
            responseBody = error.localizedDescription
            statusText = "Invalid command"
            NotificationCenter.default.post(name: .nexusPanelExpand, object: nil)
            return
        }

        isBusy = true
        isExpanded = true
        statusText = "Running \(request.command)…"

        // Tell the AppDelegate to expand the panel.
        NotificationCenter.default.post(name: .nexusPanelExpand, object: nil)

        do {
            let result = try await backend.run(command: request.command, arguments: request.arguments)
            responseBody = result
            statusText = "Completed \(request.command)"
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
