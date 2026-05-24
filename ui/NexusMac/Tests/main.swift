import Foundation
import NexusMacCore

enum TestFailure: Error, CustomStringConvertible {
    case failed(String)

    var description: String {
        switch self {
        case .failed(let message):
            return message
        }
    }
}

func expect(_ condition: @autoclosure () -> Bool, _ message: String) throws {
    if !condition() {
        throw TestFailure.failed(message)
    }
}

func testPlainInputBecomesChatPrompt() throws {
    let request = try CommandInputParser.parse("Hi")

    try expect(request.command == "/chat", "Expected plain input to route to /chat")
    try expect(request.arguments == ["prompt": .string("Hi")], "Expected prompt argument")
}

func testLogsCommandParsesTypedArguments() throws {
    let request = try CommandInputParser.parse("/logs source=backend limit=25")

    try expect(request.command == "/logs", "Expected /logs command")
    try expect(
        request.arguments == [
            "source": .string("backend"),
            "limit": .int(25),
        ],
        "Expected typed /logs arguments"
    )
}

func testChatCommandKeepsPromptText() throws {
    let request = try CommandInputParser.parse("/chat explain these files")

    try expect(request.command == "/chat", "Expected /chat command")
    try expect(
        request.arguments == ["prompt": .string("explain these files")],
        "Expected /chat prompt text"
    )
}

func testAssistantMessageUsesContent() throws {
    let payload = """
    {
      "runtime": {
        "loaded": true,
        "model_name": "model",
        "model_path": "/tmp/model.gguf",
        "server_url": "http://127.0.0.1:1234",
        "process_id": 123,
        "context_length": 8192,
        "temperature": 0.2,
        "thinking_enabled": false,
        "supports_thinking": true
      },
      "response": {
        "choices": [
          {
            "finish_reason": "stop",
            "message": {
              "role": "assistant",
              "content": " Hello "
            }
          }
        ]
      }
    }
    """.data(using: .utf8)!

    let result = try JSONDecoder().decode(ChatResult.self, from: payload)

    try expect(result.assistantMessage == "Hello", "Expected assistant content to be trimmed")
}

func testReasoningOnlyLengthResponseShowsDiagnostic() throws {
    let payload = """
    {
      "runtime": {
        "loaded": true,
        "model_name": "model",
        "model_path": "/tmp/model.gguf",
        "server_url": "http://127.0.0.1:1234",
        "process_id": 123,
        "context_length": 8192,
        "temperature": 0.2,
        "thinking_enabled": true,
        "supports_thinking": true
      },
      "response": {
        "choices": [
          {
            "finish_reason": "length",
            "message": {
              "role": "assistant",
              "content": "",
              "reasoning_content": "Thinking Process"
            }
          }
        ]
      }
    }
    """.data(using: .utf8)!

    let result = try JSONDecoder().decode(ChatResult.self, from: payload)

    try expect(result.assistantMessage.contains("response budget"), "Expected response budget diagnostic")
    try expect(result.assistantMessage.contains("thinking_enabled=false"), "Expected thinking setting diagnostic")
}

func testFrontendLoggerWritesReadableLines() throws {
    let logger = FrontendLogger.shared

    logger.info("unit_test_frontend_logger", metadata: ["suite": "NexusMacUnitTests"])
    let lines = logger.recentLines(limit: 20)

    try expect(
        lines.contains { line in
            line.contains("unit_test_frontend_logger") && line.contains("NexusMacUnitTests")
        },
        "Expected frontend logger line to be readable"
    )
}

let tests: [(String, () throws -> Void)] = [
    ("plain input routes to chat", testPlainInputBecomesChatPrompt),
    ("logs command parses arguments", testLogsCommandParsesTypedArguments),
    ("chat command keeps prompt text", testChatCommandKeepsPromptText),
    ("assistant message uses content", testAssistantMessageUsesContent),
    ("reasoning-only response shows diagnostic", testReasoningOnlyLengthResponseShowsDiagnostic),
    ("frontend logger writes readable lines", testFrontendLoggerWritesReadableLines),
]

do {
    for (name, test) in tests {
        try test()
        print("PASS \(name)")
    }
    print("Frontend unit tests passed: \(tests.count)")
} catch {
    print("FAIL \(error)")
    exit(1)
}
