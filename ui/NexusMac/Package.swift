// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "NexusMac",
    platforms: [
        .macOS(.v14),
    ],
    products: [
        .executable(name: "NexusMac", targets: ["NexusMac"]),
    ],
    targets: [
        .executableTarget(
            name: "NexusMac",
            path: "Sources"
        ),
    ]
)
