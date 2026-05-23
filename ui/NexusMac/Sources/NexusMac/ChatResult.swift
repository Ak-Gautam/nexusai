import Foundation

struct ChatResult: Decodable, Equatable, Sendable {
    let runtime: RuntimeStatus
    let response: ChatCompletionResponse

    var assistantMessage: String {
        guard let choice = response.choices.first else { return "" }

        let content = choice.message.content?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !content.isEmpty {
            return content
        }

        let reasoningContent = choice.message.reasoningContent?.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
        if !reasoningContent.isEmpty {
            if choice.finishReason == "length" {
                return "The model used the response budget for reasoning and did not produce a final answer. Try again with thinking_enabled=false or a higher max_tokens value."
            }
            return "The model returned reasoning but no final answer. Try again with thinking_enabled=false."
        }

        return ""
    }
}

struct ChatCompletionResponse: Decodable, Equatable, Sendable {
    let choices: [ChatCompletionChoice]
}

struct ChatCompletionChoice: Decodable, Equatable, Sendable {
    let finishReason: String?
    let message: ChatCompletionMessage

    enum CodingKeys: String, CodingKey {
        case finishReason = "finish_reason"
        case message
    }
}

struct ChatCompletionMessage: Decodable, Equatable, Sendable {
    let role: String?
    let content: String?
    let reasoningContent: String?

    enum CodingKeys: String, CodingKey {
        case role
        case content
        case reasoningContent = "reasoning_content"
    }
}
