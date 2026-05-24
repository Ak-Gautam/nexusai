import Foundation

public struct BackendCommandRequest: Equatable, Sendable {
    public let command: String
    public let arguments: [String: BackendArgument]
}

enum CommandInputParseError: LocalizedError, Equatable {
    case emptyInput
    case malformedArgument(String)
    case unterminatedQuote
    case invalidArgumentValue(name: String, value: String, expectedType: BackendArgumentType)

    var errorDescription: String? {
        switch self {
        case .emptyInput:
            return "Enter a command or prompt."
        case .malformedArgument(let token):
            return "Invalid argument '\(token)'. Use key=value syntax."
        case .unterminatedQuote:
            return "Close the quoted argument value."
        case .invalidArgumentValue(let name, let value, let expectedType):
            return "Invalid value '\(value)' for \(name). Expected \(expectedType.description)."
        }
    }
}

public enum CommandInputParser {
    public static func parse(_ input: String) throws -> BackendCommandRequest {
        let trimmedInput = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmedInput.isEmpty else {
            throw CommandInputParseError.emptyInput
        }

        guard trimmedInput.hasPrefix("/") else {
            return BackendCommandRequest(command: "/chat", arguments: ["prompt": .string(trimmedInput)])
        }

        let tokens = try tokenize(trimmedInput)
        guard let command = tokens.first else {
            throw CommandInputParseError.emptyInput
        }

        let argumentTokens = Array(tokens.dropFirst())
        if command == "/chat", containsPromptText(argumentTokens) {
            let prompt = trimmedInput.dropFirst(command.count).trimmingCharacters(in: .whitespacesAndNewlines)
            return BackendCommandRequest(command: command, arguments: ["prompt": .string(prompt)])
        }

        return BackendCommandRequest(
            command: command,
            arguments: try parseArguments(argumentTokens, for: command)
        )
    }

    private static func parseArguments(_ tokens: [String], for command: String) throws -> [String: BackendArgument] {
        var arguments: [String: BackendArgument] = [:]

        for token in tokens {
            guard let separator = token.firstIndex(of: "=") else {
                throw CommandInputParseError.malformedArgument(token)
            }

            let name = String(token[..<separator]).trimmingCharacters(in: .whitespacesAndNewlines)
            let value = String(token[token.index(after: separator)...]).trimmingCharacters(in: .whitespacesAndNewlines)
            guard !name.isEmpty else {
                throw CommandInputParseError.malformedArgument(token)
            }

            arguments[name] = try argumentType(for: name, command: command).parse(value, name: name)
        }

        return arguments
    }

    private static func containsPromptText(_ tokens: [String]) -> Bool {
        !tokens.isEmpty && !tokens.allSatisfy { $0.contains("=") }
    }

    private static func argumentType(for name: String, command: String) -> BackendArgumentType {
        BackendCommandSchemas.typesByCommand[command]?[name] ?? .string
    }

    private static func tokenize(_ input: String) throws -> [String] {
        var tokens: [String] = []
        var current = ""
        var quotedBy: Character?
        var isEscaped = false

        for character in input {
            if isEscaped {
                current.append(character)
                isEscaped = false
                continue
            }

            if character == "\\" {
                isEscaped = true
                continue
            }

            if character == "\"" || character == "'" {
                if quotedBy == character {
                    quotedBy = nil
                } else if quotedBy == nil {
                    quotedBy = character
                } else {
                    current.append(character)
                }
                continue
            }

            if character.isWhitespace && quotedBy == nil {
                if !current.isEmpty {
                    tokens.append(current)
                    current = ""
                }
                continue
            }

            current.append(character)
        }

        if quotedBy != nil {
            throw CommandInputParseError.unterminatedQuote
        }
        if isEscaped {
            current.append("\\")
        }
        if !current.isEmpty {
            tokens.append(current)
        }

        return tokens
    }
}

enum BackendArgumentType: Equatable, Sendable, CustomStringConvertible {
    case string
    case int
    case double
    case bool

    var description: String {
        switch self {
        case .string:
            return "a string"
        case .int:
            return "an integer"
        case .double:
            return "a number"
        case .bool:
            return "true or false"
        }
    }

    func parse(_ value: String, name: String) throws -> BackendArgument {
        switch self {
        case .string:
            return .string(value)
        case .int:
            guard let intValue = Int(value) else {
                throw CommandInputParseError.invalidArgumentValue(name: name, value: value, expectedType: self)
            }
            return .int(intValue)
        case .double:
            guard let doubleValue = Double(value) else {
                throw CommandInputParseError.invalidArgumentValue(name: name, value: value, expectedType: self)
            }
            return .double(doubleValue)
        case .bool:
            switch value.lowercased() {
            case "true":
                return .bool(true)
            case "false":
                return .bool(false)
            default:
                throw CommandInputParseError.invalidArgumentValue(name: name, value: value, expectedType: self)
            }
        }
    }
}

private enum BackendCommandSchemas {
    static let typesByCommand: [String: [String: BackendArgumentType]] = [
        "/runtime/load": [
            "model_name": .string,
            "context_length": .int,
            "temperature": .double,
            "thinking_enabled": .bool,
        ],
        "/chat": [
            "prompt": .string,
            "model_name": .string,
            "temperature": .double,
            "thinking_enabled": .bool,
            "max_tokens": .int,
        ],
        "/logs": [
            "source": .string,
            "limit": .int,
        ],
    ]
}
