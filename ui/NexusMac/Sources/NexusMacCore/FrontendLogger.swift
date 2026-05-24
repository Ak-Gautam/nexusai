import Foundation
import OSLog

public final class FrontendLogger: @unchecked Sendable {
    public static let shared = FrontendLogger()

    public let logFileURL: URL
    private let osLogger = Logger(subsystem: "NexusMac", category: "frontend")
    private let lock = NSLock()

    private init() {
        let libraryURL = FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask).first
            ?? FileManager.default.homeDirectoryForCurrentUser.appending(path: "Library")
        let logsURL = libraryURL.appending(path: "Logs").appending(path: "Nexus")
        try? FileManager.default.createDirectory(at: logsURL, withIntermediateDirectories: true)
        logFileURL = logsURL.appending(path: "frontend.log")
    }

    public func info(_ event: String, metadata: [String: String] = [:]) {
        write(level: "INFO", event: event, metadata: metadata)
    }

    public func error(_ event: String, metadata: [String: String] = [:]) {
        write(level: "ERROR", event: event, metadata: metadata)
    }

    public func recentLines(limit: Int = 200) -> [String] {
        guard let data = try? Data(contentsOf: logFileURL),
              let body = String(data: data, encoding: .utf8) else {
            return ["No frontend log file exists yet: \(logFileURL.path)"]
        }
        let lines = body.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
        return Array(lines.suffix(max(1, limit)))
    }

    private func write(level: String, event: String, metadata: [String: String]) {
        let line = "\(Self.timestamp()) \(level) \(event) \(Self.metadataString(metadata))\n"
        lock.lock()
        defer { lock.unlock() }

        if !FileManager.default.fileExists(atPath: logFileURL.path) {
            FileManager.default.createFile(atPath: logFileURL.path, contents: nil)
        }
        if let handle = try? FileHandle(forWritingTo: logFileURL) {
            defer { try? handle.close() }
            _ = try? handle.seekToEnd()
            if let data = line.data(using: .utf8) {
                try? handle.write(contentsOf: data)
            }
        }

        if level == "ERROR" {
            osLogger.error("\(event, privacy: .public) \(Self.metadataString(metadata), privacy: .public)")
        } else {
            osLogger.info("\(event, privacy: .public) \(Self.metadataString(metadata), privacy: .public)")
        }
    }

    private static func timestamp() -> String {
        ISO8601DateFormatter().string(from: Date())
    }

    private static func metadataString(_ metadata: [String: String]) -> String {
        guard !metadata.isEmpty else { return "{}" }
        let pairs = metadata.keys.sorted().map { key in
            "\"\(escape(key))\":\"\(escape(metadata[key] ?? ""))\""
        }
        return "{\(pairs.joined(separator: ","))}"
    }

    private static func escape(_ value: String) -> String {
        value
            .replacingOccurrences(of: "\\", with: "\\\\")
            .replacingOccurrences(of: "\"", with: "\\\"")
            .replacingOccurrences(of: "\n", with: "\\n")
    }
}
