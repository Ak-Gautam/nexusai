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

    func chat(arguments: [String: BackendArgument]) async throws -> ChatResult {
        let data = try await runData(command: "/chat", arguments: arguments)
        let response = try JSONDecoder().decode(CommandResponseEnvelope<ChatResult>.self, from: data)
        return response.payload
    }

    private func runData(command: String, arguments: [String: BackendArgument] = [:]) async throws -> Data {
        var request = URLRequest(url: baseURL.appending(path: "commands"))
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(CommandEnvelope(command: command, arguments: arguments))
        let (data, response) = try await URLSession.shared.data(for: request)
        if let httpResponse = response as? HTTPURLResponse, !(200..<300).contains(httpResponse.statusCode) {
            throw BackendError.http(statusCode: httpResponse.statusCode, body: String(decoding: data, as: UTF8.self))
        }
        return data
    }
}

enum BackendError: LocalizedError, Equatable {
    case http(statusCode: Int, body: String)

    var errorDescription: String? {
        switch self {
        case .http(let statusCode, let body):
            let trimmedBody = body.trimmingCharacters(in: .whitespacesAndNewlines)
            if trimmedBody.isEmpty {
                return "Backend returned HTTP \(statusCode)."
            }
            return trimmedBody
        }
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
