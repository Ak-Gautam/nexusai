import Foundation

struct ChatResult: Decodable, Equatable, Sendable {
    let runtime: RuntimeStatus
    let response: ChatCompletionResponse

    var assistantMessage: String {
        response.choices.first?.message.content.trimmingCharacters(in: .whitespacesAndNewlines) ?? ""
    }
}

struct ChatCompletionResponse: Decodable, Equatable, Sendable {
    let choices: [ChatCompletionChoice]
}

struct ChatCompletionChoice: Decodable, Equatable, Sendable {
    let message: ChatCompletionMessage
}

struct ChatCompletionMessage: Decodable, Equatable, Sendable {
    let role: String?
    let content: String
}
