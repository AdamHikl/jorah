// mac-ear: Jorah's mic and speaker on the Mac, and nothing else.
// Sends mic audio to jorah-voice on the PC and plays what comes back. No third-party code.
import AVFoundation
import Foundation

let usage = """
usage: mac-ear --url ws://<pc>.<tailnet>.ts.net:43210 [--barge-in] [--max-minutes 30] [--no-mic] [--token-file path]

The token comes from the Keychain: service "jorah-voice", account "adam".
--barge-in   talk over Jorah to cut him off, with echo cancellation on
--no-mic     play sound only, for testing
"""

struct Options {
    var url: URL
    var bargeIn = false
    var noMic = false
    var maxMinutes = 30.0
    var tokenFile: String?
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

func parseOptions() -> Options {
    var url: URL?
    var options = Options(url: URL(string: "ws://localhost")!)
    var args = Array(CommandLine.arguments.dropFirst())
    while !args.isEmpty {
        let arg = args.removeFirst()
        switch arg {
        case "--url" where !args.isEmpty: url = URL(string: args.removeFirst())
        case "--barge-in": options.bargeIn = true
        case "--no-mic": options.noMic = true
        case "--max-minutes" where !args.isEmpty: options.maxMinutes = Double(args.removeFirst()) ?? 30
        case "--token-file" where !args.isEmpty: options.tokenFile = args.removeFirst()
        default: fail(usage)
        }
    }
    guard let found = url else { fail(usage) }
    options.url = found
    return options
}

// The audio and token are plain inside the WebSocket, so it may only run inside WireGuard or on this Mac.
func hostIsPrivateTunnel(_ url: URL) -> Bool {
    guard let host = url.host else { return false }
    if host == "localhost" || host == "127.0.0.1" || host.hasSuffix(".ts.net") { return true }
    let parts = host.split(separator: ".").compactMap { Int($0) }
    return parts.count == 4 && parts[0] == 100 && (64...127).contains(parts[1])
}

func readToken(_ options: Options) -> String {
    if let path = options.tokenFile {
        guard let text = try? String(contentsOfFile: path, encoding: .utf8) else { fail("Can't read \(path)") }
        return text.trimmingCharacters(in: .whitespacesAndNewlines)
    }
    let process = Process()
    process.executableURL = URL(fileURLWithPath: "/usr/bin/security")
    process.arguments = ["find-generic-password", "-s", "jorah-voice", "-a", "adam", "-w"]
    let pipe = Pipe()
    process.standardOutput = pipe
    process.standardError = FileHandle.nullDevice
    do { try process.run() } catch { fail("Can't run the security tool") }
    let data = pipe.fileHandleForReading.readDataToEndOfFile()
    process.waitUntilExit()
    guard process.terminationStatus == 0 else { fail("No jorah-voice token in the Keychain. See docs/runbooks/voice-on-pc.md") }
    return String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
}

final class Ear: NSObject, URLSessionWebSocketDelegate {
    private let options: Options
    private let token: String
    private let engine = AVAudioEngine()
    private let player = AVAudioPlayerNode()
    private var playFormat: AVAudioFormat?
    private var socket: URLSessionWebSocketTask!
    private var ready = false
    private var finished = false

    init(options: Options, token: String) {
        self.options = options
        self.token = token
    }

    func start() {
        let session = URLSession(configuration: .default, delegate: self, delegateQueue: nil)
        socket = session.webSocketTask(with: options.url)
        socket.resume()
        receive()
        DispatchQueue.main.asyncAfter(deadline: .now() + options.maxMinutes * 60) {
            self.shut("\(Int(self.options.maxMinutes)) minute limit")
        }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        let hello: [String: Any] = ["type": "hello", "token": token, "barge_in": options.bargeIn]
        sendJSON(hello)
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        switch closeCode.rawValue {
        case 4401: shut("the PC refused the token")
        case 4409: shut("another session is already open")
        default: shut("the PC closed the connection")
        }
    }

    // Before "ready" there is nothing to cut off, and the first message must stay the hello.
    func interrupt() {
        DispatchQueue.main.async {
            if self.ready { self.sendJSON(["type": "interrupt"]) }
        }
    }

    private func sendJSON(_ object: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: object) else { return }
        socket.send(.string(String(decoding: data, as: UTF8.self))) { _ in }
    }

    private func receive() {
        socket.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure:
                DispatchQueue.main.async { self.shut("connection lost") }
            case .success(.data(let data)):
                DispatchQueue.main.async { self.play(data) }
                self.receive()
            case .success(.string(let text)):
                DispatchQueue.main.async { self.handle(text) }
                self.receive()
            case .success:
                self.receive()
            }
        }
    }

    private func handle(_ text: String) {
        guard let data = text.data(using: .utf8),
              let message = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = message["type"] as? String else { return }
        switch type {
        case "ready":
            let rate = message["sample_rate"] as? Double ?? 24000
            startAudio(sampleRate: rate)
        case "heard":
            print("You:   \(message["text"] as? String ?? "")")
        case "reply":
            print("Jorah: \(message["text"] as? String ?? "")")
        case "cut":
            player.stop()
            player.play()
        case "closed":
            if let numbers = message["numbers"] as? [String: Any] { report(numbers) }
            shut(message["reason"] as? String ?? "session ended")
        default:
            break
        }
    }

    private func report(_ numbers: [String: Any]) {
        print("\nThis session, in seconds:")
        for name in ["transcribe", "first_token", "first_audio"] {
            guard let entry = numbers[name] as? [String: Any], let median = entry["median"] as? Double, let p90 = entry["p90"] as? Double else {
                print("  \(name): no samples")
                continue
            }
            print("  \(name): median \(String(format: "%.2f", median)), P90 \(String(format: "%.2f", p90)), \(entry["turns"] ?? 0) turns")
        }
    }

    private func startAudio(sampleRate: Double) {
        guard let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1) else {
            shut("can't set up audio")
            return
        }
        playFormat = format
        engine.attach(player)
        if options.bargeIn && !options.noMic {
            do { try engine.inputNode.setVoiceProcessingEnabled(true) } catch { shut("echo cancellation failed: \(error)"); return }
        }
        engine.connect(player, to: engine.mainMixerNode, format: format)
        if !options.noMic { installMicTap() }
        engine.prepare()
        do { try engine.start() } catch { shut("can't start audio: \(error)"); return }
        player.play()
        ready = true
        if options.noMic {
            print("Connected, with the mic off.")
        } else {
            print("\n● MIC OPEN. Talk to Jorah. Press Enter to cut him off. Say \"goodbye\" or Ctrl-C to close.\n")
        }
    }

    private func installMicTap() {
        let input = engine.inputNode
        let micFormat = input.outputFormat(forBus: 0)
        guard let target = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true),
              let converter = AVAudioConverter(from: micFormat, to: target) else {
            shut("can't convert the mic's audio")
            return
        }
        input.installTap(onBus: 0, bufferSize: 2048, format: micFormat) { [weak self] buffer, _ in
            guard let self else { return }
            let capacity = AVAudioFrameCount(Double(buffer.frameLength) * 16000 / micFormat.sampleRate) + 16
            guard let out = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: capacity) else { return }
            var fed = false
            var error: NSError?
            converter.convert(to: out, error: &error) { _, status in
                if fed { status.pointee = .noDataNow; return nil }
                fed = true
                status.pointee = .haveData
                return buffer
            }
            guard error == nil, out.frameLength > 0, let samples = out.int16ChannelData else { return }
            let data = Data(bytes: samples[0], count: Int(out.frameLength) * 2)
            self.socket.send(.data(data)) { _ in }
        }
    }

    private func play(_ data: Data) {
        guard let format = playFormat, data.count >= 2 else { return }
        let frames = AVAudioFrameCount(data.count / 2)
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames), let channel = buffer.floatChannelData else { return }
        buffer.frameLength = frames
        data.withUnsafeBytes { raw in
            let samples = raw.bindMemory(to: Int16.self)
            for index in 0..<Int(frames) { channel[0][index] = Float(samples[index]) / 32768 }
        }
        player.scheduleBuffer(buffer, completionHandler: nil)
    }

    func shut(_ reason: String) {
        DispatchQueue.main.async {
            guard !self.finished else { return }
            self.finished = true
            if !self.options.noMic { self.engine.inputNode.removeTap(onBus: 0) }
            self.engine.stop()
            self.socket.cancel(with: .normalClosure, reason: nil)
            print("\n○ MIC CLOSED (\(reason)).")
            exit(0)
        }
    }
}

setvbuf(stdout, nil, _IOLBF, 0)
let options = parseOptions()
guard hostIsPrivateTunnel(options.url) else {
    fail("Refusing \(options.url.host ?? "that host"): use the PC's .ts.net name or 100.x address, so audio stays inside the tailnet.")
}
let ear = Ear(options: options, token: readToken(options))

signal(SIGINT, SIG_IGN)
let interruptSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
interruptSource.setEventHandler { ear.shut("Ctrl-C") }
interruptSource.resume()

ear.start()
Thread.detachNewThread {
    while readLine() != nil { ear.interrupt() }
}
dispatchMain()
