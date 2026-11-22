import AppKit
import Foundation
import HUDCore
import Observation

struct ChatLine: Identifiable, Equatable {
    enum Role { case user, assistant, notice }
    let id: String
    var role: Role
    var text: String
    var at: Date?
    var streaming = false
}

struct ActivityItem: Identifiable, Equatable {
    enum State { case running, done, failed }
    let id: String
    var runId: String
    var name: String
    var detail: String
    var state: State
    var startedAt: Date
    var endedAt: Date?
    var isSubagent: Bool
}

struct SessionRow: Identifiable, Equatable {
    var id: String { key }
    let key: String
    var title: String
    var updatedAt: Date?
    var active: Bool
    var model: String?
    var totalTokens: Int?
    var modelProvider: String? = nil
    /// Why this model: "user" (chosen), "auto" or "inherited". Nil means the default, or not reported.
    var overrideSource: String? = nil
    /// The parent session's key, when this session is a sub-agent.
    var spawnedBy: String? = nil
    var label: String? = nil
    var status: String? = nil
    var startedAt: Date? = nil
    var endedAt: Date? = nil

    var isRunning: Bool {
        if let status { return status == "running" || status == "queued" }
        return active
    }
}

struct ModelChoice: Identifiable, Equatable {
    let id: String
    var name: String
    var provider: String
    var available: Bool?
    var unavailableReason: String?

    /// The value `sessions.patch` takes: `provider/model`.
    var ref: String { HUDModel.modelRef(provider: provider, model: id) }
}

struct CronRow: Identifiable, Equatable {
    let id: String
    var name: String
    var enabled: Bool
    var nextRun: Date?
    var lastRun: Date?
    var lastStatus: String?
    var running: Bool
}

struct PresenceRow: Identifiable, Equatable {
    let id: String
    var label: String
    var detail: String
    var seenAt: Date?
}

struct EventTick: Identifiable, Equatable {
    let id = UUID()
    let name: String
    let at: Date
}

enum OrbState: String {
    case offline = "OFFLINE"
    case listening = "LISTENING"
    case idle = "STANDING BY"
    case thinking = "THINKING"
    case acting = "WORKING"
    case speaking = "REPLYING"
}

/// Everything the HUD shows. Each panel keeps its own "as of" time, and a value the
/// Gateway has not sent stays nil and is drawn as unknown, never as 0.
@MainActor
@Observable
final class HUDModel {
    // Settings
    var gatewayURLText: String = HUDProfile.defaults.string(forKey: "hud.gatewayURL") ?? "wss://rocket.tail1574a5.ts.net" {
        didSet { HUDProfile.defaults.set(gatewayURLText, forKey: "hud.gatewayURL") }
    }
    var commandMode: Bool = HUDProfile.defaults.object(forKey: "hud.commandMode") as? Bool ?? true {
        didSet { HUDProfile.defaults.set(commandMode, forKey: "hud.commandMode") }
    }

    var voiceURLText: String = HUDProfile.defaults.string(forKey: "hud.voiceURL") ?? "wss://rocket.tail1574a5.ts.net:43211" {
        didSet {
            HUDProfile.defaults.set(voiceURLText, forKey: "hud.voiceURL")
            voice.configure(url: URL(string: voiceURLText))
        }
    }

    // Voice
    var voiceState: VoiceEngine.State = .off
    var voiceLevel: Double = 0
    var voiceError: String?
    var lastHeard: String?
    /// The last few words the wake listener heard on this Mac. Memory only, cleared when it stops.
    var wakeHeard: String?
    /// The whole message behind the last spoken overview. Memory only; closed by Adam or replaced.
    var fullReply: String?
    var lastSpoken: String?
    var wakeEnabled = false
    let voice = VoiceEngine()

    // Voice-confirmed cards & confirmation phrase (ADR 0010). The phrase itself is never stored here.
    var voiceCards: [VoiceCard] = []
    var voiceCardFirstShown: [String: Date] = [:]
    var voiceCardBusy: Set<String> = []
    var voiceCardErrors: [String: String] = [:]
    var showPhraseSheet = false
    var phraseState: PhraseState = .unknown
    var phraseBusy = false
    var phraseError: String?
    private var voiceSessionHadReady = false

    // Kill switch
    var showPower = false
    var powerBusy = false
    var powerLog: [String] = []
    /// When this Mac paused Jorah on the PC. The PC is the truth: this only remembers what was done here.
    var pausedAt: Date? = HUDProfile.defaults.object(forKey: "hud.pausedAt") as? Date {
        didSet { HUDProfile.defaults.set(pausedAt, forKey: "hud.pausedAt") }
    }
    let power = PowerControl()

    // Max plan / API key switch (docs/adr/0009-hud-brain-switch.md). The PC is the truth: the lane
    // is what the last run read there, with its time, and unknown until one has.
    var showBrain = false
    var brainBusy = false
    var brainLog: [String] = []
    var brainLane: BrainLane = .unknown
    var brainCheckedAt: Date?
    /// The route the last test turn took ("api", "max", "failed", "unknown"), and when.
    var brainProbe: (route: String, at: Date)?
    let brain = BrainControl()

    // PC stats (docs/adr/0008-hud-pc-stats.md). Read straight from the PC's reader over Serve, not
    // through the Gateway, so they keep coming while Jorah is paused. Polled only while the PC
    // panel is on screen and the HUD window is visible.
    var pcStatsURLText: String = HUDProfile.defaults.string(forKey: "hud.pcStatsURL") ?? "https://rocket.tail1574a5.ts.net:43231/v1/stats" {
        didSet { HUDProfile.defaults.set(pcStatsURLText, forKey: "hud.pcStatsURL") }
    }
    var pcStats: PCStats?
    /// When the last good reading arrived on this Mac.
    var pcStatsAsOf: Date?
    var pcStatsError: String?
    @ObservationIgnored private var pcStatsTask: Task<Void, Never>?
    @ObservationIgnored private lazy var pcStatsSession: URLSession = {
        let config = URLSessionConfiguration.ephemeral
        config.timeoutIntervalForRequest = 8
        config.requestCachePolicy = .reloadIgnoringLocalCacheData
        config.urlCache = nil
        config.httpCookieStorage = nil
        return URLSession(configuration: config)
    }()

    /// The last reading, or nil once it is more than 10 seconds old: an old number is not shown as now.
    func freshPCStats(at now: Date) -> PCStats? {
        if isDemo { return pcStats }
        guard let pcStats, let asOf = pcStatsAsOf, now.timeIntervalSince(asOf) <= 10 else { return nil }
        return pcStats
    }

    func startPCStats() {
        guard !isDemo, pcStatsTask == nil else { return }
        pcStatsTask = Task { [weak self] in
            while !Task.isCancelled {
                guard let self else { return }
                if Self.hudWindowIsVisible { await self.fetchPCStats() }
                try? await Task.sleep(for: .seconds(2))
            }
        }
    }

    func stopPCStats() {
        pcStatsTask?.cancel()
        pcStatsTask = nil
    }

    private static var hudWindowIsVisible: Bool {
        NSApp.windows.contains { $0.isVisible && $0.occlusionState.contains(.visible) && $0.frame.width > 600 }
    }

    func fetchPCStats() async {
        guard let url = URL(string: pcStatsURLText), url.scheme == "https" || url.scheme == "http" else {
            pcStatsError = "the PC stats address is not a web address"
            return
        }
        do {
            let (data, response) = try await pcStatsSession.data(from: url)
            let status = (response as? HTTPURLResponse)?.statusCode ?? 0
            guard status == 200 else {
                pcStatsError = status == 502 ? "the reader on the PC is not answering (502)" : "the PC answered \(status)"
                return
            }
            guard data.count <= 64_000 else {
                pcStatsError = "the PC sent an oversized reading"
                return
            }
            pcStats = try PCStatsParsing.parse(data)
            pcStatsAsOf = Date()
            pcStatsError = nil
        } catch PCStatsParsing.Failure.wrongSchema(let schema) {
            pcStatsError = "the PC sent \(schema ?? "no schema"), this HUD reads \(PCStats.schema)"
        } catch is PCStatsParsing.Failure {
            pcStatsError = "the PC sent something that is not a reading"
        } catch {
            pcStatsError = "can't reach the PC: \(error.localizedDescription)"
        }
    }

    // Connection
    var phase: GatewayClient.Phase = .idle
    var isDemo = false
    var showPairing = false
    var serverVersion: String?
    var grantedScopes: [String] = []
    var connectedAt: Date?
    var gatewayUptimeAtHello: (ms: Double, at: Date)?
    var lastTickAt: Date?

    // Conversation
    /// The Gateway's main session, the one Telegram uses (and voice uses by default).
    var mainSessionKey: String?
    /// The session the HUD is showing and typing into. Starts as the main one.
    var currentSessionKey: String?
    var mainSessionId: String?
    var sessionError: String?
    /// Unused parent for HUD-created conversations so talking in them does not wake Main (or Telegram).
    var homeSessionKey: String? = HUDProfile.defaults.string(forKey: HomeSessionRules.defaultsKey) {
        didSet {
            if let homeSessionKey {
                HUDProfile.defaults.set(homeSessionKey, forKey: HomeSessionRules.defaultsKey)
                sessions.removeAll { isHomeSession($0) }
            } else {
                HUDProfile.defaults.removeObject(forKey: HomeSessionRules.defaultsKey)
            }
        }
    }

    // Model of the session on screen. Nil means unknown.
    var models: [ModelChoice] = []
    var modelsAsOf: Date?
    var currentModel: String?
    var currentModelSource: String?
    var defaultModel: String?
    var modelError: String?
    var modelBusy = false

    // Sub-agents spawned by the session on screen
    var subagents: [SessionRow] = []
    var subagentsAsOf: Date?
    var subagentsError: String?
    private var subagentsRefresh: Task<Void, Never>?
    var lines: [ChatLine] = []
    var historyAsOf: Date?
    var draft = ""
    var sendError: String?

    // Work
    var activity: [ActivityItem] = []
    var activeRuns: Set<String> = []
    var lastDeltaAt: Date?
    var ticker: [EventTick] = []

    // Panels
    var sessions: [SessionRow] = []
    var sessionsAsOf: Date?
    var cron: [CronRow] = []
    var cronAsOf: Date?
    var cronError: String?
    var presence: [PresenceRow] = []
    var presenceAsOf: Date?
    var healthOK: Bool?
    var healthAsOf: Date?
    var channels: [String] = []
    var pluginErrors: Int?
    var heartbeatSeconds: Int?

    // Approval cards (ADR 0007). Nil `approvalsAsOf` means unknown: not linked, no scope, or the
    // list failed. The HUD never shows "no cards" unless the Gateway just said so.
    var approvals: [ApprovalCard] = []
    var approvalsAsOf: Date?
    var approvalsError: String?
    /// When each card first appeared on this screen. Buttons wait `ApprovalRules.holdSeconds`.
    var approvalFirstShown: [String: Date] = [:]
    var approvalBusy: Set<String> = []
    var approvalCardErrors: [String: String] = [:]
    /// One line about the last answer sent from here, shown under the cards.
    var approvalNote: String?
    /// "Ask for card access": the pending upgrade's request id while it waits for Adam on the PC.
    var cardAccessRequestId: String?
    var cardAccessError: String?
    private var cardAccessWait: Task<Void, Never>?
    private var approvalsRefresh: Task<Void, Never>?
    private var approvalsPoll: Task<Void, Never>?

    let client = GatewayClient()
    private var cronRefresh: Task<Void, Never>?
    private var sessionsRefresh: Task<Void, Never>?
    private var historyRefresh: Task<Void, Never>?

    var canWrite: Bool { grantedScopes.contains("operator.write") || grantedScopes.contains("operator.admin") }
    var canAnswerApprovals: Bool {
        grantedScopes.contains("operator.approvals") || grantedScopes.contains("operator.admin")
    }
    var isVoiceLinkOpen: Bool {
        voiceState == .listening || voiceState == .thinking || voiceState == .speaking
    }
    var visibleVoiceCards: [VoiceCard] {
        VoiceCardDedupe.uniqueVoiceCards(voiceCards: voiceCards, gatewayApprovals: approvals)
    }

    var orbState: OrbState {
        // An open voice session speaks for itself, whatever the Gateway link is doing.
        switch voiceState {
        case .listening, .connecting: return .listening
        case .thinking: return .thinking
        case .speaking: return .speaking
        case .off, .waitingForWake: break
        }
        guard phase == .connected || isDemo else { return .offline }
        if activity.contains(where: { $0.state == .running }) { return .acting }
        if let lastDeltaAt, Date().timeIntervalSince(lastDeltaAt) < 1.5 { return .speaking }
        if !activeRuns.isEmpty { return .thinking }
        return .idle
    }

    init() {
        client.onPhase = { [weak self] phase in self?.phaseChanged(phase) }
        client.onHello = { [weak self] hello in self?.applyHello(hello) }
        client.onEvent = { [weak self] name, payload in self?.apply(event: name, payload: payload) }

        voice.configure(url: URL(string: voiceURLText))
        voice.onState = { [weak self] state in
            guard let self else { return }
            // A spoken turn runs on the PC (jorah-voice → the conversation open here), not through
            // this HUD, so its transcript is fetched when Jorah starts speaking and when he's done.
            let wasBusy = self.voiceState == .thinking || self.voiceState == .speaking
            if state == .speaking || (wasBusy && !state.isSessionOpen) || (wasBusy && state == .listening) {
                self.scheduleHistoryRefresh(onlyForSession: self.currentSessionKey)
            }
            self.voiceState = state
            self.wakeEnabled = self.voice.wakeEnabled
            if state != .waitingForWake { self.wakeHeard = nil }
            if state.isSessionOpen { self.voiceError = nil }

            if self.isVoiceLinkOpen && !self.voiceSessionHadReady {
                self.voiceSessionHadReady = true
                self.clearVoiceCards()
                self.requestVoicePhraseStatus()
            } else if !state.isSessionOpen {
                self.voiceSessionHadReady = false
                self.voiceCardBusy.removeAll()
            }
        }
        voice.onWakeHeard = { [weak self] text in
            guard let self, self.voiceState == .waitingForWake else { return }
            self.wakeHeard = text
        }
        voice.onLevel = { [weak self] level in
            guard let self else { return }
            // Rise at once, fall gently, so the orb does not flicker.
            self.voiceLevel = max(Double(level), self.voiceLevel * 0.82)
        }
        voice.onHeard = { [weak self] text in self?.lastHeard = text }
        voice.onReply = { [weak self] text in self?.lastSpoken = text }
        voice.onFullReply = { [weak self] text in self?.fullReply = text }
        voice.onCard = { [weak self] card in self?.receiveVoiceCard(card) }
        voice.onCardClosed = { [weak self] id, outcome in self?.closeVoiceCard(id: id, outcome: outcome) }
        voice.onPhraseStatus = { [weak self] status in
            guard let self else { return }
            self.phraseState = PhraseState(status: status)
            self.phraseBusy = false
            self.phraseError = nil
        }
        voice.onPhraseError = { [weak self] reason in
            guard let self else { return }
            self.phraseBusy = false
            self.phraseError = reason
        }
        voice.onPhraseUnknown = { [weak self] reason in
            guard let self else { return }
            self.phraseState = .unknown
            self.phraseBusy = false
            self.phraseError = reason
        }
        voice.onError = { [weak self] message in
            guard let self else { return }
            self.voiceError = message
            self.wakeEnabled = self.voice.wakeEnabled
        }
    }

    // MARK: - Kill switch

    func runPower(_ action: PowerControl.Action, backup: Bool = true) {
        guard !isDemo, !powerBusy else { return }
        powerBusy = true
        powerLog = []
        if action == .pause {
            voice.setWake(false)
            voice.endSession()
            wakeEnabled = false
        }
        power.run(action, backup: backup, onLine: { [weak self] line in
            self?.powerLog.append(line)
        }, onFinish: { [weak self] ok in
            guard let self else { return }
            self.powerBusy = false
            switch action {
            case .pause:
                if ok {
                    self.pausedAt = Date()
                    self.client.stop()
                } else {
                    self.powerLog.append("Jorah may be partly stopped. Use \"Check what is running\".")
                }
            case .resume:
                if ok {
                    self.pausedAt = nil
                    self.startIfPaired()
                }
            case .status:
                break
            }
        })
    }

    // MARK: - Max plan / API key

    /// Reads the lane on the PC, or switches it. Switches come only from the buttons in BrainView.
    func runBrain(_ action: BrainControl.Action) {
        guard !isDemo, !brainBusy else { return }
        // A paused distro would be started by `wsl -d jorah`; the script refuses too, this saves the trip.
        guard pausedAt == nil else {
            brainLog = ["Jorah is paused from this Mac. Resume it first."]
            brainLane = .unknown
            brainCheckedAt = nil
            return
        }
        brainBusy = true
        brainLog = []
        brain.run(action, onLine: { [weak self] line in
            self?.brainLog.append(line)
        }, onFinish: { [weak self] ok in
            guard let self else { return }
            self.brainBusy = false
            self.brainLane = BrainLaneParsing.lane(in: self.brainLog)
            self.brainCheckedAt = self.brainLane == .unknown ? nil : Date()
            if let route = BrainLaneParsing.probe(in: self.brainLog) {
                self.brainProbe = (route, Date())
            }
            if let target = action.target {
                // A test turn from before the switch is not evidence of the new route.
                self.brainProbe = nil
                if !ok || self.brainLane != target {
                    self.brainLog.append("The switch did not finish. The lane above is what the PC has now.")
                }
            }
        })
    }

    // MARK: - Voice

    func toggleTalk() {
        guard !isDemo else { return }
        if voiceState.isSessionOpen { voice.endSession() } else { voice.startSession() }
    }

    func setWake(_ enabled: Bool) {
        guard !isDemo else { return }
        voiceError = nil
        wakeEnabled = enabled
        voice.setWake(enabled)
    }

    func requestVoicePhraseStatus() {
        guard !isDemo else { return }
        phraseBusy = true
        phraseError = nil
        voice.requestPhraseStatus()
    }

    func setVoicePhrase(_ phrase: String) {
        guard !isDemo, !phraseBusy else { return }
        phraseBusy = true
        phraseError = nil
        voice.setPhrase(phrase)
    }

    func clearVoicePhrase() {
        guard !isDemo, !phraseBusy else { return }
        phraseBusy = true
        phraseError = nil
        voice.clearPhrase()
    }

    // MARK: - Connection

    func startIfPaired() {
        guard !isDemo else { return }
        // Paused from here: do not hammer a Gateway that was stopped on purpose.
        guard pausedAt == nil else { return }
        guard GatewayClient.hasStoredDeviceToken, let url = URL(string: gatewayURLText) else {
            showPairing = true
            return
        }
        client.start(url: url, sharedToken: nil, scopes: GatewayClient.storedScopes)
    }

    /// First pairing, or a scope change. `sharedToken` is typed by Adam and is not stored.
    func pair(sharedToken: String, allowTyping: Bool, allowCards: Bool) {
        guard let url = URL(string: gatewayURLText), url.scheme == "wss" || url.scheme == "ws" else {
            phase = .failed("The Gateway address must start with wss://")
            return
        }
        var scopes = ["operator.read"]
        if allowTyping { scopes.append("operator.write") }
        if allowCards { scopes.append("operator.approvals") }
        GatewayClient.forgetPairing()
        client.start(url: url, sharedToken: sharedToken, scopes: scopes)
    }

    /// Asks the Gateway, over the live link, to add `operator.approvals` to this paired HUD
    /// (`device.scopes.requestUpgrade`). Nothing widens until Adam runs
    /// `openclaw --profile jorah devices approve <id>` on the PC; then `device.scopes.waitUpgrade`
    /// hands this connection a new device token, which the HUD keeps and reconnects with.
    func requestCardAccess() {
        guard !isDemo, phase == .connected, !canAnswerApprovals, cardAccessWait == nil else { return }
        var scopes = grantedScopes
        if !scopes.contains("operator.approvals") { scopes.append("operator.approvals") }
        cardAccessError = nil
        cardAccessWait = Task { [weak self] in
            guard let self else { return }
            defer { self.cardAccessWait = nil }
            do {
                let filed = try await self.client.request("device.scopes.requestUpgrade", .object([
                    "scopes": .array(scopes.map { .string($0) }),
                ]))
                guard let requestId = filed["requestId"].string else {
                    self.cardAccessError = "The Gateway did not return a request id."
                    return
                }
                self.cardAccessRequestId = PlainText.clean(requestId, limit: 80)
                // Wait as long as Adam needs; a timeout of this call only means "ask again".
                while !Task.isCancelled {
                    let result: JSONValue
                    do {
                        result = try await self.client.request("device.scopes.waitUpgrade", .object([
                            "requestId": .string(requestId),
                        ]), timeout: .seconds(300))
                    } catch let error as GatewayClient.RequestError where error.code == "TIMEOUT" {
                        continue
                    }
                    let status = result["status"].string ?? "unknown"
                    let granted = (result["scopes"].array ?? []).compactMap(\.string)
                    if status == "approved", let token = result["deviceToken"].string,
                       granted.contains("operator.approvals") {
                        self.cardAccessRequestId = nil
                        if !self.client.adoptUpgradedToken(token, scopes: granted) {
                            self.cardAccessError = "Approved, but the new device token could not be kept in the Keychain."
                        }
                    } else {
                        self.cardAccessRequestId = nil
                        self.cardAccessError = "Card access was not granted (\(PlainText.clean(status, limit: 40)))."
                    }
                    return
                }
            } catch {
                self.cardAccessRequestId = nil
                self.cardAccessError = "Card access request failed: \(error.localizedDescription)"
            }
        }
    }

    func forgetPairing() {
        client.stop()
        GatewayClient.forgetPairing()
        resetLiveState()
        showPairing = true
    }

    private func phaseChanged(_ phase: GatewayClient.Phase) {
        self.phase = phase
        switch phase {
        case .connected:
            showPairing = false
        case .pairingRequired:
            showPairing = true
        case .idle, .connecting, .failed:
            // Live facts are no longer current. Keep the transcript, drop "running" claims.
            activeRuns.removeAll()
            // Cards fail closed: without a link they are unknown, and none can be answered.
            clearApprovals()
            for index in activity.indices where activity[index].state == .running {
                activity[index].state = .failed
                activity[index].endedAt = Date()
                activity[index].detail = "connection lost before this finished"
            }
        }
    }

    private func resetLiveState() {
        lines = []; activity = []; activeRuns = []; sessions = []; cron = []; presence = []
        healthOK = nil; healthAsOf = nil; sessionsAsOf = nil; cronAsOf = nil; presenceAsOf = nil
        serverVersion = nil; grantedScopes = []; connectedAt = nil; gatewayUptimeAtHello = nil
        currentSessionKey = nil; mainSessionId = nil; sessionError = nil; homeSessionKey = nil
        voice.setSessionKey(nil)
        models = []; modelsAsOf = nil; currentModel = nil; currentModelSource = nil; defaultModel = nil
        subagents = []; subagentsAsOf = nil
        clearApprovals()
    }

    func applyHello(_ hello: JSONValue) {
        let now = Date()
        serverVersion = hello["server"]["version"].string
        grantedScopes = (hello["auth"]["scopes"].array ?? []).compactMap(\.string)
        connectedAt = now
        let snapshot = hello["snapshot"]
        if let uptime = snapshot["uptimeMs"].double { gatewayUptimeAtHello = (uptime, now) }
        applyPresence(snapshot["presence"], at: now)
        applyHealth(snapshot["health"], at: now)
        mainSessionKey = snapshot["sessionDefaults"]["mainSessionKey"].string ?? mainSessionKey
        if currentSessionKey == nil { currentSessionKey = mainSessionKey }
        voice.setSessionKey(currentSessionKey)
        guard !isDemo else { return }
        Task { await bootstrap() }
    }

    private func bootstrap() async {
        // Listeners are already installed, so events that race these calls are not lost.
        if let list = try? await client.request("sessions.subscribe", .object(["limit": .number(30), "excludeSubagents": .bool(true)])) {
            applySessions(list["list"])
        }
        if let key = currentSessionKey {
            _ = try? await client.request("sessions.messages.subscribe", .object(["key": .string(key)]))
            await loadHistory()
        }
        await refreshApprovals()
        startApprovalsPoll()
        await loadModels()
        await refreshSubagents()
        await refreshCron()
    }

    // MARK: - Approval cards

    private func clearApprovals() {
        // A link change ends a pending card-access wait; its request stays on the PC until it expires.
        cardAccessWait?.cancel(); cardAccessWait = nil; cardAccessRequestId = nil
        approvalsPoll?.cancel(); approvalsPoll = nil
        approvalsRefresh?.cancel(); approvalsRefresh = nil
        approvals = []; approvalsAsOf = nil; approvalsError = nil
        approvalFirstShown = [:]; approvalBusy = []; approvalCardErrors = [:]
    }

    /// Lists pending plugin approvals this HUD may answer. The list is the truth; events only
    /// make it arrive sooner. A failed list shows as unknown, never as "none".
    func refreshApprovals() async {
        guard !isDemo, phase == .connected else { return }
        guard canAnswerApprovals else {
            approvals = []; approvalsAsOf = nil; approvalsError = nil
            return
        }
        do {
            let result = try await client.request("plugin.approval.list", .object([:]))
            guard let cards = ApprovalParsing.cards(fromList: result.any) else {
                throw GatewayClient.RequestError(code: "SHAPE", message: "the Gateway's answer was not a list", details: .null)
            }
            let now = Date()
            let fresh = cards.filter { !$0.isExpired(at: now) }
            let arrived = fresh.filter { approvalFirstShown[$0.id] == nil }
            for card in fresh where approvalFirstShown[card.id] == nil { approvalFirstShown[card.id] = now }
            let live = Set(fresh.map(\.id))
            approvalFirstShown = approvalFirstShown.filter { live.contains($0.key) }
            approvalCardErrors = approvalCardErrors.filter { live.contains($0.key) }
            approvals = fresh.sorted { ($0.createdAt ?? .distantPast) < ($1.createdAt ?? .distantPast) }
            approvalsAsOf = now
            approvalsError = nil
            if !isVoiceLinkOpen { pruneExpiredVoiceCards(at: now) }
            if !arrived.isEmpty { NSApp.requestUserAttention(.criticalRequest) }
        } catch {
            approvals = []
            approvalsAsOf = nil
            approvalsError = "Cards unknown: \(error.localizedDescription)"
        }
    }

    private func scheduleApprovalsRefresh() {
        approvalsRefresh?.cancel()
        approvalsRefresh = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            await self?.refreshApprovals()
        }
    }

    /// Catches cards whose events were missed, and drops expired ones, while linked.
    private func startApprovalsPoll() {
        approvalsPoll?.cancel()
        approvalsPoll = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(15))
                guard !Task.isCancelled, let self, self.phase == .connected else { return }
                await self.refreshApprovals()
            }
        }
    }

    /// Sends Adam's answer to one card. The only caller is the card's button action in
    /// `ApprovalsPanel`: voice, chat text and anything Jorah writes have no path here.
    func answerApprovalFromClick(id: String, decision: String) {
        guard !isDemo, phase == .connected, canAnswerApprovals, !approvalBusy.contains(id),
              let card = approvals.first(where: { $0.id == id }),
              let shown = approvalFirstShown[id],
              ApprovalRules.mayAnswer(card: card, decision: decision, firstShownAt: shown, now: Date())
        else { return }
        approvalBusy.insert(id)
        approvalCardErrors[id] = nil
        Task {
            defer { approvalBusy.remove(id) }
            do {
                let result = try await client.request("plugin.approval.resolve", .object([
                    "id": .string(id), "decision": .string(decision),
                ]))
                let recorded = result["decision"].string
                if let recorded, recorded != decision {
                    approvalNote = "Already answered elsewhere (\(recorded)): \(card.title)"
                } else {
                    approvalNote = "\(decision == "deny" ? "Denied" : "Allowed once"): \(card.title)"
                }
                approvals.removeAll { $0.id == id }
            } catch let error as GatewayClient.RequestError
                where error.message.contains("already resolved") || error.message.contains("unknown or expired") {
                // Someone else answered first (Telegram), or it timed out. The first answer stands.
                approvalNote = "Not sent: already answered elsewhere or expired: \(card.title)"
                approvals.removeAll { $0.id == id }
            } catch {
                approvalCardErrors[id] = "Not answered: \(error.localizedDescription)"
            }
            await refreshApprovals()
        }
    }

    // MARK: - Voice cards

    private func clearVoiceCards() {
        voiceCards = []
        voiceCardFirstShown = [:]
        voiceCardBusy = []
        voiceCardErrors = [:]
    }

    private func pruneExpiredVoiceCards(at now: Date) {
        let expiredIds = Set(voiceCards.filter { $0.isExpired(at: now) }.map(\.id))
        guard !expiredIds.isEmpty else { return }
        voiceCards.removeAll { expiredIds.contains($0.id) }
        for id in expiredIds {
            voiceCardFirstShown.removeValue(forKey: id)
            voiceCardBusy.remove(id)
            voiceCardErrors.removeValue(forKey: id)
        }
    }

    func receiveVoiceCard(_ card: VoiceCard) {
        let now = Date()
        if let index = voiceCards.firstIndex(where: { $0.id == card.id }) {
            voiceCards[index] = card
        } else {
            voiceCards.append(card)
        }
        if voiceCardFirstShown[card.id] == nil {
            voiceCardFirstShown[card.id] = now
            NSApp.requestUserAttention(.criticalRequest)
        }
        voiceCardErrors[card.id] = nil
    }

    func closeVoiceCard(id: String, outcome: String) {
        let removed = voiceCards.first { $0.id == id }
        voiceCards.removeAll { $0.id == id }
        voiceCardFirstShown.removeValue(forKey: id)
        voiceCardBusy.remove(id)
        voiceCardErrors.removeValue(forKey: id)
        if let removed {
            switch outcome {
            case "allowed": approvalNote = "Allowed once: \(removed.title)"
            case "denied": approvalNote = "Denied: \(removed.title)"
            case "expired": approvalNote = "Expired: \(removed.title)"
            case "elsewhere": approvalNote = "Already answered elsewhere: \(removed.title)"
            default: break
            }
        }
    }

    /// Sends Adam's answer to one voice card over the active voice socket, never `plugin.approval.resolve`.
    /// The only caller is the card's button action in `ApprovalsPanel`.
    func answerVoiceCardFromClick(id: String, decision: String) {
        guard !isDemo, isVoiceLinkOpen, !voiceCardBusy.contains(id),
              let card = voiceCards.first(where: { $0.id == id }),
              let shown = voiceCardFirstShown[id],
              ApprovalRules.mayAnswer(voiceCard: card, decision: decision, firstShownAt: shown, now: Date(), linkOpen: isVoiceLinkOpen)
        else { return }
        voiceCardErrors[id] = nil
        if voice.sendCardDecision(id: id, decision: decision) {
            voiceCardBusy.insert(id)
            approvalNote = "\(decision == "deny" ? "Denied" : "Allowed once"): \(card.title)"
        } else {
            voiceCardErrors[id] = "Not sent: voice link closed."
        }
    }

    // MARK: - Models

    nonisolated static func modelRef(provider: String?, model: String) -> String {
        guard let provider, !provider.isEmpty, !model.hasPrefix(provider + "/") else { return model }
        return "\(provider)/\(model)"
    }

    private func updateCurrentModelFromRoster() {
        guard let key = currentSessionKey, let row = sessions.first(where: { $0.key == key }),
              let model = row.model else { return }
        currentModel = Self.modelRef(provider: row.modelProvider, model: model)
        currentModelSource = row.overrideSource
    }

    func loadModels() async {
        guard let key = currentSessionKey else { return }
        do {
            let result = try await client.request("models.list", .object([
                "sessionKey": .string(key), "view": .string("configured"), "includeDetails": .bool(true),
            ]))
            guard currentSessionKey == key else { return }
            models = (result["models"].array ?? []).compactMap { choice in
                guard let id = choice["id"].string else { return nil }
                return ModelChoice(
                    id: id, name: choice["name"].string ?? id, provider: choice["provider"].string ?? "",
                    available: choice["available"].bool, unavailableReason: choice["unavailableReason"].string)
            }
            if defaultModel == nil { defaultModel = result["modelSelectionPolicy"]["defaultModel"].string }
            modelsAsOf = Date()
            modelError = nil
        } catch {
            modelError = "Model list is unknown: \(error.localizedDescription)"
        }
    }

    /// Switches the model of the session on screen. Nil goes back to the default.
    func setModel(_ ref: String?) {
        guard !isDemo, canWrite, !modelBusy, let key = currentSessionKey else { return }
        modelBusy = true
        modelError = nil
        Task {
            defer { modelBusy = false }
            do {
                let result = try await client.request("sessions.patch", .object([
                    "key": .string(key), "model": ref.map { .string($0) } ?? .null,
                ]))
                guard currentSessionKey == key else { return }
                let resolved = result["resolved"]
                if let model = resolved["model"].string {
                    currentModel = Self.modelRef(provider: resolved["modelProvider"].string, model: model)
                    currentModelSource = ref == nil ? nil : "user"
                } else {
                    // The Gateway accepted the change but did not say what is now in effect.
                    currentModel = ref
                    currentModelSource = ref == nil ? nil : "user"
                }
            } catch {
                modelError = "Model not changed: \(error.localizedDescription)"
            }
        }
    }

    // MARK: - Sub-agents

    func refreshSubagents() async {
        guard !isDemo, phase == .connected, let key = currentSessionKey else { return }
        do {
            let result = try await client.request("sessions.list", .object([
                "spawnedBy": .string(key), "limit": .number(30),
            ]))
            guard currentSessionKey == key else { return }
            let rows = (result["sessions"].array ?? result.array ?? []).compactMap(Self.sessionRow(from:))
            subagents = rows.sorted {
                ($0.startedAt ?? $0.updatedAt ?? .distantPast) > ($1.startedAt ?? $1.updatedAt ?? .distantPast)
            }
            subagentsAsOf = Date()
            subagentsError = nil
        } catch {
            subagentsError = error.localizedDescription
        }
    }

    private func scheduleSubagentsRefresh() {
        subagentsRefresh?.cancel()
        subagentsRefresh = Task { [weak self] in
            try? await Task.sleep(for: .seconds(1))
            guard !Task.isCancelled else { return }
            await self?.refreshSubagents()
        }
    }

    /// Stops one sub-agent and anything it spawned.
    func stopSubagent(_ key: String) {
        guard !isDemo, canWrite else { return }
        Task {
            do {
                _ = try await client.request("sessions.abort", .object(["key": .string(key)]))
                subagentsError = nil
            } catch {
                subagentsError = "Not stopped: \(error.localizedDescription)"
            }
            await refreshSubagents()
        }
    }

    // MARK: - Sessions

    var isViewingMain: Bool { currentSessionKey == nil || currentSessionKey == mainSessionKey }

    var currentSessionTitle: String {
        guard let key = currentSessionKey else { return "session unknown" }
        if key == mainSessionKey { return "Main" }
        return sessions.first(where: { $0.key == key })?.title ?? key
    }

    func isHomeSession(_ row: SessionRow) -> Bool {
        HomeSessionRules.isHomeSession(key: row.key, label: row.label, homeSessionKey: homeSessionKey)
    }

    func isHomeSession(key: String) -> Bool {
        let label = sessions.first(where: { $0.key == key })?.label
        return HomeSessionRules.isHomeSession(key: key, label: label, homeSessionKey: homeSessionKey)
    }

    /// Shows another session: its transcript, its live replies and its tool calls.
    func switchSession(to key: String) {
        guard !isDemo, phase == .connected, key != currentSessionKey, !isHomeSession(key: key) else { return }
        let previous = currentSessionKey
        currentSessionKey = key
        voice.switchSession(to: key)
        mainSessionId = nil
        lines = []
        activity = []
        activeRuns = []
        historyAsOf = nil
        sendError = nil
        sessionError = nil
        models = []; modelsAsOf = nil; currentModel = nil; currentModelSource = nil; modelError = nil
        subagents = []; subagentsAsOf = nil; subagentsError = nil
        updateCurrentModelFromRoster()
        Task {
            if let previous {
                _ = try? await client.request("sessions.messages.unsubscribe", .object(["key": .string(previous)]))
            }
            do {
                _ = try await client.request("sessions.messages.subscribe", .object(["key": .string(key)]))
            } catch {
                sessionError = "Live updates for this session are unknown: \(error.localizedDescription)"
            }
            // A later switch may have won while these calls were in flight.
            guard currentSessionKey == key else { return }
            await loadHistory()
            await loadModels()
            await refreshSubagents()
        }
    }

    /// Starts a fresh conversation with Jorah and shows it. The main session is left as it is.
    func newConversation() {
        guard !isDemo, phase == .connected, canWrite else { return }
        sessionError = nil
        Task {
            // New conversations sit under an unused home session instead of Main so OpenClaw
            // does not wake Main (and Telegram) whenever Adam types or speaks in one.
            let parentKey = await ensureHomeSessionKey()
            let create = HomeSessionRules.conversationCreateParams(
                idempotencyKey: UUID().uuidString,
                homeSessionKey: parentKey
            )
            do {
                let result = try await client.request(
                    "sessions.create",
                    .object(create.params.mapValues { .string($0) })
                )
                guard let key = HomeSessionRules.sessionKey(fromCreateResult: result.any) else {
                    sessionError = "The Gateway created a session but did not say which. Pick it from the list."
                    return
                }
                guard !isHomeSession(key: key) else {
                    sessionError = "Could not start a new conversation: the Gateway returned the HUD home session."
                    return
                }
                if let row = Self.sessionRow(from: result["session"]) ?? Self.sessionRow(from: result) {
                    merge(session: row)
                }
                switchSession(to: key)
                if !create.hasParent {
                    sessionError = HomeSessionRules.fallbackWarning
                }
            } catch {
                sessionError = "Could not start a new conversation: \(error.localizedDescription)"
            }
        }
    }

    /// Ensures the hidden `jorah-hud-home` session exists on the Gateway and returns its key.
    private func ensureHomeSessionKey() async -> String? {
        if let stored = HomeSessionRules.usableKey(homeSessionKey) {
            if let existing = await verifySessionExists(key: stored) {
                if existing != homeSessionKey { homeSessionKey = existing }
                return existing
            }
            // The remembered home session is gone on the Gateway; clear it and recreate below.
            homeSessionKey = nil
        }

        do {
            let params = HomeSessionRules.homeCreateParams(idempotencyKey: UUID().uuidString)
            let result = try await client.request("sessions.create", .object(params.mapValues { .string($0) }))
            if let createdKey = HomeSessionRules.sessionKey(fromCreateResult: result.any) {
                homeSessionKey = createdKey
                return createdKey
            }
        } catch {
            let message = (error as? GatewayClient.RequestError)?.message ?? error.localizedDescription
            if HomeSessionRules.isLabelAlreadyInUseError(message) ||
                HomeSessionRules.isLabelAlreadyInUseError(error.localizedDescription) {
                if let found = await findHomeSessionByLabel() {
                    homeSessionKey = found
                    return found
                }
            }
        }
        return nil
    }

    private func verifySessionExists(key: String) async -> String? {
        do {
            let result = try await client.request("sessions.resolve", .object([
                "key": .string(key),
                "allowMissing": .bool(true),
            ]))
            return HomeSessionRules.resolvedKey(fromResolveResult: result.any)
        } catch {
            if let list = try? await client.request("sessions.list", .object([
                "limit": .number(100),
                "excludeSubagents": .bool(true),
            ])),
               let byLabel = HomeSessionRules.findSessionKey(withLabel: HomeSessionRules.label, inSessionsList: list.any) {
                return byLabel
            }
            return nil
        }
    }

    private func findHomeSessionByLabel() async -> String? {
        if let resolved = try? await client.request("sessions.resolve", .object([
            "label": .string(HomeSessionRules.label),
            "allowMissing": .bool(true),
        ])),
           let key = HomeSessionRules.resolvedKey(fromResolveResult: resolved.any) {
            return key
        }
        if let list = try? await client.request("sessions.list", .object([
            "limit": .number(100),
            "excludeSubagents": .bool(true),
        ])),
           let key = HomeSessionRules.findSessionKey(withLabel: HomeSessionRules.label, inSessionsList: list.any) {
            return key
        }
        return nil
    }

    /// Reloads the transcript half a second after the last change, if `key` is the session on
    /// screen (or unknown). Notices shown here (stops, failures) are kept in time order.
    private func scheduleHistoryRefresh(onlyForSession key: String?) {
        guard !isDemo, phase == .connected else { return }
        if let key, let current = currentSessionKey, key != current { return }
        historyRefresh?.cancel()
        historyRefresh = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(500))
            guard !Task.isCancelled, let self else { return }
            let notices = self.lines.filter { $0.role == .notice }
            await self.loadHistory()
            for notice in notices where !self.lines.contains(where: { $0.id == notice.id }) {
                let at = notice.at ?? .distantPast
                let index = self.lines.firstIndex(where: { ($0.at ?? .distantPast) > at }) ?? self.lines.endIndex
                self.lines.insert(notice, at: index)
            }
        }
    }

    private func loadHistory() async {
        guard let key = currentSessionKey else { return }
        do {
            let result = try await client.request("chat.history", .object([
                "sessionKey": .string(key), "limit": .number(40),
            ]))
            guard currentSessionKey == key else { return }
            mainSessionId = result["sessionId"].string
            var loaded: [ChatLine] = []
            for (index, message) in (result["messages"].array ?? []).enumerated() {
                guard let line = Self.line(from: message, fallbackId: "h\(index)") else { continue }
                loaded.append(line)
            }
            lines = loaded
            historyAsOf = Date()
            if let run = result["inFlightRun"]["runId"].string {
                activeRuns.insert(run)
                let text = result["inFlightRun"]["text"].string ?? ""
                upsertAssistant(runId: run, text: text, streaming: true)
            }
        } catch {
            lines.append(ChatLine(id: UUID().uuidString, role: .notice,
                                  text: "History is unknown: \(error.localizedDescription)", at: Date()))
        }
    }

    func refreshCron() async {
        do {
            let result = try await client.request("cron.list", .object(["includeDisabled": .bool(true), "limit": .number(50)]))
            let jobs = result["jobs"].array ?? result.array ?? []
            cron = jobs.compactMap { job in
                guard let id = job["id"].string else { return nil }
                let state = job["state"]
                return CronRow(
                    id: id,
                    name: job["displayName"].string ?? job["name"].string ?? id,
                    enabled: job["enabled"].bool ?? false,
                    nextRun: state["nextRunAtMs"].dateFromMs ?? job["nextRunAtMs"].dateFromMs,
                    lastRun: state["lastRunAtMs"].dateFromMs ?? job["lastRunAtMs"].dateFromMs,
                    lastStatus: state["lastRunStatus"].string ?? job["lastRunStatus"].string,
                    running: !state["runningAtMs"].isNull)
            }
            cronAsOf = Date()
            cronError = nil
        } catch {
            cronError = error.localizedDescription
        }
    }

    // MARK: - Sending

    func send() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, canWrite, let key = currentSessionKey else { return }
        guard !isHomeSession(key: key) else {
            sendError = "Not sent: cannot message the HUD home session."
            return
        }
        draft = ""
        sendError = nil
        let idempotencyKey = UUID().uuidString
        lines.append(ChatLine(id: "u-\(idempotencyKey)", role: .user, text: text, at: Date()))
        var params: [String: JSONValue] = [
            "sessionKey": .string(key),
            "message": .string(text),
            "idempotencyKey": .string(idempotencyKey),
        ]
        if let mainSessionId { params["sessionId"] = .string(mainSessionId) }
        Task {
            do {
                let ack = try await client.request("chat.send", .object(params))
                if let run = ack["runId"].string { activeRuns.insert(run) }
            } catch {
                sendError = "Not sent: \(error.localizedDescription)"
            }
        }
    }

    func stopRun() {
        guard canWrite, let key = currentSessionKey else { return }
        Task { _ = try? await client.request("chat.abort", .object(["sessionKey": .string(key)])) }
    }

    // MARK: - Events

    func apply(event name: String, payload: JSONValue) {
        let now = Date()
        if name != "tick" {
            ticker.append(EventTick(name: name, at: now))
            if ticker.count > 40 { ticker.removeFirst(ticker.count - 40) }
        }
        switch name {
        case "tick":
            lastTickAt = now
        case "chat":
            applyChat(payload, at: now)
        case "agent":
            applyAgent(payload, at: now)
        case "session.message":
            // A transcript change in the subscribed session, including turns that didn't start here
            // (voice, Telegram). Reloading is simpler and safer than merging the event's own shape.
            let key = payload["sessionKey"].string ?? payload["key"].string ?? payload["session"]["key"].string
            scheduleHistoryRefresh(onlyForSession: key)
        case "session.tool":
            let sessionKey = payload["sessionKey"].string
            let fromChild = payload["spawnedBy"].string != nil && payload["spawnedBy"].string == currentSessionKey
            guard sessionKey == nil || sessionKey == currentSessionKey || fromChild else { break }
            applyTool(runId: payload["runId"].string ?? "session", data: payload["data"].isNull ? payload : payload["data"],
                      spawnedBy: fromChild ? payload["spawnedBy"].string : nil, at: now)
            if fromChild { scheduleSubagentsRefresh() }
        case "presence":
            applyPresence(payload["presence"].isNull ? payload : payload["presence"], at: now)
        case "health":
            applyHealth(payload, at: now)
        case "cron", "cron.inventory.changed":
            cronRefresh?.cancel()
            cronRefresh = Task { [weak self] in
                try? await Task.sleep(for: .seconds(1))
                guard !Task.isCancelled else { return }
                await self?.refreshCron()
            }
        case "sessions.changed":
            if let row = Self.sessionRow(from: payload["session"]) {
                if let parent = row.spawnedBy {
                    // Sub-agents stay out of the roster and go to their own panel.
                    if parent == currentSessionKey { scheduleSubagentsRefresh() }
                    break
                }
                if isHomeSession(row) {
                    if homeSessionKey == nil { homeSessionKey = row.key }
                    sessions.removeAll { isHomeSession($0) }
                    break
                }
                merge(session: row)
                updateCurrentModelFromRoster()
                sessionsAsOf = now
            } else {
                sessionsRefresh?.cancel()
                sessionsRefresh = Task { [weak self] in
                    try? await Task.sleep(for: .seconds(1))
                    guard !Task.isCancelled, let self else { return }
                    if let list = try? await self.client.request("sessions.list", .object(["limit": .number(30), "excludeSubagents": .bool(true)])) {
                        self.applySessions(list)
                    }
                }
            }
        case "plugin.approval.requested":
            scheduleApprovalsRefresh()
        case "plugin.approval.resolved":
            // Answered here, in Telegram, or timed out: the first answer wins and the card goes.
            if let id = ApprovalParsing.resolvedId(fromEvent: payload.any) {
                approvals.removeAll { $0.id == id }
                voiceCards.removeAll { $0.id == id }
                voiceCardFirstShown.removeValue(forKey: id)
                voiceCardBusy.remove(id)
                voiceCardErrors.removeValue(forKey: id)
            }
            scheduleApprovalsRefresh()
        case "device.pair.resolved":
            client.pairingResolved(decision: payload["decision"].string ?? "unknown")
        case "shutdown":
            lines.append(ChatLine(id: UUID().uuidString, role: .notice,
                                  text: "The Gateway is shutting down: \(payload["reason"].string ?? "no reason given")", at: now))
        default:
            break
        }
    }

    private func applyChat(_ payload: JSONValue, at now: Date) {
        guard let runId = payload["runId"].string else { return }
        if let key = payload["sessionKey"].string, let current = currentSessionKey, key != current { return }
        switch payload["state"].string {
        case "delta":
            activeRuns.insert(runId)
            lastDeltaAt = now
            if !payload["message"].isNull, let snapshot = Self.text(of: payload["message"]) {
                upsertAssistant(runId: runId, text: snapshot, streaming: true)
            } else if payload["replace"].bool == true {
                upsertAssistant(runId: runId, text: payload["deltaText"].string ?? "", streaming: true)
            } else {
                appendAssistant(runId: runId, delta: payload["deltaText"].string ?? "")
            }
        case "final":
            activeRuns.remove(runId)
            if let text = Self.text(of: payload["message"]) {
                upsertAssistant(runId: runId, text: text, streaming: false)
            } else {
                finishAssistant(runId: runId)
            }
        case "aborted":
            activeRuns.remove(runId)
            finishAssistant(runId: runId)
            lines.append(ChatLine(id: UUID().uuidString, role: .notice, text: "Stopped.", at: now))
        case "error":
            activeRuns.remove(runId)
            finishAssistant(runId: runId)
            lines.append(ChatLine(id: UUID().uuidString, role: .notice,
                                  text: "Run failed: \(payload["errorMessage"].string ?? "no reason given")", at: now))
        default:
            break
        }
    }

    private func applyAgent(_ payload: JSONValue, at now: Date) {
        guard let runId = payload["runId"].string else { return }
        let data = payload["data"]
        switch payload["stream"].string {
        case "lifecycle":
            switch data["phase"].string {
            case "start": activeRuns.insert(runId)
            case "end", "error": activeRuns.remove(runId)
            default: break
            }
        case "tool":
            applyTool(runId: runId, data: data, spawnedBy: payload["spawnedBy"].string, at: now)
        default:
            break
        }
    }

    private func applyTool(runId: String, data: JSONValue, spawnedBy: String?, at now: Date) {
        let name = data["name"].string ?? data["toolName"].string ?? data["title"].string ?? "tool"
        let id = data["toolCallId"].string ?? data["id"].string ?? "\(runId):\(name)"
        let phase = data["phase"].string ?? data["status"].string ?? "start"
        let finished = ["result", "end", "done", "completed", "error", "failed"].contains(phase)
        let failed = data["isError"].bool == true || phase == "error" || phase == "failed"

        if let index = activity.firstIndex(where: { $0.id == id }) {
            if finished {
                activity[index].state = failed ? .failed : .done
                activity[index].endedAt = now
            }
        } else {
            activity.append(ActivityItem(
                id: id, runId: runId, name: name, detail: Self.summary(of: data["args"]),
                state: finished ? (failed ? .failed : .done) : .running,
                startedAt: now, endedAt: finished ? now : nil,
                isSubagent: spawnedBy != nil))
            if activity.count > 80 { activity.removeFirst(activity.count - 80) }
        }
    }

    private func applyPresence(_ value: JSONValue, at now: Date) {
        guard let entries = value.array else { return }
        presence = entries.enumerated().map { index, entry in
            let label = entry["host"].string ?? entry["clientId"].string ?? entry["deviceFamily"].string ?? "client"
            let parts = [entry["mode"].string, entry["platform"].string, entry["version"].string].compactMap { $0 }
            return PresenceRow(
                id: entry["connectionId"].string ?? entry["instanceId"].string ?? "\(index)-\(label)",
                label: label, detail: parts.joined(separator: " · "), seenAt: entry["ts"].dateFromMs)
        }
        presenceAsOf = now
    }

    private func applyHealth(_ value: JSONValue, at now: Date) {
        // The hello snapshot can be an empty object until the Gateway has measured health.
        guard let object = value.object, !object.isEmpty else { return }
        healthOK = value["ok"].bool
        healthAsOf = value["ts"].dateFromMs ?? now
        channels = (value["channelOrder"].array ?? []).compactMap(\.string)
        pluginErrors = value["plugins"]["errors"].array?.count
        heartbeatSeconds = value["heartbeatSeconds"].int
    }

    private func applySessions(_ list: JSONValue) {
        guard let rows = list["sessions"].array ?? list.array else { return }
        let parsed = rows.compactMap(Self.sessionRow(from:))
        if homeSessionKey == nil, let home = parsed.first(where: { isHomeSession($0) }) {
            homeSessionKey = home.key
        }
        sessions = parsed.filter { $0.spawnedBy == nil && !isHomeSession($0) }
        sessionsAsOf = Date()
        if let model = list["defaults"]["model"].string {
            defaultModel = Self.modelRef(provider: list["defaults"]["modelProvider"].string, model: model)
        }
        updateCurrentModelFromRoster()
    }

    private func merge(session row: SessionRow) {
        guard !isHomeSession(row) else { return }
        if let index = sessions.firstIndex(where: { $0.key == row.key }) {
            sessions[index] = row
        } else {
            sessions.insert(row, at: 0)
        }
        sessions.sort { ($0.updatedAt ?? .distantPast) > ($1.updatedAt ?? .distantPast) }
    }

    // MARK: - Transcript helpers

    private func assistantIndex(_ runId: String) -> Int? {
        lines.lastIndex(where: { $0.id == "a-\(runId)" })
    }

    private func upsertAssistant(runId: String, text: String, streaming: Bool) {
        if let index = assistantIndex(runId) {
            lines[index].text = text
            lines[index].streaming = streaming
        } else {
            lines.append(ChatLine(id: "a-\(runId)", role: .assistant, text: text, at: Date(), streaming: streaming))
        }
    }

    private func appendAssistant(runId: String, delta: String) {
        if let index = assistantIndex(runId) {
            lines[index].text += delta
            lines[index].streaming = true
        } else {
            lines.append(ChatLine(id: "a-\(runId)", role: .assistant, text: delta, at: Date(), streaming: true))
        }
    }

    private func finishAssistant(runId: String) {
        if let index = assistantIndex(runId) { lines[index].streaming = false }
    }

    static func line(from message: JSONValue, fallbackId: String) -> ChatLine? {
        let role: ChatLine.Role
        switch message["role"].string {
        case "user": role = .user
        case "assistant": role = .assistant
        default: return nil
        }
        guard var text = text(of: message), !text.isEmpty else { return nil }
        if role == .user { text = withoutSpokenNote(text) }
        let id = message["__openclaw"]["id"].string.map { "\($0)-\(fallbackId)" } ?? fallbackId
        return ChatLine(id: id, role: role, text: text, at: message["timestamp"].dateFromMs)
    }

    /// jorah-voice puts a bracketed "[Spoken turn. …]" instruction (its TURN_NOTE) in front of
    /// Adam's words. The transcript keeps it; the screen shows his words with a mic mark.
    static func withoutSpokenNote(_ text: String) -> String {
        guard let start = text.range(of: "[Spoken turn."),
              text.distance(from: text.startIndex, to: start.lowerBound) < 120,
              let end = text[start.upperBound...].firstIndex(of: "]")
        else { return text }
        let words = (text[..<start.lowerBound] + text[text.index(after: end)...])
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return "🎙 " + words
    }

    /// Visible text of a chat message: a string, or the text blocks of a content array.
    static func text(of message: JSONValue) -> String? {
        if message.isNull { return nil }
        let content = message["content"]
        if let string = content.string { return string }
        if let blocks = content.array {
            let parts = blocks.compactMap { block -> String? in
                block["type"].string == "text" ? block["text"].string : nil
            }
            return parts.isEmpty ? nil : parts.joined(separator: "\n")
        }
        return message["text"].string
    }

    static func sessionRow(from row: JSONValue) -> SessionRow? {
        guard let key = row["key"].string else { return nil }
        let title = row["derivedTitle"].string ?? row["title"].string ?? row["displayName"].string
            ?? row["label"].string ?? key
        var session = SessionRow(
            key: key, title: title, updatedAt: row["updatedAt"].dateFromMs,
            active: row["hasActiveRun"].bool ?? false,
            model: row["model"].string, totalTokens: row["totalTokens"].int)
        session.modelProvider = row["modelProvider"].string
        session.overrideSource = row["modelOverrideSource"].string
        session.spawnedBy = row["spawnedBy"].string
        session.label = row["label"].string
        session.status = row["status"].string
        session.startedAt = row["startedAt"].dateFromMs
        session.endedAt = row["endedAt"].dateFromMs
        return session
    }

    /// One short line describing a tool call's arguments.
    static func summary(of args: JSONValue) -> String {
        guard let object = args.object, !object.isEmpty else { return "" }
        for key in ["command", "cmd", "query", "url", "path", "file_path", "prompt", "task"] {
            if let value = object[key]?.string { return clip(value) }
        }
        let parts = object.keys.sorted().prefix(3).map { key -> String in
            let value = object[key]?.string ?? object[key]?.serialized ?? ""
            return "\(key)=\(value)"
        }
        return clip(parts.joined(separator: " "))
    }

    static func clip(_ text: String, _ limit: Int = 90) -> String {
        let single = text.replacingOccurrences(of: "\n", with: " ")
        return single.count > limit ? String(single.prefix(limit)) + "…" : single
    }
}
