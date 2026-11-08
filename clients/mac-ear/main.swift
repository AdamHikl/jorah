// mac-ear: Jorah's mic and speaker on the Mac, and nothing else.
// Sends mic audio to jorah-voice on the PC and plays what comes back. No third-party code.
import AppKit
import AVFoundation
import Foundation
import Speech

let usage = """
usage: mac-ear --url ws://<pc>.<tailnet>.ts.net:43211 [--barge-in] [--max-minutes 30] [--no-mic] [--token-file path] [--wake]

The token comes from the Keychain: service "jorah-voice", account "adam".
--barge-in   talk over Jorah to cut him off, with echo cancellation on
--no-mic     play sound only, for testing
--wake       wait on-device for "Jorah" or "hey Jorah" before opening the connection
"""

struct Options {
    var url: URL
    var bargeIn = false
    var noMic = false
    var wake = false
    var maxMinutes = 30.0
    var tokenFile: String?
}

func fail(_ message: String) -> Never {
    FileHandle.standardError.write(Data((message + "\n").utf8))
    exit(1)
}

let wakePhrases: Set<String> = ["jorah", "hey jorah", "jora", "jorra", "zora", "hey jora"]

func isWakePhrase(_ text: String) -> Bool {
    let cleaned = text.lowercased().filter { !$0.isPunctuation }
    let recent = Array(cleaned.split(whereSeparator: { $0.isWhitespace }).suffix(5).map(String.init))
    for i in recent.indices {
        if wakePhrases.contains(recent[i]) { return true }
        if i + 1 < recent.count && wakePhrases.contains("\(recent[i]) \(recent[i + 1])") { return true }
    }
    return false
}

func runWakeSelfTest() -> Never {
    let positives = [
        "jorah",
        "hey jorah",
        "Hey, Jorah!",
        "jorah what time is it",
        "and then jorah said",
        "hey jora can you help",
        "jora",
        "jorra please",
        "okay zora",
        "earlier words then hey jorah",
    ]
    let negatives = [
        "",
        "   ... !? ",
        "georgia is lovely",
        "and then jorah said one two three four five",
        "jorah one two three four five",
        "hey there how are you",
        "majora mask is a game",
        "jorahs coat is warm",
        "hello world",
        "Hey Jorah! One, two, three, four, five.",
    ]
    for sample in positives where !isWakePhrase(sample) {
        fail("wake self-test failed: expected true for \(sample.debugDescription)")
    }
    for sample in negatives where isWakePhrase(sample) {
        fail("wake self-test failed: expected false for \(sample.debugDescription)")
    }
    exit(0)
}

func parseOptions() -> Options {
    var url: URL?
    var options = Options(url: URL(string: "ws://localhost")!)
    var args = Array(CommandLine.arguments.dropFirst())
    while !args.isEmpty {
        let arg = args.removeFirst()
        switch arg {
        case "--self-test-wake": runWakeSelfTest()
        case "--url" where !args.isEmpty: url = URL(string: args.removeFirst())
        case "--barge-in": options.bargeIn = true
        case "--no-mic": options.noMic = true
        case "--wake": options.wake = true
        case "--max-minutes" where !args.isEmpty: options.maxMinutes = Double(args.removeFirst()) ?? 30
        case "--token-file" where !args.isEmpty: options.tokenFile = args.removeFirst()
        default: fail(usage)
        }
    }
    guard let found = url else { fail(usage) }
    if options.wake && options.noMic { fail("--wake and --no-mic cannot be used together") }
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
    guard process.terminationStatus == 0 else { fail("No jorah-voice token in the Keychain. See Voice from the Mac in docs/runbooks/jorah-on-pc.md") }
    return String(decoding: data, as: UTF8.self).trimmingCharacters(in: .whitespacesAndNewlines)
}

final class Ear: NSObject, URLSessionWebSocketDelegate {
    private let options: Options
    private let token: String
    private let onFinish: ((String, Bool) -> Void)?
    private let engine = AVAudioEngine()
    private let player = AVAudioPlayerNode()
    private var playFormat: AVAudioFormat?
    private var socket: URLSessionWebSocketTask!
    private var timeoutWork: DispatchWorkItem?
    private var tapInstalled = false
    private var ready = false
    private var finished = false

    init(options: Options, token: String, onFinish: ((String, Bool) -> Void)? = nil) {
        self.options = options
        self.token = token
        self.onFinish = onFinish
    }

    func start() {
        let session = URLSession(configuration: .default, delegate: self, delegateQueue: nil)
        socket = session.webSocketTask(with: options.url)
        socket.resume()
        receive()
        let timeout = DispatchWorkItem { [weak self] in
            guard let self else { return }
            self.shut("\(Int(self.options.maxMinutes)) minute limit")
        }
        timeoutWork = timeout
        DispatchQueue.main.asyncAfter(deadline: .now() + options.maxMinutes * 60, execute: timeout)
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        let hello: [String: Any] = ["type": "hello", "token": token, "barge_in": options.bargeIn]
        sendJSON(hello)
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        switch closeCode.rawValue {
        case 4401: shut("the PC refused the token", isError: true)
        case 4409: shut("another session is already open", isError: true)
        default: shut("the PC closed the connection", isError: !ready)
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
                DispatchQueue.main.async { self.shut("connection lost", isError: true) }
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
            shut("can't set up audio", isError: true)
            return
        }
        playFormat = format
        engine.attach(player)
        if options.bargeIn && !options.noMic {
            do { try engine.inputNode.setVoiceProcessingEnabled(true) } catch { shut("echo cancellation failed: \(error)", isError: true); return }
        }
        engine.connect(player, to: engine.mainMixerNode, format: format)
        if !options.noMic { installMicTap() }
        engine.prepare()
        do { try engine.start() } catch { shut("can't start audio: \(error)", isError: true); return }
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
            shut("can't convert the mic's audio", isError: true)
            return
        }
        installAudioTap(on: input, bufferSize: 2048, format: micFormat) { [weak self] buffer in
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
        tapInstalled = true
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

    func shut(_ reason: String, isError: Bool = false) {
        DispatchQueue.main.async {
            guard !self.finished else { return }
            self.finished = true
            self.timeoutWork?.cancel()
            self.timeoutWork = nil
            if self.tapInstalled {
                self.engine.inputNode.removeTap(onBus: 0)
                self.tapInstalled = false
            }
            self.engine.stop()
            self.socket.cancel(with: .normalClosure, reason: nil)
            print("\n○ MIC CLOSED (\(reason)).")
            if let onFinish = self.onFinish, reason != "Ctrl-C" {
                onFinish(reason, isError)
            } else {
                exit(0)
            }
        }
    }
}

func installAudioTap(on node: AVAudioNode, bufferSize: AVAudioFrameCount, format: AVAudioFormat, handler: @escaping (AVAudioPCMBuffer) -> Void) {
    node.installTap(onBus: 0, bufferSize: bufferSize, format: format) { buffer, _ in
        handler(buffer)
    }
}

// Listens on-device for "Jorah" / "hey Jorah" and never sends audio over the network.
final class WakeListener {
    private let recognizer: SFSpeechRecognizer
    private let onWake: () -> Void
    private let requestLock = NSLock()
    private var engine = AVAudioEngine()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var restartTimer: DispatchWorkItem?
    private var tapInstalled = false
    private var active = false
    private var generation = 0

    init(recognizer: SFSpeechRecognizer, onWake: @escaping () -> Void) {
        self.recognizer = recognizer
        self.onWake = onWake
    }

    func start() {
        guard !active else { return }
        active = true
        engine = AVAudioEngine()
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else {
            fail("No microphone input available for wake word listening.")
        }
        installAudioTap(on: input, bufferSize: 1024, format: format) { [weak self] buffer in
            guard let self else { return }
            self.requestLock.lock()
            let currentRequest = self.request
            self.requestLock.unlock()
            currentRequest?.append(buffer)
        }
        tapInstalled = true
        engine.prepare()
        do { try engine.start() } catch { fail("Can't start audio for wake word: \(error)") }
        print("○ waiting for \"Jorah\"")
        startTask()
    }

    func stop() {
        active = false
        generation += 1
        restartTimer?.cancel()
        restartTimer = nil
        requestLock.lock()
        let oldRequest = request
        request = nil
        requestLock.unlock()
        oldRequest?.endAudio()
        task?.cancel()
        task = nil
        if tapInstalled {
            engine.inputNode.removeTap(onBus: 0)
            tapInstalled = false
        }
        engine.stop()
    }

    // Apple's recognition tasks stop after about a minute; roll over every 50s or when one ends.
    private func startTask() {
        guard active else { return }
        guard recognizer.supportsOnDeviceRecognition else {
            stop()
            fail("On-device speech recognition is no longer available.")
        }
        generation += 1
        let currentGen = generation
        restartTimer?.cancel()

        requestLock.lock()
        let oldRequest = request
        let newRequest = SFSpeechAudioBufferRecognitionRequest()
        newRequest.requiresOnDeviceRecognition = true
        newRequest.shouldReportPartialResults = true
        request = newRequest
        requestLock.unlock()

        oldRequest?.endAudio()
        task?.cancel()

        let timer = DispatchWorkItem { [weak self] in
            guard let self, self.active, self.generation == currentGen else { return }
            self.startTask()
        }
        restartTimer = timer
        DispatchQueue.main.asyncAfter(deadline: .now() + 50, execute: timer)

        task = recognizer.recognitionTask(with: newRequest) { [weak self] result, error in
            DispatchQueue.main.async {
                guard let self, self.active, self.generation == currentGen else { return }
                if let text = result?.bestTranscription.formattedString, isWakePhrase(text) {
                    self.stop()
                    NSSound(named: NSSound.Name("Tink"))?.play()
                    print("● Jorah is listening")
                    self.onWake()
                    return
                }
                if error != nil {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
                        guard let self, self.active, self.generation == currentGen else { return }
                        self.startTask()
                    }
                } else if result?.isFinal == true {
                    self.startTask()
                }
            }
        }
    }
}

func requestOnDeviceRecognizer(then ready: @escaping (SFSpeechRecognizer) -> Void) {
    SFSpeechRecognizer.requestAuthorization { status in
        DispatchQueue.main.async {
            guard status == .authorized else {
                fail("Speech recognition permission denied (\(status.rawValue)): enable it in System Settings > Privacy & Security > Speech Recognition.")
            }
            guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")) else {
                fail("Can't create an en-US speech recognizer.")
            }
            guard recognizer.supportsOnDeviceRecognition else {
                fail("On-device en-US speech recognition is not supported on this Mac.")
            }
            ready(recognizer)
        }
    }
}

setvbuf(stdout, nil, _IOLBF, 0)
let options = parseOptions()
guard hostIsPrivateTunnel(options.url) else {
    fail("Refusing \(options.url.host ?? "that host"): use the PC's .ts.net name or 100.x address, so audio stays inside the tailnet.")
}
let token = readToken(options)
var currentEar: Ear?
var wakeListener: WakeListener?

signal(SIGINT, SIG_IGN)
let interruptSource = DispatchSource.makeSignalSource(signal: SIGINT, queue: .main)
interruptSource.setEventHandler {
    if let ear = currentEar {
        ear.shut("Ctrl-C")
    } else {
        wakeListener?.stop()
        print("\n○ MIC CLOSED (Ctrl-C).")
        exit(0)
    }
}
interruptSource.resume()

Thread.detachNewThread {
    while readLine() != nil {
        DispatchQueue.main.async { currentEar?.interrupt() }
    }
}

if options.wake {
    var consecutiveErrors = 0
    requestOnDeviceRecognizer { recognizer in
        let listener = WakeListener(recognizer: recognizer) {
            let ear = Ear(options: options, token: token) { reason, isError in
                currentEar = nil
                if isError {
                    consecutiveErrors += 1
                    if consecutiveErrors >= 3 {
                        fail("Giving up after \(consecutiveErrors) connection errors in a row: \(reason)")
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 5) {
                        wakeListener?.start()
                    }
                } else {
                    consecutiveErrors = 0
                    wakeListener?.start()
                }
            }
            currentEar = ear
            ear.start()
        }
        wakeListener = listener
        listener.start()
    }
} else {
    let ear = Ear(options: options, token: token)
    currentEar = ear
    ear.start()
}
dispatchMain()
