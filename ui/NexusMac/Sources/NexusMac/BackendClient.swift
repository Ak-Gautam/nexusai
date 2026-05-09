import Foundation

struct BackendClient: Sendable {
    let baseURL = URL(string: "http://127.0.0.1:8765")!

    func health() async throws -> String {
        let (data, _) = try await URLSession.shared.data(from: baseURL.appending(path: "health"))
        return String(decoding: data, as: UTF8.self)
    }

    func run(command: String, arguments: [String: BackendArgument] = [:]) async throws -> String {
        var request = URLRequest(url: baseURL.appending(path: "commands"))
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(CommandEnvelope(command: command, arguments: arguments))
        let (data, _) = try await URLSession.shared.data(for: request)
        return String(decoding: data, as: UTF8.self)
    }
}

enum BackendArgument: Encodable, Sendable, Equatable {
    case string(String)
    case int(Int)
    case double(Double)
    case bool(Bool)

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .int(let value):
            try container.encode(value)
        case .double(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        }
    }
}

private struct CommandEnvelope: Encodable {
    let command: String
    let arguments: [String: BackendArgument]
}
