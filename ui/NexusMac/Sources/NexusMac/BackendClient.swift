import Foundation

struct BackendClient: Sendable {
    let baseURL = URL(string: "http://127.0.0.1:8765")!

    func health() async throws -> String {
        let (data, _) = try await URLSession.shared.data(from: baseURL.appending(path: "health"))
        return String(decoding: data, as: UTF8.self)
    }

    func run(command: String, arguments: [String: BackendArgument] = [:]) async throws -> String {
        let data = try await runData(command: command, arguments: arguments)
        return String(decoding: data, as: UTF8.self)
    }

    func fetchModelCatalog() async throws -> ModelCatalog {
        let data = try await runData(command: "/models")
        let response = try JSONDecoder().decode(CommandResponseEnvelope<ModelCatalog>.self, from: data)
        return response.payload
    }

    func fetchRuntimeStatus() async throws -> RuntimeStatus {
        let data = try await runData(command: "/runtime/status")
        let response = try JSONDecoder().decode(CommandResponseEnvelope<RuntimeStatus>.self, from: data)
        return response.payload
    }

    private func runData(command: String, arguments: [String: BackendArgument] = [:]) async throws -> Data {
        var request = URLRequest(url: baseURL.appending(path: "commands"))
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(CommandEnvelope(command: command, arguments: arguments))
        let (data, _) = try await URLSession.shared.data(for: request)
        return data
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

private struct CommandResponseEnvelope<Payload: Decodable>: Decodable {
    let ok: Bool
    let command: String
    let payload: Payload
}
