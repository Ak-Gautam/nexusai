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
        .target(
            name: "NexusMacCore",
            path: "Sources/NexusMacCore"
        ),
        .executableTarget(
            name: "NexusMac",
            dependencies: ["NexusMacCore"],
            path: "Sources/NexusMac"
        ),
        .executableTarget(
            name: "NexusMacUnitTests",
            dependencies: ["NexusMacCore"],
            path: "Tests"
        ),
    ]
)
