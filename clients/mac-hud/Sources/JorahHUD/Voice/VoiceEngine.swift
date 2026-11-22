import AppKit
import AVFoundation
import Foundation
import HUDCore
import OSLog
import Speech

/// Jorah's mic and speaker inside the HUD. This is `clients/mac-ear` moved into the app:
/// the same wake phrases, the same `jorah-voice` wire protocol, the same Keychain token.
///
/// - Waiting for the wake word uses Apple's on-device recognition. No audio leaves the Mac.
/// - After the wake word, or a press of Talk, mic audio goes to `jorah-voice` on the PC
///   over the tailnet, and the PC's reply audio is played here.
/// - Voice never approves anything.
///
/// All callbacks arrive on the main queue.
final class VoiceEngine: NSObject, URLSessionWebSocketDelegate {
    enum State: Equatable {
        case off
        case waitingForWake
        case connecting
        case listening
        case thinking
        case speaking

        /// True while mic audio is being sent to the PC.
        var isSessionOpen: Bool { self == .listening || self == .thinking || self == .speaking || self == .connecting }
    }

    static let wakePhrases: Set<String> = ["jorah", "hey jorah", "jora", "jorra", "zora", "hey jora"]
    static let maxSessionSeconds = 30.0 * 60
    static let phraseTimeoutSeconds = 10.0

    var onState: ((State) -> Void)?
    var onLevel: ((Float) -> Void)?
    var onHeard: ((String) -> Void)?
    /// What the on-device recogniser hears while waiting for the wake word. Screen only.
    var onWakeHeard: ((String) -> Void)?
    var onReply: ((String) -> Void)?
    /// The whole of a long reply, of which only an overview was spoken.
    var onFullReply: ((String) -> Void)?
    var onCard: ((VoiceCard) -> Void)?
    var onCardClosed: ((String, String) -> Void)?
    var onPhraseStatus: ((PhraseStatus) -> Void)?
    var onPhraseError: ((String) -> Void)?
    var onPhraseUnknown: ((String?) -> Void)?
    var onError: ((String) -> Void)?

    private(set) var state: State = .off {
        didSet { if state != oldValue { onState?(state) } }
    }

    private var url: URL?
    private(set) var wakeEnabled = false
    private var consecutiveErrors = 0
    /// Turned off for the rest of this launch if the echo-cancelling audio unit will not start.
    /// Off, as in `mac-ear` without `--barge-in`: with Apple's voice processing on, the MacBook
    /// Pro's 3-channel mic reached the PC as silence (2026-11-19), so sessions closed unheard.
    /// Use headphones; talking over Jorah needs this, and stays off until that is solved.
    private var echoCancellation = false

    // Session
    private var socket: URLSessionWebSocketTask?
    private var session: URLSession?
    private var engine: AVAudioEngine?
    private var player: AVAudioPlayerNode?
    private var playFormat: AVAudioFormat?
    private var tapInstalled = false
    private var ready = false
    private var serverReady = false
    private var sessionGeneration = 0
    private var timeoutWork: DispatchWorkItem?
    private var settingsConnection: SettingsConnection?
    private var sessionPhrasePending = false
    private var pendingSessionPhrasePayload: [String: Any]?
    private var sessionPhraseTimeout: DispatchWorkItem?
    /// Without echo cancellation, the mic sends silence while Jorah's speech is still playing here.
    /// The PC can say "listening" seconds before the Mac has played everything it was sent, and
    /// the open mic then hands Jorah his own last words as Adam's next turn (2026-11-20).
    private let speechGate = SpeechGate()
    /// Room echo after the last sample has played.
    static let speechTailSeconds = 0.5

    // Wake word
    private var recognizer: SFSpeechRecognizer?
    private var wakeEngine: AVAudioEngine?
    private let requestLock = NSLock()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var restartTimer: DispatchWorkItem?
    private var wakeTapInstalled = false
    private var wakeActive = false
    private var wakeGeneration = 0
    private var lastWakeError = ""
    // Read and written on the audio thread only.
    private var wakePeak: Float = 0
    private var wakeLevelLoggedAt = Date()
    private static let log = Logger(subsystem: "dev.jorah.hud", category: "wake")

    /// Averages every input channel into one, so the recogniser gets ordinary mono audio.
    static func mixToMono(_ buffer: AVAudioPCMBuffer, format: AVAudioFormat) -> AVAudioPCMBuffer? {
        let frames = Int(buffer.frameLength)
        let channels = Int(buffer.format.channelCount)
        guard frames > 0, channels > 0, let src = buffer.floatChannelData,
              let out = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: buffer.frameLength),
              let dst = out.floatChannelData?[0] else { return nil }
        out.frameLength = buffer.frameLength
        let stride = buffer.format.isInterleaved ? channels : 1
        let scale = 1 / Float(channels)
        for frame in 0..<frames {
            var sum: Float = 0
            for channel in 0..<channels {
                sum += buffer.format.isInterleaved ? src[0][frame * stride + channel] : src[channel][frame]
            }
            dst[frame] = sum * scale
        }
        return out
    }

    /// Logs the loudest sample every 5 s while waiting: a number only, never audio or words.
    private func logWakeLevel(_ buffer: AVAudioPCMBuffer) {
        guard let data = buffer.floatChannelData?[0] else { return }
        for index in 0..<Int(buffer.frameLength) { wakePeak = max(wakePeak, abs(data[index])) }
        if Date().timeIntervalSince(wakeLevelLoggedAt) >= 5 {
            Self.log.info("wake mic peak \(String(format: "%.4f", self.wakePeak), privacy: .public)")
            wakePeak = 0
            wakeLevelLoggedAt = Date()
        }
    }

    /// Cancelled tasks and "no speech yet" are normal while waiting; anything else is worth saying.
    static func isRoutineWakeError(_ error: NSError) -> Bool {
        error.domain == "kAFAssistantErrorDomain" && [216, 301, 1110].contains(error.code)
    }

    static func isWakePhrase(_ text: String) -> Bool {
        let cleaned = text.lowercased().filter { !$0.isPunctuation }
        let recent = Array(cleaned.split(whereSeparator: { $0.isWhitespace }).suffix(5).map(String.init))
        for i in recent.indices {
            if wakePhrases.contains(recent[i]) { return true }
            if i + 1 < recent.count && wakePhrases.contains("\(recent[i]) \(recent[i + 1])") { return true }
        }
        return false
    }

    /// The audio and token are plain inside the WebSocket, so it may only run inside the tailnet or on this Mac.
    static func hostIsPrivateTunnel(_ url: URL) -> Bool {
        guard let host = url.host else { return false }
        if host == "localhost" || host == "127.0.0.1" || host.hasSuffix(".ts.net") { return true }
        let parts = host.split(separator: ".").compactMap { Int($0) }
        return parts.count == 4 && parts[0] == 100 && (64...127).contains(parts[1])
    }

    // MARK: - Public controls

    func configure(url: URL?) { self.url = url }

    /// Turns wake-word listening on or off. It only listens while no session is open.
    func setWake(_ enabled: Bool) {
        wakeEnabled = enabled
        consecutiveErrors = 0
        if enabled {
            if state == .off { startWakeListening() }
        } else {
            stopWakeListening()
            if state == .waitingForWake { state = .off }
        }
    }

    private enum CredentialsResult {
        case ok(url: URL, token: String)
        case badURL
        case missingToken
    }

    private func readCredentials() -> CredentialsResult {
        guard let url, Self.hostIsPrivateTunnel(url) else { return .badURL }
        guard let token = Keychain.read("adam", service: "jorah-voice").flatMap({ String(data: $0, encoding: .utf8) })?
            .trimmingCharacters(in: .whitespacesAndNewlines), !token.isEmpty
        else { return .missingToken }
        return .ok(url: url, token: token)
    }

    /// Opens a voice session now, without the wake word.
    func startSession() {
        guard !state.isSessionOpen else { return }
        let url: URL
        let token: String
        switch readCredentials() {
        case .badURL:
            wakeEnabled = false
            onError?("The voice address must be the PC's .ts.net name or 100.x address, so audio stays inside the tailnet.")
            return
        case .missingToken:
            wakeEnabled = false
            onError?("No jorah-voice token in the Keychain. See \"Voice from the Mac\" in docs/runbooks/jorah-on-pc.md.")
            return
        case .ok(let validURL, let validToken):
            url = validURL
            token = validToken
        }
        stopWakeListening()
        state = .connecting
        AVCaptureDevice.requestAccess(for: .audio) { [weak self] granted in
            DispatchQueue.main.async {
                guard let self, self.state == .connecting else { return }
                guard granted else {
                    self.finishSession("Microphone access is off. Turn it on in System Settings, Privacy & Security, Microphone.", isError: true)
                    return
                }
                self.openSocket(url: url, token: token)
            }
        }
    }

    func endSession() {
        guard state.isSessionOpen else { return }
        finishSession("ended here", isError: false)
    }

    /// Cuts Jorah off mid-sentence.
    func interrupt() {
        guard ready else { return }
        sendJSON(["type": "interrupt"])
    }

    /// Sends a deliberate click's decision for a voice approval card over the active voice socket.
    @discardableResult
    func sendCardDecision(id: String, decision: String) -> Bool {
        guard state.isSessionOpen, ready, socket != nil,
              let payload = VoiceMessageEncoding.cardDecision(id: id, decision: decision)
        else { return false }
        sendJSON(payload)
        return true
    }

    /// Asks the PC for the current confirmation-phrase status.
    func requestPhraseStatus() {
        sendPhraseRequest(VoiceMessageEncoding.phraseStatusRequest())
    }

    /// Sets or changes the confirmation phrase on the PC. Never stored or logged here.
    func setPhrase(_ phrase: String) {
        guard let payload = VoiceMessageEncoding.phraseSet(phrase: phrase) else { return }
        sendPhraseRequest(payload)
    }

    /// Clears the confirmation phrase on the PC.
    func clearPhrase() {
        sendPhraseRequest(VoiceMessageEncoding.phraseClear())
    }

    private func sendPhraseRequest(_ payload: [String: Any]) {
        if state.isSessionOpen {
            settingsConnection?.cancel()
            settingsConnection = nil
            startSessionPhraseTimeout()
            if serverReady, socket != nil {
                sendJSON(payload)
            } else {
                pendingSessionPhrasePayload = payload
            }
            return
        }

        let url: URL
        let token: String
        switch readCredentials() {
        case .badURL:
            onPhraseUnknown?("The voice address must be the PC's .ts.net name or 100.x address, so audio stays inside the tailnet.")
            return
        case .missingToken:
            onPhraseUnknown?("No jorah-voice token in the Keychain. See \"Voice from the Mac\" in docs/runbooks/jorah-on-pc.md.")
            return
        case .ok(let validURL, let validToken):
            url = validURL
            token = validToken
        }

        settingsConnection?.cancel()
        let connection = SettingsConnection(
            url: url,
            token: token,
            payload: payload,
            timeoutSeconds: Self.phraseTimeoutSeconds
        ) { [weak self] outcome in
            guard let self else { return }
            self.settingsConnection = nil
            switch outcome {
            case .status(let status):
                self.onPhraseStatus?(status)
            case .error(let reason):
                self.onPhraseError?(reason)
            case .unknown(let reason):
                self.onPhraseUnknown?(reason)
            }
        }
        settingsConnection = connection
        connection.start()
    }

    private func startSessionPhraseTimeout() {
        sessionPhraseTimeout?.cancel()
        sessionPhrasePending = true
        let generation = sessionGeneration
        let work = DispatchWorkItem { [weak self] in
            guard let self, generation == self.sessionGeneration, self.sessionPhrasePending else { return }
            self.sessionPhrasePending = false
            self.pendingSessionPhrasePayload = nil
            self.sessionPhraseTimeout = nil
            self.onPhraseUnknown?("No reply from the PC within 10 seconds.")
        }
        sessionPhraseTimeout = work
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.phraseTimeoutSeconds, execute: work)
    }

    private func clearSessionPhraseTimeout() {
        sessionPhrasePending = false
        pendingSessionPhrasePayload = nil
        sessionPhraseTimeout?.cancel()
        sessionPhraseTimeout = nil
    }

    // MARK: - Session

    private func openSocket(url: URL, token: String) {
        sessionGeneration += 1
        let generation = sessionGeneration
        ready = false
        serverReady = false
        let session = URLSession(configuration: .ephemeral, delegate: self, delegateQueue: nil)
        self.session = session
        let socket = session.webSocketTask(with: url)
        self.socket = socket
        // Talking over Jorah needs echo cancellation, or he would hear himself and stop.
        pendingHello = ["type": "hello", "token": token, "barge_in": echoCancellation, "follow_up": wakeEnabled]
        socket.resume()
        receive(socket, generation)
        let timeout = DispatchWorkItem { [weak self] in
            guard let self, generation == self.sessionGeneration else { return }
            self.finishSession("30 minute limit", isError: false)
        }
        timeoutWork = timeout
        DispatchQueue.main.asyncAfter(deadline: .now() + Self.maxSessionSeconds, execute: timeout)
    }

    private var pendingHello: [String: Any]?

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        DispatchQueue.main.async {
            guard webSocketTask === self.socket, let hello = self.pendingHello else { return }
            self.pendingHello = nil
            self.sendJSON(hello)
        }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                    didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        DispatchQueue.main.async {
            guard webSocketTask === self.socket else { return }
            switch closeCode.rawValue {
            case 4401: self.finishSession("The PC refused the voice token.", isError: true)
            case 4409: self.finishSession("Another voice session is already open.", isError: true)
            default: self.finishSession("The PC closed the voice connection.", isError: !self.ready)
            }
        }
    }

    private func sendJSON(_ object: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: object) else { return }
        socket?.send(.string(String(decoding: data, as: UTF8.self))) { _ in }
    }

    private func receive(_ socket: URLSessionWebSocketTask, _ generation: Int) {
        socket.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure:
                DispatchQueue.main.async {
                    guard generation == self.sessionGeneration, self.state.isSessionOpen else { return }
                    self.finishSession("The voice connection was lost.", isError: true)
                }
            case .success(.data(let data)):
                DispatchQueue.main.async {
                    guard generation == self.sessionGeneration else { return }
                    self.play(data)
                }
                self.receive(socket, generation)
            case .success(.string(let text)):
                DispatchQueue.main.async {
                    guard generation == self.sessionGeneration else { return }
                    self.handle(text)
                }
                self.receive(socket, generation)
            case .success:
                self.receive(socket, generation)
            }
        }
    }

    private func handle(_ text: String) {
        guard let data = text.data(using: .utf8),
              let message = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = message["type"] as? String else { return }
        switch type {
        case "ready":
            serverReady = true
            if let pending = pendingSessionPhrasePayload {
                pendingSessionPhrasePayload = nil
                sendJSON(pending)
            }
            startAudio(sampleRate: message["sample_rate"] as? Double ?? 24000)
        case "state":
            switch message["state"] as? String {
            case "listening":
                state = .listening
                let left = speechGate.secondsLeft()
                if left > 0.05 {
                    Self.log.info("PC said listening with \(String(format: "%.2f", left), privacy: .public) s of speech still to play here")
                }
            case "thinking": state = .thinking
            case "speaking": state = .speaking
            default: break
            }
        case "heard":
            onHeard?(message["text"] as? String ?? "")
        case "reply":
            onReply?(message["text"] as? String ?? "")
        case "full_reply":
            // A long reply: only an overview is spoken, and the whole message shows here.
            if let text = message["text"] as? String, !text.isEmpty { onFullReply?(text) }
        case "cut":
            player?.stop()
            player?.play()
            speechGate.stopped()
        case "closed":
            finishSession(message["reason"] as? String ?? "session ended", isError: false)
        default:
            switch VoiceMessageParsing.parse(text) {
            case .card(let card):
                onCard?(card)
            case .cardClosed(let id, let outcome):
                onCardClosed?(id, outcome)
            case .phraseStatus(let status):
                clearSessionPhraseTimeout()
                onPhraseStatus?(status)
            case .phraseError(let reason):
                clearSessionPhraseTimeout()
                onPhraseError?(reason)
            case .ready, .unknown, .none:
                break
            }
        }
    }

    /// Starts the mic and speaker. The echo-cancelling audio unit can fail to initialise
    /// (error -10875) when the wake listener has only just let go of the microphone, so this
    /// tries three times, a little apart. If it still fails, the session is reopened without
    /// echo cancellation, and without talking over Jorah, which needs it.
    private func startAudio(sampleRate: Double, attempt: Int = 1) {
        guard let format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1) else {
            finishSession("Can't set up audio.", isError: true)
            return
        }
        let generation = sessionGeneration
        let engine = AVAudioEngine()
        let player = AVAudioPlayerNode()
        self.engine = engine
        self.player = player
        playFormat = format
        engine.attach(player)

        var failure: String?
        if echoCancellation {
            do { try engine.inputNode.setVoiceProcessingEnabled(true) } catch {
                failure = "echo cancellation: \(error.localizedDescription)"
            }
        }
        if failure == nil {
            engine.connect(player, to: engine.mainMixerNode, format: format)
            guard installMicTap(engine) else { return }
            engine.prepare()
            do { try engine.start() } catch {
                failure = error.localizedDescription
            }
        }

        if let failure {
            if tapInstalled {
                engine.inputNode.removeTap(onBus: 0)
                tapInstalled = false
            }
            engine.stop()
            self.engine = nil
            self.player = nil
            if attempt < 3 {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.4 * Double(attempt)) { [weak self] in
                    guard let self, generation == self.sessionGeneration, self.state.isSessionOpen else { return }
                    self.startAudio(sampleRate: sampleRate, attempt: attempt + 1)
                }
            } else if echoCancellation {
                echoCancellation = false
                onError?("Echo cancellation would not start (\(failure)). Carrying on without it: use headphones, and talking over Jorah is off until the HUD restarts.")
                reopenSession()
            } else {
                finishSession("Can't start audio: \(failure)", isError: true)
            }
            return
        }

        player.play()
        speechGate.reset()
        ready = true
        consecutiveErrors = 0
        state = .listening
    }

    /// Closes the socket and opens a new session at once, keeping the wake listener out of the way.
    private func reopenSession() {
        sessionGeneration += 1
        timeoutWork?.cancel()
        timeoutWork = nil
        ready = false
        serverReady = false
        if sessionPhrasePending {
            clearSessionPhraseTimeout()
            onPhraseUnknown?("The voice connection reopened before replying.")
        }
        pendingHello = nil
        socket?.cancel(with: .normalClosure, reason: nil)
        socket = nil
        session?.invalidateAndCancel()
        session = nil
        state = .off
        startSession()
    }

    private func installMicTap(_ engine: AVAudioEngine) -> Bool {
        let input = engine.inputNode
        let micFormat = input.outputFormat(forBus: 0)
        guard micFormat.sampleRate > 0, micFormat.channelCount > 0,
              let target = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true),
              let converter = AVAudioConverter(from: micFormat, to: target)
        else {
            finishSession("Can't read the microphone.", isError: true)
            return false
        }
        let socket = self.socket
        // Talking over Jorah needs the mic open while he speaks, and echo cancellation to allow it.
        let gate = echoCancellation ? nil : speechGate
        let tail = Self.speechTailSeconds
        Self.log.info("session mic \(micFormat.channelCount, privacy: .public) ch \(Int(micFormat.sampleRate), privacy: .public) Hz, echo cancellation \(self.echoCancellation, privacy: .public)")
        input.installTap(onBus: 0, bufferSize: 2048, format: micFormat) { [weak self] buffer, _ in
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
            let count = Int(out.frameLength)
            if gate?.isHeld(tail: tail) == true {
                // Same length, so the PC's sense of how long it has been quiet stays right.
                socket?.send(.data(Data(count: count * 2))) { _ in }
                return
            }
            let data = Data(bytes: samples[0], count: count * 2)
            socket?.send(.data(data)) { _ in }
            let level = Self.level(samples[0], count: count)
            DispatchQueue.main.async {
                self?.onLevel?(level)
                self?.logSessionLevel(level)
            }
        }
        tapInstalled = true
        return true
    }

    private var sessionPeak: Float = 0
    private var sessionLevelLoggedAt = Date()

    /// The loudest mic level sent to the PC, every 3 s: a number only, never audio or words.
    private func logSessionLevel(_ level: Float) {
        sessionPeak = max(sessionPeak, level)
        if Date().timeIntervalSince(sessionLevelLoggedAt) >= 3 {
            Self.log.info("session mic level \(String(format: "%.3f", self.sessionPeak), privacy: .public)")
            sessionPeak = 0
            sessionLevelLoggedAt = Date()
        }
    }

    private func play(_ data: Data) {
        guard let format = playFormat, let player, data.count >= 2 else { return }
        let frames = AVAudioFrameCount(data.count / 2)
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: frames),
              let channel = buffer.floatChannelData else { return }
        buffer.frameLength = frames
        var level: Float = 0
        data.withUnsafeBytes { raw in
            let samples = raw.bindMemory(to: Int16.self)
            for index in 0..<Int(frames) { channel[0][index] = Float(samples[index]) / 32768 }
            if let base = samples.baseAddress { level = Self.level(base, count: Int(frames)) }
        }
        player.scheduleBuffer(buffer, completionHandler: nil)
        speechGate.queued(seconds: Double(frames) / format.sampleRate)
        onLevel?(level)
    }

    /// Loudness from 0 to 1, for the orb only.
    private static func level(_ samples: UnsafePointer<Int16>, count: Int) -> Float {
        guard count > 0 else { return 0 }
        var sum: Float = 0
        var index = 0
        while index < count {
            let value = Float(samples[index]) / 32768
            sum += value * value
            index += 4
        }
        let rms = (sum / Float((count + 3) / 4)).squareRoot()
        return min(1, rms * 6)
    }

    private func finishSession(_ reason: String, isError: Bool) {
        guard state.isSessionOpen else { return }
        Self.log.info("session ended: \(reason, privacy: .public)")
        sessionGeneration += 1
        timeoutWork?.cancel()
        timeoutWork = nil
        if tapInstalled {
            engine?.inputNode.removeTap(onBus: 0)
            tapInstalled = false
        }
        engine?.stop()
        engine = nil
        player = nil
        ready = false
        serverReady = false
        if sessionPhrasePending {
            clearSessionPhraseTimeout()
            onPhraseUnknown?("The voice connection closed before replying.")
        }
        pendingHello = nil
        socket?.cancel(with: .normalClosure, reason: nil)
        socket = nil
        session?.invalidateAndCancel()
        session = nil
        state = .off
        onLevel?(0)

        if isError {
            onError?(reason)
            consecutiveErrors += 1
        } else {
            consecutiveErrors = 0
        }
        guard wakeEnabled else { return }
        if consecutiveErrors >= 3 {
            wakeEnabled = false
            onError?("Wake word turned off after 3 voice errors in a row. Last: \(reason)")
            return
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + (isError ? 5 : 0.3)) { [weak self] in
            guard let self, self.wakeEnabled, self.state == .off else { return }
            self.startWakeListening()
        }
    }

    // MARK: - Wake word (on this Mac only)

    private func startWakeListening() {
        AVCaptureDevice.requestAccess(for: .audio) { [weak self] micGranted in
            SFSpeechRecognizer.requestAuthorization { status in
                DispatchQueue.main.async {
                    guard let self, self.wakeEnabled, self.state == .off else { return }
                    guard micGranted else { return self.wakeFailed("Microphone access is off. Turn it on in System Settings, Privacy & Security, Microphone.") }
                    guard status == .authorized else { return self.wakeFailed("Speech Recognition access is off. Turn it on in System Settings, Privacy & Security, Speech Recognition.") }
                    guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")),
                          recognizer.supportsOnDeviceRecognition
                    else { return self.wakeFailed("On-device English speech recognition is not available on this Mac.") }
                    self.recognizer = recognizer
                    self.beginWake()
                }
            }
        }
    }

    private func wakeFailed(_ message: String) {
        wakeEnabled = false
        state = .off
        onError?(message)
    }

    private func beginWake() {
        guard !wakeActive else { return }
        let engine = AVAudioEngine()
        let input = engine.inputNode
        let format = input.outputFormat(forBus: 0)
        guard format.sampleRate > 0, format.channelCount > 0 else {
            return wakeFailed("No microphone input is available for the wake word.")
        }
        // The MacBook Pro's built-in mic arrives as 3 raw channels. Apple's recogniser returns
        // nothing for that, so mix down to one channel before it sees the audio.
        guard let mono = AVAudioFormat(commonFormat: .pcmFormatFloat32, sampleRate: format.sampleRate,
                                       channels: 1, interleaved: false) else {
            return wakeFailed("Can't set up audio for the wake word.")
        }
        wakePeak = 0
        wakeLevelLoggedAt = Date()
        input.installTap(onBus: 0, bufferSize: 1024, format: format) { [weak self] buffer, _ in
            guard let self, let out = Self.mixToMono(buffer, format: mono) else { return }
            self.requestLock.lock()
            let current = self.request
            self.requestLock.unlock()
            current?.append(out)
            self.logWakeLevel(out)
        }
        wakeTapInstalled = true
        engine.prepare()
        do { try engine.start() } catch {
            input.removeTap(onBus: 0)
            wakeTapInstalled = false
            return wakeFailed("Can't start audio for the wake word: \(error.localizedDescription)")
        }
        wakeEngine = engine
        wakeActive = true
        state = .waitingForWake
        startWakeTask()
    }

    private func stopWakeListening() {
        wakeActive = false
        wakeGeneration += 1
        restartTimer?.cancel()
        restartTimer = nil
        requestLock.lock()
        let old = request
        request = nil
        requestLock.unlock()
        old?.endAudio()
        task?.cancel()
        task = nil
        if wakeTapInstalled {
            wakeEngine?.inputNode.removeTap(onBus: 0)
            wakeTapInstalled = false
        }
        wakeEngine?.stop()
        wakeEngine = nil
    }

    /// Apple's recognition tasks stop after about a minute, so roll over every 50 s or when one ends.
    private func startWakeTask() {
        guard wakeActive, let recognizer else { return }
        guard recognizer.supportsOnDeviceRecognition else {
            stopWakeListening()
            return wakeFailed("On-device speech recognition is no longer available.")
        }
        wakeGeneration += 1
        let generation = wakeGeneration
        restartTimer?.cancel()

        requestLock.lock()
        let old = request
        let new = SFSpeechAudioBufferRecognitionRequest()
        new.requiresOnDeviceRecognition = true
        new.shouldReportPartialResults = true
        // An unusual name: tell the recogniser to expect it (the mac-ear fix of 0fada79).
        new.contextualStrings = ["Jorah", "hey Jorah"]
        request = new
        requestLock.unlock()
        old?.endAudio()
        task?.cancel()

        let timer = DispatchWorkItem { [weak self] in
            guard let self, self.wakeActive, self.wakeGeneration == generation else { return }
            self.startWakeTask()
        }
        restartTimer = timer
        DispatchQueue.main.asyncAfter(deadline: .now() + 50, execute: timer)

        task = recognizer.recognitionTask(with: new) { [weak self] result, error in
            DispatchQueue.main.async {
                guard let self, self.wakeActive, self.wakeGeneration == generation else { return }
                if let error {
                    let ns = error as NSError
                    Self.log.info("wake task error \(ns.domain, privacy: .public) \(ns.code, privacy: .public)")
                }
                if let text = result?.bestTranscription.formattedString, !text.isEmpty {
                    // A word count and the wake decision only; the words stay private.
                    Self.log.info("wake heard \(text.split(separator: " ").count, privacy: .public) words, wake=\(Self.isWakePhrase(text), privacy: .public)")
                    // On screen only, never stored or sent: shows whether the name is being caught.
                    self.onWakeHeard?(text.split(separator: " ").suffix(6).joined(separator: " "))
                }
                if let text = result?.bestTranscription.formattedString, Self.isWakePhrase(text) {
                    self.lastWakeError = ""
                    self.stopWakeListening()
                    self.state = .off
                    NSSound(named: NSSound.Name("Tink"))?.play()
                    self.startSession()
                    return
                }
                if let error {
                    // Say why once (for example Dictation off, or no permission); the same
                    // reason repeating, or a normal end-of-task error, stays quiet.
                    let ns = error as NSError
                    let reason = "\(error.localizedDescription) [\(ns.domain) \(ns.code)]"
                    if reason != self.lastWakeError && !Self.isRoutineWakeError(ns) {
                        self.lastWakeError = reason
                        self.onError?("Wake word recognition stopped: \(reason). Retrying.")
                    }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { [weak self] in
                        guard let self, self.wakeActive, self.wakeGeneration == generation else { return }
                        self.startWakeTask()
                    }
                } else if result?.isFinal == true {
                    self.startWakeTask()
                }
            }
        }
    }
}

/// When the speech queued in the player will have finished playing on this Mac. Written on the
/// main queue as audio arrives from the PC, read on the mic's audio thread.
final class SpeechGate: @unchecked Sendable {
    private let lock = NSLock()
    /// `ProcessInfo.systemUptime` at which the last queued sample plays. 0 when nothing was queued.
    private var playsUntil: TimeInterval = 0

    private static var now: TimeInterval { ProcessInfo.processInfo.systemUptime }

    /// Audio was queued. If the player had run dry, it starts playing now.
    func queued(seconds: Double) {
        lock.withLock { playsUntil = max(playsUntil, Self.now) + seconds }
    }

    /// The player was stopped and its queue dropped, so speech ends now; the room tail still applies.
    func stopped() {
        lock.withLock { playsUntil = Self.now }
    }

    /// A new session: nothing queued, the mic is open.
    func reset() {
        lock.withLock { playsUntil = 0 }
    }

    /// True while queued speech is playing, or ended less than `tail` seconds ago.
    func isHeld(tail: Double) -> Bool {
        lock.withLock { playsUntil > 0 && Self.now < playsUntil + tail }
    }

    func secondsLeft() -> Double {
        lock.withLock { max(0, playsUntil - Self.now) }
    }
}

/// Short-lived WebSocket used only to read or update the confirmation phrase when no voice
/// session is open (`"purpose":"settings"`). Never starts audio, mic or wake listening.
private final class SettingsConnection: NSObject, URLSessionWebSocketDelegate, URLSessionTaskDelegate {
    enum Outcome {
        case status(PhraseStatus)
        case error(String)
        case unknown(String?)
    }

    private let url: URL
    private var token: String
    private var payload: [String: Any]
    private let timeoutSeconds: TimeInterval
    private var completion: ((Outcome) -> Void)?

    private var session: URLSession?
    private var socket: URLSessionWebSocketTask?
    private var timeoutWork: DispatchWorkItem?
    private var sentPayload = false
    private var finished = false

    init(
        url: URL,
        token: String,
        payload: [String: Any],
        timeoutSeconds: TimeInterval,
        completion: @escaping (Outcome) -> Void
    ) {
        self.url = url
        self.token = token
        self.payload = payload
        self.timeoutSeconds = timeoutSeconds
        self.completion = completion
    }

    func start() {
        let session = URLSession(configuration: .ephemeral, delegate: self, delegateQueue: nil)
        self.session = session
        let socket = session.webSocketTask(with: url)
        self.socket = socket

        let work = DispatchWorkItem { [weak self] in
            self?.finish(.unknown("No reply from the PC within 10 seconds."))
        }
        timeoutWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + timeoutSeconds, execute: work)

        socket.resume()
        receive(socket)
    }

    func cancel() {
        guard !finished else { return }
        finished = true
        completion = nil
        cleanup()
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        DispatchQueue.main.async {
            guard !self.finished, webSocketTask === self.socket else { return }
            guard let hello = VoiceMessageEncoding.settingsHello(token: self.token) else {
                self.finish(.unknown("No jorah-voice token in the Keychain."))
                return
            }
            self.token = ""
            self.sendJSON(hello)
        }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                    didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        DispatchQueue.main.async {
            guard !self.finished, webSocketTask === self.socket else { return }
            if closeCode.rawValue == 4401 {
                self.finish(.unknown("The PC refused the voice token."))
            } else {
                self.finish(.unknown("The PC closed the voice connection before replying."))
            }
        }
    }

    func urlSession(_ session: URLSession, task: URLSessionTask, didCompleteWithError error: (any Error)?) {
        guard error != nil else { return }
        DispatchQueue.main.async {
            guard !self.finished, task === self.socket else { return }
            self.finish(.unknown("Could not reach the voice service on the PC."))
        }
    }

    private func receive(_ socket: URLSessionWebSocketTask) {
        socket.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .failure:
                DispatchQueue.main.async {
                    guard !self.finished, socket === self.socket else { return }
                    self.finish(.unknown("Could not reach the voice service on the PC."))
                }
            case .success(.string(let text)):
                DispatchQueue.main.async {
                    guard !self.finished, socket === self.socket else { return }
                    self.handle(text)
                    if !self.finished { self.receive(socket) }
                }
            case .success:
                DispatchQueue.main.async {
                    guard !self.finished, socket === self.socket else { return }
                    self.receive(socket)
                }
            }
        }
    }

    private func handle(_ text: String) {
        switch VoiceMessageParsing.parse(text) {
        case .ready:
            if !sentPayload {
                sentPayload = true
                let outgoing = payload
                payload = [:]
                sendJSON(outgoing)
            }
        case .phraseStatus(let status):
            finish(.status(status))
        case .phraseError(let reason):
            finish(.error(reason))
        case .card, .cardClosed, .unknown, .none:
            break
        }
    }

    private func sendJSON(_ object: [String: Any]) {
        guard let data = try? JSONSerialization.data(withJSONObject: object) else { return }
        socket?.send(.string(String(decoding: data, as: UTF8.self))) { _ in }
    }

    private func finish(_ outcome: Outcome) {
        guard !finished else { return }
        finished = true
        let done = completion
        completion = nil
        cleanup()
        done?(outcome)
    }

    private func cleanup() {
        timeoutWork?.cancel()
        timeoutWork = nil
        token = ""
        payload = [:]
        socket?.cancel(with: .normalClosure, reason: nil)
        socket = nil
        session?.invalidateAndCancel()
        session = nil
    }
}
