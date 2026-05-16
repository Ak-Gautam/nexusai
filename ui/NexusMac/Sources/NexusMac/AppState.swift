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
    @Published var runtimeStatus: RuntimeStatus?
    @Published var chatTranscript: [ChatTranscriptMessage] = []
    @Published var isShowingChatTranscript = false
    @Published var supportedCommands = ["/models", "/downloads", "/runtime/status"]

    let backend = BackendClient()
    private var hasRequestedModelCatalog = false
    private var hasRequestedRuntimeStatus = false

    var loadableModels: [ModelArtifact] {
        modelCatalog?.artifacts.filter { artifact in
            artifact.runtime == "llama.cpp" && artifact.kind == "text"
        } ?? []
    }

    var defaultChatModelName: String? {
        if let router = modelCatalog?.defaults.router,
           loadableModels.contains(where: { $0.name == router }) {
            return router
        }
        return loadableModels.first?.name
    }

    var runtimeSummary: String {
        guard let runtimeStatus else {
            return "Runtime status unknown"
        }
        guard runtimeStatus.loaded else {
            return "No model loaded"
        }

        let modelName = runtimeStatus.modelName ?? "Unknown model"
        if let contextLength = runtimeStatus.contextLength {
            return "\(modelName) loaded, context \(contextLength)"
        }
        return "\(modelName) loaded"
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

    func refreshRuntimeStatusIfNeeded() async {
        guard !hasRequestedRuntimeStatus else { return }
        hasRequestedRuntimeStatus = true
        await refreshRuntimeStatus()
    }

    func refreshRuntimeStatus() async {
        do {
            runtimeStatus = try await backend.fetchRuntimeStatus()
        } catch {
            runtimeStatus = nil
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
            if request.command == "/chat" {
                let result = try await submitChat(arguments: request.arguments)
                responseBody = result.assistantMessage
                runtimeStatus = result.runtime
            } else {
                isShowingChatTranscript = false
                let result = try await backend.run(command: request.command, arguments: request.arguments)
                responseBody = result
                await refreshRuntimeStatusIfNeeded(after: request.command)
            }
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
            await refreshRuntimeStatus()
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
        chatTranscript = []
        isShowingChatTranscript = false
        statusText = "Ready"
        focusTrigger = UUID()   // Triggers onChange → re-focus text field
    }

    private func expandPanel() {
        isExpanded = true
        NotificationCenter.default.post(name: .nexusPanelExpand, object: nil)
    }

    private func refreshRuntimeStatusIfNeeded(after command: String) async {
        if ["/runtime/load", "/runtime/unload", "/runtime/status", "/chat"].contains(command) {
            await refreshRuntimeStatus()
        }
    }

    private func chatArguments(from arguments: [String: BackendArgument]) async -> [String: BackendArgument] {
        var resolvedArguments = arguments
        guard resolvedArguments["model_name"] == nil else {
            return resolvedArguments
        }

        await refreshRuntimeStatusIfNeeded()
        if runtimeStatus?.loaded == true {
            return resolvedArguments
        }

        await refreshModelCatalogIfNeeded()
        if let defaultChatModelName {
            resolvedArguments["model_name"] = .string(defaultChatModelName)
        }
        return resolvedArguments
    }

    private func submitChat(arguments: [String: BackendArgument]) async throws -> ChatResult {
        guard case .string(let prompt)? = arguments["prompt"] else {
            let result = try await backend.chat(arguments: await chatArguments(from: arguments))
            appendAssistantMessage(result.assistantMessage)
            return result
        }

        let userMessage = ChatTranscriptMessage(role: .user, content: prompt)
        chatTranscript.append(userMessage)
        isShowingChatTranscript = true

        var chatArguments = arguments
        chatArguments["prompt"] = nil
        chatArguments["messages"] = .array(chatTranscript.map { message in
            .object([
                "role": .string(message.role.rawValue),
                "content": .string(message.content),
            ])
        })

        do {
            let result = try await backend.chat(arguments: await self.chatArguments(from: chatArguments))
            appendAssistantMessage(result.assistantMessage)
            return result
        } catch {
            chatTranscript.removeAll { $0.id == userMessage.id }
            if chatTranscript.isEmpty {
                isShowingChatTranscript = false
            }
            throw error
        }
    }

    private func appendAssistantMessage(_ content: String) {
        let messageContent = content.isEmpty ? "No assistant message returned." : content
        chatTranscript.append(ChatTranscriptMessage(role: .assistant, content: messageContent))
    }
}
