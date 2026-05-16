import Foundation

struct ChatTranscriptMessage: Equatable, Identifiable, Sendable {
    let id: UUID
    let role: ChatTranscriptRole
    let content: String

    init(id: UUID = UUID(), role: ChatTranscriptRole, content: String) {
        self.id = id
        self.role = role
        self.content = content
    }
}

enum ChatTranscriptRole: String, Equatable, Sendable {
    case user
    case assistant
}
