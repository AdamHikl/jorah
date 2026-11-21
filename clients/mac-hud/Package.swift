// swift-tools-version: 6.0
import PackageDescription

// Jorah HUD: a native Mac dashboard for Jorah. No third-party dependencies.
let package = Package(
    name: "JorahHUD",
    platforms: [.macOS(.v15)],
    targets: [
        .executableTarget(
            name: "JorahHUD",
            path: "Sources/JorahHUD",
            swiftSettings: [.swiftLanguageMode(.v5)]
        )
    ]
)
