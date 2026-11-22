import Foundation

/// Runs one of the shell scripts `just mac-hud` copies into the app, and hands back its output a
/// line at a time. The app holds no key: the scripts run `ssh`, which reads `~/.ssh` as it does in
/// Terminal. Callers pass only fixed words as arguments.
final class BundledScript {
    let resource: String

    init(resource: String) {
        self.resource = resource
    }

    var url: URL? {
        Bundle.main.url(forResource: resource, withExtension: "sh")
    }

    private var process: Process?

    var isRunning: Bool { process?.isRunning == true }

    /// `onLine` and `onFinish` arrive on the main queue. `onFinish` gets true for exit code 0.
    func run(_ arguments: [String],
             onLine: @escaping (String) -> Void,
             onFinish: @escaping (Bool) -> Void) {
        guard !isRunning else { return }
        guard let script = url else {
            onLine("FAILED: \(resource).sh is not in this build. Build with `just mac-hud`.")
            onFinish(false)
            return
        }
        let process = Process()
        process.executableURL = URL(fileURLWithPath: "/bin/bash")
        process.arguments = [script.path] + arguments
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
            onLine("FAILED: could not start \(resource).sh: \(error.localizedDescription)")
            onFinish(false)
        }
    }
}
