import Foundation

/// The kill switch. It runs `scripts/pc/jorah-power.sh`, copied into the app at build time,
/// which pauses or resumes Jorah on the PC over SSH with Adam's setup key.
/// The app holds no key: `ssh` reads it from `~/.ssh`, as it does in Terminal.
/// Nothing here runs without Adam pressing the button and confirming.
final class PowerControl {
    enum Action: String {
        case pause, resume, status
    }

    static var scriptURL: URL? {
        Bundle.main.url(forResource: "jorah-power", withExtension: "sh")
    }

    private var process: Process?

    var isRunning: Bool { process?.isRunning == true }

    /// Runs the script. `onLine` and `onFinish` arrive on the main queue.
    func run(_ action: Action, backup: Bool = true,
             onLine: @escaping (String) -> Void,
             onFinish: @escaping (Bool) -> Void) {
        guard !isRunning else { return }
        guard let script = Self.scriptURL else {
            onLine("FAILED: the power script is not in this build. Build with `just mac-hud`.")
            onFinish(false)
            return
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        var arguments = [script.path, action.rawValue]
        if action == .pause, !backup { arguments.append("--no-backup") }
        process.arguments = arguments
        let pipe = Pipe()
        process.standardOutput = pipe
        process.standardError = pipe
        process.standardInput = FileHandle.nullDevice

        var buffer = Data()
        pipe.fileHandleForReading.readabilityHandler = { handle in
            let chunk = handle.availableData
            guard !chunk.isEmpty else { return }
            DispatchQueue.main.async {
                buffer.append(chunk)
                while let newline = buffer.firstIndex(of: 0x0A) {
                    let line = String(decoding: buffer[buffer.startIndex..<newline], as: UTF8.self)
                    buffer.removeSubrange(buffer.startIndex...newline)
                    if !line.isEmpty { onLine(line) }
                }
            }
        }
        process.terminationHandler = { finished in
            pipe.fileHandleForReading.readabilityHandler = nil
            let rest = pipe.fileHandleForReading.readDataToEndOfFile()
            DispatchQueue.main.async {
                buffer.append(rest)
                let tail = String(decoding: buffer, as: UTF8.self)
                for line in tail.split(separator: "\n") where !line.isEmpty { onLine(String(line)) }
                self.process = nil
                onFinish(finished.terminationStatus == 0)
            }
        }
        do {
            try process.run()
            self.process = process
        } catch {
            onLine("FAILED: could not start the script: \(error.localizedDescription)")
            onFinish(false)
        }
    }
}
