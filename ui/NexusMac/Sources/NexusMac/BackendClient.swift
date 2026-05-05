import Foundation

struct BackendClient {
    let baseURL = URL(string: "http://127.0.0.1:8765")!

    func health() async throws -> String {
        let (data, _) = try await URLSession.shared.data(from: baseURL.appending(path: "health"))
        return String(decoding: data, as: UTF8.self)
    }

    func run(command: String) async throws -> String {
        var request = URLRequest(url: baseURL.appending(path: "commands"))
        request.httpMethod = "POST"
        request.addValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try JSONEncoder().encode(CommandEnvelope(command: command, arguments: [:]))
        let (data, _) = try await URLSession.shared.data(for: request)
        return String(decoding: data, as: UTF8.self)
    }
}

private struct CommandEnvelope: Encodable {
    let command: String
    let arguments: [String: String]
}
