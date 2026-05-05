import Foundation

@MainActor
final class AppState: ObservableObject {
    @Published var commandText = ""
    @Published var isExpanded = false
    @Published var isBusy = false
    @Published var statusText = "Ready"
    @Published var responseBody = ""
    @Published var supportedCommands = ["/models", "/downloads"]

    let backend = BackendClient()

    func submitCommand() async {
        let command = commandText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !command.isEmpty else { return }

        isBusy = true
        isExpanded = true
        statusText = "Running \(command)"

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
}
