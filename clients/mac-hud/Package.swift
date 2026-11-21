// swift-tools-version: 6.0
import PackageDescription

// Jorah HUD: a native Mac dashboard for Jorah. No third-party dependencies.
// HUDCore holds the logic that has unit tests: parsing and checking approval cards.
let package = Package(
    name: "JorahHUD",
    platforms: [.macOS(.v15)],
    targets: [
        .target(
            name: "HUDCore",
            path: "Sources/HUDCore",
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
        .executableTarget(
            name: "JorahHUD",
            dependencies: ["HUDCore"],
            path: "Sources/JorahHUD",
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
        .testTarget(
            name: "HUDCoreTests",
            dependencies: ["HUDCore"],
            path: "Tests/HUDCoreTests",
            swiftSettings: [.swiftLanguageMode(.v5)]
        ),
    ]
)
