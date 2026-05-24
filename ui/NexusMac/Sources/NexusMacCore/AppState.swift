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
    @Published var supportedCommands = ["/models", "/downloads", "/runtime/status", "/runtime/unload", "/logs", "/frontend/logs", "/chat/new"]

    let backend = BackendClient()
    private let logger = FrontendLogger.shared
    private let maxChatContextMessages = 16
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

        if input == "/chat/new" {
            logger.info("command_local_chat_new")
            startNewChat()
            return
        }

        if input == "/frontend/logs" {
            showFrontendLogs()
            return
        }

        let request: BackendCommandRequest
        do {
            request = try CommandInputParser.parse(input)
        } catch {
            expandPanel()
            responseBody = error.localizedDescription
            statusText = "Invalid command"
            logger.error("command_parse_failed", metadata: ["input": input, "error": error.localizedDescription])
            return
        }

        isBusy = true
        expandPanel()
        statusText = "Running \(request.command)…"
        logger.info("command_started", metadata: ["command": request.command])

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
            logger.info("command_completed", metadata: ["command": request.command])
        } catch {
            responseBody = "Backend error: \(error.localizedDescription)"
            statusText = "Request failed"
            logger.error("command_failed", metadata: ["command": request.command, "error": error.localizedDescription])
        }

        isBusy = false
    }

    func loadModel(_ artifact: ModelArtifact) async {
        isBusy = true
        expandPanel()
        statusText = "Loading \(artifact.name)…"
        logger.info("runtime_load_started", metadata: ["model": artifact.name])

        do {
            let status = try await backend.loadRuntime(
                modelName: artifact.name,
                contextLength: artifact.recommendedContextLength > 0 ? artifact.recommendedContextLength : nil,
                thinkingEnabled: false
            )
            runtimeStatus = status
            responseBody = runtimeDetails(status)
            statusText = "Loaded \(artifact.name)"
            logger.info("runtime_load_completed", metadata: ["model": artifact.name])
        } catch {
            responseBody = "Backend error: \(error.localizedDescription)"
            statusText = "Load failed"
            logger.error("runtime_load_failed", metadata: ["model": artifact.name, "error": error.localizedDescription])
        }

        isBusy = false
    }

    func unloadRuntime() async {
        isBusy = true
        expandPanel()
        statusText = "Unloading runtime…"
        logger.info("runtime_unload_started")

        do {
            let status = try await backend.unloadRuntime()
            runtimeStatus = status
            responseBody = runtimeDetails(status)
            statusText = "Runtime unloaded"
            logger.info("runtime_unload_completed")
        } catch {
            responseBody = "Backend error: \(error.localizedDescription)"
            statusText = "Unload failed"
            logger.error("runtime_unload_failed", metadata: ["error": error.localizedDescription])
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

    func startNewChat() {
        chatTranscript = []
        isShowingChatTranscript = false
        responseBody = ""
        statusText = "New chat"
        commandText = ""
        expandPanel()
        focusTrigger = UUID()
    }

    private func showFrontendLogs() {
        expandPanel()
        isShowingChatTranscript = false
        responseBody = "Frontend log: \(logger.logFileURL.path)\n\n" + logger.recentLines(limit: 200).joined(separator: "\n")
        statusText = "Completed /frontend/logs"
        commandText = ""
        logger.info("frontend_logs_viewed")
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
        chatArguments["messages"] = .array(chatContextMessages().map { message in
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

    private func chatContextMessages() -> [ChatTranscriptMessage] {
        Array(chatTranscript.suffix(maxChatContextMessages))
    }

    private func runtimeDetails(_ status: RuntimeStatus) -> String {
        guard status.loaded else {
            return "No model loaded."
        }

        var lines = ["Loaded model: \(status.modelName ?? "Unknown")"]
        if let contextLength = status.contextLength {
            lines.append("Context length: \(contextLength)")
        }
        if let temperature = status.temperature {
            lines.append("Temperature: \(temperature)")
        }
        if let thinkingEnabled = status.thinkingEnabled {
            lines.append("Thinking: \(thinkingEnabled ? "enabled" : "disabled")")
        }
        if let serverURL = status.serverURL {
            lines.append("Server: \(serverURL)")
        }
        if let processID = status.processID {
            lines.append("Process ID: \(processID)")
        }
        return lines.joined(separator: "\n")
    }
}
