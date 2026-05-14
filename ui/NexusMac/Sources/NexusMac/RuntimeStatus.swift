import Foundation

struct RuntimeStatus: Decodable, Equatable, Sendable {
    let loaded: Bool
    let modelName: String?
    let modelPath: String?
    let serverURL: String?
    let processID: Int?
    let contextLength: Int?
    let temperature: Double?
    let thinkingEnabled: Bool?
    let supportsThinking: Bool?

    private enum CodingKeys: String, CodingKey {
        case loaded
        case modelName = "model_name"
        case modelPath = "model_path"
        case serverURL = "server_url"
        case processID = "process_id"
        case contextLength = "context_length"
        case temperature
        case thinkingEnabled = "thinking_enabled"
        case supportsThinking = "supports_thinking"
    }
}
