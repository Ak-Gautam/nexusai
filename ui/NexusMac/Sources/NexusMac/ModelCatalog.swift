import Foundation

struct ModelCatalog: Decodable, Equatable, Sendable {
    let artifacts: [ModelArtifact]
    let defaults: ModelRoleDefaults
}

struct ModelArtifact: Decodable, Equatable, Identifiable, Sendable {
    let name: String
    let path: String
    let launchPath: String
    let runtime: String
    let kind: String
    let supportsThinking: Bool
    let recommendedContextLength: Int

    var id: String { name }

    private enum CodingKeys: String, CodingKey {
        case name
        case path
        case launchPath = "launch_path"
        case runtime
        case kind
        case supportsThinking = "supports_thinking"
        case recommendedContextLength = "recommended_context_length"
    }
}

struct ModelRoleDefaults: Decodable, Equatable, Sendable {
    let router: String?
    let planner: String?
    let ocr: String?
    let vlm: String?
}
