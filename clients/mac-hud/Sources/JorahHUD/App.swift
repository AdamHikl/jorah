import AppKit
import Carbon.HIToolbox
import SwiftUI

/// Jorah HUD. Environment variables, used for build checks only:
///   JORAH_HUD_DEMO=1            show made-up data, clearly labelled, with no connection
///   JORAH_HUD_SNAPSHOT=<path>   with the demo: save a PNG of the window, then quit
/// The window does not open in a second copy of the app while one with the same
/// bundle identifier is running (seen on macOS 27.0.1), so quit the HUD before a demo run.
@main
struct JorahHUDApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var delegate
    @State private var model = AppState.model

    var body: some Scene {
        Window("Jorah", id: "hud") {
            HUDView()
                .environment(model)
        }
        .windowStyle(.hiddenTitleBar)
        .defaultSize(width: 1440, height: 900)
        .defaultLaunchBehavior(.presented)
        .restorationBehavior(.disabled)

        MenuBarExtra {
            Text(menuStatus)
            Divider()
            Button("Show or hide the HUD  (⌃⌥J)") { HotKey.toggle() }
            if !model.isDemo {
                Divider()
                // Drive mode (ADR 0012): only this click turns it on.
                if let until = model.driveUntil {
                    Text("Claude Code is driving until \(until.hudTime)")
                    Button("Stop Claude Code driving") { model.stopDrive(reason: "you clicked Stop") }
                } else {
                    Button("Let Claude Code drive (30 min)") { model.armDrive() }
                }
                if let error = model.driveError { Text(error) }
            }
            Divider()
            Button("Quit Jorah HUD") { NSApp.terminate(nil) }
        } label: {
            Image(systemName: model.phase == .connected ? "circle.hexagongrid.fill" : "circle.hexagongrid")
                .accessibilityLabel("Jorah HUD")
        }
    }

    private var menuStatus: String {
        if model.isDemo { return "Demo data, not connected" }
        switch model.phase {
        case .connected: return "Linked: \(model.orbState.rawValue.lowercased())"
        case .connecting: return "Connecting"
        case .pairingRequired: return "Waiting for your approval"
        case .idle: return "Not connected"
        case .failed: return "Link failed"
        }
    }
}

@MainActor
enum AppState {
    static let model = HUDModel()
}

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        NSApp.activate(ignoringOtherApps: true)
        HotKey.register()

        let environment = ProcessInfo.processInfo.environment
        let model = AppState.model
        if environment["JORAH_HUD_DEMO"] == "1" {
            model.isDemo = true
            DemoFeed.start(model)
            if let path = environment["JORAH_HUD_SNAPSHOT"], !path.isEmpty {
                DispatchQueue.main.asyncAfter(deadline: .now() + 4) {
                    Snapshot.save(to: path)
                    NSApp.terminate(nil)
                }
            }
        } else {
            model.startIfPaired()
            // Read-only: which lane the PC is on, for the ROUTE button. Skipped while paused.
            if model.pausedAt == nil { model.runBrain(.status) }
        }
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    func applicationWillTerminate(_ notification: Notification) {
        MainActor.assumeIsolated { AppState.model.stopDrive(reason: "the HUD quit") }
    }
}

/// A system-wide shortcut, Control-Option-J, to show or hide the HUD. Carbon hot keys need no permission.
enum HotKey {
    private static var reference: EventHotKeyRef?

    static func register() {
        var spec = EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed))
        InstallEventHandler(GetApplicationEventTarget(), { _, _, _ in
            DispatchQueue.main.async { HotKey.toggle() }
            return noErr
        }, 1, &spec, nil, nil)
        let id = EventHotKeyID(signature: OSType(0x4A_48_55_44), id: 1) // "JHUD"
        RegisterEventHotKey(UInt32(kVK_ANSI_J), UInt32(controlKey | optionKey), id,
                            GetApplicationEventTarget(), 0, &reference)
    }

    @MainActor
    static func toggle() {
        guard let window = NSApp.windows.first(where: { $0.identifier?.rawValue.contains("hud") == true })
            ?? NSApp.windows.first(where: { $0.canBecomeMain })
        else { return }
        if window.isVisible, NSApp.isActive {
            window.orderOut(nil)
        } else {
            window.makeKeyAndOrderFront(nil)
            NSApp.activate(ignoringOtherApps: true)
        }
    }
}

@MainActor
enum Snapshot {
    static func save(to path: String) {
        let candidates = NSApp.windows.filter { $0.contentView != nil && $0.frame.width > 600 }
        guard let window = candidates.max(by: { $0.frame.width < $1.frame.width }),
              let view = window.contentView,
              let rep = view.bitmapImageRepForCachingDisplay(in: view.bounds)
        else {
            let seen = NSApp.windows.map { "\($0.className) \($0.frame.size) visible=\($0.isVisible)" }
            FileHandle.standardError.write(Data("snapshot: no window. Windows: \(seen)\n".utf8))
            return
        }
        view.cacheDisplay(in: view.bounds, to: rep)
        guard let png = rep.representation(using: .png, properties: [:]) else { return }
        try? png.write(to: URL(fileURLWithPath: path))
    }
}
