import Foundation
import HUDCore

/// The kill switch. It runs `scripts/pc/jorah-power.sh`, copied into the app at build time,
/// which pauses or resumes Jorah on the PC over SSH with Adam's setup key.
/// Nothing here runs without Adam pressing the button and confirming.
final class PowerControl {
    enum Action: String {
        case pause, resume, status
    }

    private let script = BundledScript(resource: "jorah-power")

    var isRunning: Bool { script.isRunning }

    /// Runs the script. `onLine` and `onFinish` arrive on the main queue.
    func run(_ action: Action, backup: Bool = true,
             onLine: @escaping (String) -> Void,
             onFinish: @escaping (Bool) -> Void) {
        var arguments = [action.rawValue]
        if action == .pause, !backup { arguments.append("--no-backup") }
        script.run(arguments, onLine: onLine, onFinish: onFinish)
    }
}

/// The Max plan / API key switch (docs/adr/0009-hud-brain-switch.md). It runs
/// `scripts/pc/jorah-brain.sh`, copied into the app at build time, which runs the fixed
/// `brain-lane.sh` on the PC over SSH with Adam's setup key. A switch runs only from its button
/// in the switch sheet; the status reads change nothing.
final class BrainControl {
    enum Action {
        case status, probe, api, max

        var arguments: [String] {
            switch self {
            case .status: return ["status"]
            case .probe: return ["status", "--probe"]
            case .api: return ["api"]
            case .max: return ["max"]
            }
        }

        /// The lane a switch is meant to reach; nil for the reads.
        var target: BrainLane? {
            switch self {
            case .api: return .api
            case .max: return .max
            case .status, .probe: return nil
            }
        }
    }

    private let script = BundledScript(resource: "jorah-brain")

    var isRunning: Bool { script.isRunning }

    func run(_ action: Action,
             onLine: @escaping (String) -> Void,
             onFinish: @escaping (Bool) -> Void) {
        script.run(action.arguments, onLine: onLine, onFinish: onFinish)
    }
}
