import Foundation

/// A small operator client for the OpenClaw Gateway WebSocket protocol, wire version 4.
/// Written against the protocol docs and source of OpenClaw 2026.10.9, the version on the PC.
///
/// What it does: waits for `connect.challenge`, signs the device proof, sends `connect`,
/// keeps the device token the Gateway issues after Adam approves the pairing, then
/// carries requests, responses and events.
///
/// What it never does: store the shared Gateway token, ask for approval, pairing or admin
/// scopes, or register as a node.
@MainActor
final class GatewayClient {
    enum Phase: Equatable {
        case idle
        case connecting
        /// The Gateway wants Adam to approve this device. `requestId` is what he approves on the PC.
        case pairingRequired(requestId: String?)
        case connected
        case failed(String)
    }

    struct RequestError: Error, LocalizedError {
        let code: String
        let message: String
        let details: JSONValue
        var errorDescription: String? { "\(code): \(message)" }
    }

    static let clientId = "gateway-client"
    static let clientMode = "ui"
    static let clientVersion = "0.1.0"
    static let platform = "macos"
    static let deviceFamily = "Mac"
    static let role = "operator"
    static let caps = ["tool-events", "chat-only-assistant-text"]
    static let tokenAccount = "device-token"
    static let scopesDefaultsKey = "hud.grantedScopes"

    var onPhase: ((Phase) -> Void)?
    var onHello: ((JSONValue) -> Void)?
    var onEvent: ((String, JSONValue) -> Void)?

    private(set) var phase: Phase = .idle {
        didSet { if phase != oldValue { onPhase?(phase) } }
    }

    private let session = URLSession(configuration: .ephemeral)
    private var task: URLSessionWebSocketTask?
    private var generation = 0
    private var pending: [String: CheckedContinuation<JSONValue, Error>] = [:]
    private var connectRequestId: String?
    private var lastEventSeq: Int?
    private var reconnectAttempt = 0
    private var reconnectTask: Task<Void, Never>?

    private var url: URL?
    /// Held in memory only, and only until the Gateway issues a device token.
    private var sharedToken: String?
    private var requestedScopes: [String] = []
    private var identity: DeviceIdentity?

    static var hasStoredDeviceToken: Bool { Keychain.read(tokenAccount) != nil }

    static var storedScopes: [String] {
        UserDefaults.standard.stringArray(forKey: scopesDefaultsKey) ?? []
    }

    /// Forgets the pairing on this Mac. The Gateway's record is removed on the PC with `openclaw devices`.
    static func forgetPairing() {
        Keychain.delete(tokenAccount)
        UserDefaults.standard.removeObject(forKey: scopesDefaultsKey)
    }

    /// Starts or restarts the connection. Pass `sharedToken` only for a first pairing or a scope change.
    func start(url: URL, sharedToken: String?, scopes: [String]) {
        stop()
        self.url = url
        self.sharedToken = sharedToken?.trimmingCharacters(in: .whitespacesAndNewlines).nonEmpty
        self.requestedScopes = scopes
        reconnectAttempt = 0
        open()
    }

    func stop() {
        generation += 1
        reconnectTask?.cancel()
        reconnectTask = nil
        task?.cancel(with: .goingAway, reason: nil)
        task = nil
        failPending(RequestError(code: "CLOSED", message: "connection closed", details: .null))
        phase = .idle
    }

    /// Tries again after Adam approved the pairing on the PC.
    func retry() {
        guard url != nil else { return }
        reconnectAttempt = 0
        open()
    }

    func request(_ method: String, _ params: JSONValue = .object([:])) async throws -> JSONValue {
        guard phase == .connected, let task else {
            throw RequestError(code: "NOT_CONNECTED", message: "not connected", details: .null)
        }
        let id = UUID().uuidString
        let frame: JSONValue = .object([
            "type": .string("req"), "id": .string(id), "method": .string(method), "params": params,
        ])
        guard let text = frame.serialized else {
            throw RequestError(code: "ENCODE", message: "could not encode request", details: .null)
        }
        return try await withCheckedThrowingContinuation { continuation in
            pending[id] = continuation
            task.send(.string(text)) { [weak self] error in
                guard let error else { return }
                Task { @MainActor in self?.resolve(id, .failure(error)) }
            }
            Task { @MainActor [weak self] in
                try? await Task.sleep(for: .seconds(30))
                self?.resolve(id, .failure(RequestError(code: "TIMEOUT", message: "\(method) timed out", details: .null)))
            }
        }
    }

    // MARK: - Connection

    private func open() {
        guard let url else { return }
        generation += 1
        let gen = generation
        task?.cancel(with: .goingAway, reason: nil)
        failPending(RequestError(code: "CLOSED", message: "connection closed", details: .null))
        connectRequestId = nil
        lastEventSeq = nil

        if identity == nil { identity = DeviceIdentity.loadOrCreate() }
        guard identity != nil else {
            phase = .failed("Could not store the device key in the Keychain.")
            return
        }
        guard sharedToken != nil || Self.hasStoredDeviceToken else {
            phase = .failed("Not paired yet.")
            return
        }

        phase = .connecting
        let task = session.webSocketTask(with: url)
        task.maximumMessageSize = 32 * 1024 * 1024
        self.task = task
        task.resume()
        Task { await receiveLoop(task, gen) }
    }

    private func receiveLoop(_ task: URLSessionWebSocketTask, _ gen: Int) async {
        while gen == generation {
            do {
                let message = try await task.receive()
                guard gen == generation else { return }
                switch message {
                case .string(let text): handle(text)
                case .data(let data): if let text = String(data: data, encoding: .utf8) { handle(text) }
                @unknown default: break
                }
            } catch {
                guard gen == generation else { return }
                connectionDropped(error.localizedDescription)
                return
            }
        }
    }

    private func connectionDropped(_ reason: String) {
        failPending(RequestError(code: "CLOSED", message: reason, details: .null))
        task = nil
        // While waiting for Adam's approval, or after a refusal, do not loop.
        if case .pairingRequired = phase { return }
        if case .failed = phase { return }
        guard Self.hasStoredDeviceToken else {
            phase = .failed("Connection lost: \(reason)")
            return
        }
        phase = .connecting
        scheduleReconnect()
    }

    private func scheduleReconnect() {
        reconnectTask?.cancel()
        let delay = min(30.0, pow(2.0, Double(reconnectAttempt)))
        reconnectAttempt += 1
        let gen = generation
        reconnectTask = Task { [weak self] in
            try? await Task.sleep(for: .seconds(delay))
            guard let self, !Task.isCancelled, gen == self.generation else { return }
            self.open()
        }
    }

    // MARK: - Frames

    private func handle(_ text: String) {
        guard let frame = JSONValue.parse(text) else { return }
        switch frame["type"].string {
        case "event":
            let name = frame["event"].string ?? ""
            if name == "connect.challenge" {
                sendConnect(challenge: frame["payload"])
                return
            }
            if let seq = frame["seq"].int {
                if let last = lastEventSeq, seq > last + 1, phase == .connected {
                    // A gap means lost events. The protocol says to retire the connection and resync.
                    lastEventSeq = nil
                    open()
                    return
                }
                lastEventSeq = seq
            }
            onEvent?(name, frame["payload"])
        case "res":
            guard let id = frame["id"].string else { return }
            if id == connectRequestId {
                connectRequestId = nil
                handleConnectResponse(frame)
                return
            }
            if frame["ok"].bool == true {
                resolve(id, .success(frame["payload"]))
            } else {
                let error = frame["error"]
                resolve(id, .failure(RequestError(
                    code: error["code"].string ?? "ERROR",
                    message: error["message"].string ?? "request failed",
                    details: error["details"])))
            }
        default:
            break
        }
    }

    private func sendConnect(challenge: JSONValue) {
        guard let identity, let task,
              let nonce = challenge["nonce"].string,
              let ts = challenge["ts"].double, ts >= 0
        else {
            phase = .failed("The Gateway sent an invalid challenge.")
            return
        }
        let signedAt = Int64(ts)
        let storedToken = Keychain.read(Self.tokenAccount).flatMap { String(data: $0, encoding: .utf8) }
        // A shared token, when Adam just typed one, wins: that is a pairing or a scope change.
        let usingShared = sharedToken != nil
        let token = sharedToken ?? storedToken
        let scopes = usingShared || Self.storedScopes.isEmpty ? requestedScopes : Self.storedScopes

        let payload = DeviceIdentity.authPayloadV3(
            deviceId: identity.deviceId,
            clientId: Self.clientId,
            clientMode: Self.clientMode,
            role: Self.role,
            scopes: scopes,
            signedAtMs: signedAt,
            token: token,
            nonce: nonce,
            platform: Self.platform,
            deviceFamily: Self.deviceFamily)
        guard let signature = identity.sign(payload) else {
            phase = .failed("Could not sign the device proof.")
            return
        }

        var auth: [String: JSONValue] = [:]
        if usingShared, let token { auth["token"] = .string(token) } else if let token { auth["deviceToken"] = .string(token) }

        let id = UUID().uuidString
        connectRequestId = id
        let params: JSONValue = .object([
            "minProtocol": .number(4),
            "maxProtocol": .number(4),
            "client": .object([
                "id": .string(Self.clientId),
                "displayName": .string("Jorah HUD"),
                "version": .string(Self.clientVersion),
                "platform": .string(Self.platform),
                "deviceFamily": .string(Self.deviceFamily),
                "mode": .string(Self.clientMode),
            ]),
            "role": .string(Self.role),
            "scopes": .array(scopes.map { .string($0) }),
            "caps": .array(Self.caps.map { .string($0) }),
            "auth": .object(auth),
            "locale": .string(Locale.current.identifier.replacingOccurrences(of: "_", with: "-")),
            "userAgent": .string("jorah-hud/\(Self.clientVersion)"),
            "device": .object([
                "id": .string(identity.deviceId),
                "publicKey": .string(identity.publicKeyBase64Url),
                "signature": .string(signature),
                "signedAt": .number(Double(signedAt)),
                "nonce": .string(nonce),
            ]),
        ])
        let frame: JSONValue = .object([
            "type": .string("req"), "id": .string(id), "method": .string("connect"), "params": params,
        ])
        guard let text = frame.serialized else { return }
        task.send(.string(text)) { _ in }
    }

    private func handleConnectResponse(_ frame: JSONValue) {
        if frame["ok"].bool == true {
            let hello = frame["payload"]
            let auth = hello["auth"]
            let granted = (auth["scopes"].array ?? []).compactMap(\.string)
            if let deviceToken = auth["deviceToken"].string, let data = deviceToken.data(using: .utf8) {
                // Keep the device token, then drop the shared token from memory.
                if Keychain.write(Self.tokenAccount, data) {
                    UserDefaults.standard.set(granted, forKey: Self.scopesDefaultsKey)
                    sharedToken = nil
                }
            }
            reconnectAttempt = 0
            phase = .connected
            onHello?(hello)
            return
        }

        let error = frame["error"]
        let details = error["details"]
        let code = details["code"].string ?? error["code"].string ?? "ERROR"
        let message = error["message"].string ?? "The Gateway refused the connection."
        switch code {
        case "PAIRING_REQUIRED", "NOT_PAIRED":
            // Do not retry on a timer: a new connect can replace the request Adam is about to approve.
            phase = .pairingRequired(requestId: details["requestId"].string)
        case "AUTH_SCOPE_MISMATCH":
            phase = .failed("The pairing does not cover these scopes. Pair again to change them.")
        default:
            if error["retryable"].bool == true, Self.hasStoredDeviceToken {
                phase = .connecting
                scheduleReconnect()
            } else {
                phase = .failed("\(code): \(message)")
            }
        }
    }

    /// Called by the model when the Gateway reports that this device's pairing request was settled.
    func pairingResolved(decision: String) {
        guard case .pairingRequired = phase else { return }
        if decision == "approved" {
            retry()
        } else {
            phase = .failed("The pairing request was \(decision).")
        }
    }

    private func resolve(_ id: String, _ result: Result<JSONValue, Error>) {
        guard let continuation = pending.removeValue(forKey: id) else { return }
        continuation.resume(with: result)
    }

    private func failPending(_ error: Error) {
        let waiting = pending
        pending.removeAll()
        for continuation in waiting.values { continuation.resume(throwing: error) }
    }
}

extension String {
    var nonEmpty: String? { isEmpty ? nil : self }
}
