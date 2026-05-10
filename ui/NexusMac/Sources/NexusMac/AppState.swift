import Foundation

@MainActor
final class AppState: ObservableObject {
    @Published var commandText = ""
    @Published var isExpanded = false
    @Published var isBusy = false
    @Published var statusText = "Ready"
    @Published var responseBody = ""
    @Published var focusTrigger = UUID()
    @Published var modelCatalog: ModelCatalog?
    @Published var isLoadingModelCatalog = false
    @Published var supportedCommands = ["/models", "/downloads", "/runtime/status"]

    let backend = BackendClient()
    private var hasRequestedModelCatalog = false

    var loadableModels: [ModelArtifact] {
        modelCatalog?.artifacts.filter { artifact in
            artifact.runtime == "llama.cpp" && artifact.kind == "text"
        } ?? []
    }

    func refreshModelCatalogIfNeeded() async {
        guard !hasRequestedModelCatalog else { return }

        hasRequestedModelCatalog = true
        isLoadingModelCatalog = true
        defer { isLoadingModelCatalog = false }

        do {
            modelCatalog = try await backend.fetchModelCatalog()
        } catch {
            modelCatalog = nil
        }
    }

    func submitCommand() async {
        let input = commandText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !input.isEmpty else { return }

        let request: BackendCommandRequest
        do {
            request = try CommandInputParser.parse(input)
        } catch {
            expandPanel()
            responseBody = error.localizedDescription
            statusText = "Invalid command"
            return
        }

        isBusy = true
        expandPanel()
        statusText = "Running \(request.command)…"

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

    func loadModel(_ artifact: ModelArtifact) async {
        isBusy = true
        expandPanel()
        statusText = "Loading \(artifact.name)…"

        var arguments: [String: BackendArgument] = [
            "model_name": .string(artifact.name),
            "thinking_enabled": .bool(artifact.supportsThinking),
        ]
        if artifact.recommendedContextLength > 0 {
            arguments["context_length"] = .int(artifact.recommendedContextLength)
        }

        do {
            let result = try await backend.run(command: "/runtime/load", arguments: arguments)
            responseBody = result
            statusText = "Loaded \(artifact.name)"
        } catch {
            responseBody = "Backend error: \(error.localizedDescription)"
            statusText = "Load failed"
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

    private func expandPanel() {
        isExpanded = true
        NotificationCenter.default.post(name: .nexusPanelExpand, object: nil)
    }
}
