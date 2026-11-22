import Foundation

/// An approval card sent over `jorah-voice` for a voice turn (ADR 0010).
///
/// Follows ADR 0007's plain-text and click rules: all text is sanitised with `PlainText.clean`,
/// only `allow-once` and `deny` are offered, and buttons stay held for `ApprovalRules.holdSeconds`
/// after appearing and disable when expired or when the voice socket closes.
public struct VoiceCard: Identifiable, Equatable, Sendable {
    public let id: String
    public let title: String
    public let description: String
    public let leavesPC: Bool
    public let expiresAt: Date?
    public let needsPhrase: Bool
    public let phraseSet: Bool

    public init(
        id: String,
        title: String,
        description: String,
        leavesPC: Bool,
        expiresAt: Date?,
        needsPhrase: Bool,
        phraseSet: Bool
    ) {
        self.id = id
        self.title = title
        self.description = description
        self.leavesPC = leavesPC
        self.expiresAt = expiresAt
        self.needsPhrase = needsPhrase
        self.phraseSet = phraseSet
    }

    /// Only `allow-once` and `deny` are ever offered.
    public var offeredDecisions: [String] { ApprovalRules.offered }

    public func secondsLeft(at now: Date) -> Int? {
        guard let expiresAt else { return nil }
        return max(0, Int(expiresAt.timeIntervalSince(now).rounded(.down)))
    }

    public func isExpired(at now: Date) -> Bool {
        guard let expiresAt else { return false }
        return expiresAt <= now
    }
}

extension ApprovalRules {
    /// Whether a deliberate click may send `decision` for a voice `card`.
    public static func mayAnswer(
        voiceCard: VoiceCard,
        decision: String,
        firstShownAt: Date,
        now: Date,
        linkOpen: Bool = true
    ) -> Bool {
        guard linkOpen else { return false }
        guard offered.contains(decision) else { return false }
        guard !voiceCard.isExpired(at: now) else { return false }
        return now.timeIntervalSince(firstShownAt) >= holdSeconds
    }
}

/// Wire payload of `{"type":"phrase_status","set":B,"words":N|null,"locked":B}`.
public struct PhraseStatus: Equatable, Sendable {
    public let isSet: Bool
    public let words: Int?
    public let locked: Bool

    public init(isSet: Bool, words: Int?, locked: Bool) {
        self.isSet = isSet
        self.words = words
        self.locked = locked
    }
}

/// HUD-facing state of the voice confirmation phrase.
public enum PhraseState: Equatable, Sendable {
    case unknown
    case notSet(locked: Bool)
    case set(words: Int?, locked: Bool)

    public init(status: PhraseStatus) {
        if status.isSet {
            self = .set(words: status.words, locked: status.locked)
        } else {
            self = .notSet(locked: status.locked)
        }
    }

    public var isLocked: Bool {
        switch self {
        case .unknown: return false
        case .notSet(let locked), .set(_, let locked): return locked
        }
    }

    /// True when known to be set, false when known not to be set, nil when unknown.
    public var isSet: Bool? {
        switch self {
        case .unknown: return nil
        case .notSet: return false
        case .set: return true
        }
    }

    public var summaryText: String {
        switch self {
        case .unknown:
            return "unknown"
        case .notSet(let locked):
            return locked ? "locked" : "not set"
        case .set(let words, let locked):
            if locked { return "locked" }
            if let words {
                return "set, \(words) \(words == 1 ? "word" : "words")"
            }
            return "set"
        }
    }
}

/// Parsed PC → HUD frames on the `jorah-voice` WebSocket (`build/briefs/protocol.md`).
public enum VoiceServerMessage: Equatable, Sendable {
    case ready(sampleRate: Double)
    case card(VoiceCard)
    case cardClosed(id: String, outcome: String)
    case phraseStatus(PhraseStatus)
    case phraseError(reason: String)
    case unknown
}

public enum VoiceMessageParsing {
    /// Parses a JSON text frame from `jorah-voice`. Returns nil on malformed JSON or invalid
    /// required fields; returns `.unknown` for valid JSON with an ignored/other `type`.
    public static func parse(_ text: String) -> VoiceServerMessage? {
        guard let data = text.data(using: .utf8),
              let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let type = object["type"] as? String
        else { return nil }
        return parse(dictionary: object, type: type)
    }

    private static func parse(dictionary: [String: Any], type: String) -> VoiceServerMessage? {
        switch type {
        case "ready":
            return .ready(sampleRate: number(dictionary["sample_rate"]) ?? 24000)

        case "card":
            guard let rawId = dictionary["id"] as? String else { return nil }
            let id = PlainText.clean(rawId, limit: 200)
            guard !id.isEmpty else { return nil }
            let rawTitle = PlainText.clean(dictionary["title"] as? String ?? "", limit: ApprovalRules.maxTitle)
            let description = PlainText.clean(dictionary["description"] as? String ?? "", limit: ApprovalRules.maxDescription)
            let leavesPC = bool(dictionary["leaves_pc"]) ?? false
            let needsPhrase = bool(dictionary["needs_phrase"]) ?? leavesPC
            let phraseSet = bool(dictionary["phrase_set"]) ?? false
            let expiresAt = date(fromMs: dictionary["expires_at_ms"])
            return .card(VoiceCard(
                id: id,
                title: rawTitle.isEmpty ? "(no title)" : rawTitle,
                description: description,
                leavesPC: leavesPC,
                expiresAt: expiresAt,
                needsPhrase: needsPhrase,
                phraseSet: phraseSet
            ))

        case "card_closed":
            guard let rawId = dictionary["id"] as? String else { return nil }
            let id = PlainText.clean(rawId, limit: 200)
            guard !id.isEmpty else { return nil }
            let outcome = PlainText.clean(dictionary["outcome"] as? String ?? "", limit: 40)
            return .cardClosed(id: id, outcome: outcome)

        case "phrase_status":
            guard let isSet = bool(dictionary["set"]) else { return nil }
            let locked = bool(dictionary["locked"]) ?? false
            let words = integer(dictionary["words"])
            return .phraseStatus(PhraseStatus(isSet: isSet, words: words, locked: locked))

        case "phrase_error":
            guard let rawReason = dictionary["reason"] as? String else { return nil }
            let reason = PlainText.clean(rawReason, limit: 300)
            guard !reason.isEmpty else { return nil }
            return .phraseError(reason: reason)

        default:
            return .unknown
        }
    }

    private static func bool(_ value: Any?) -> Bool? {
        guard let number = value as? NSNumber, CFGetTypeID(number) == CFBooleanGetTypeID() else { return nil }
        return number.boolValue
    }

    private static func number(_ value: Any?) -> Double? {
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        let double = number.doubleValue
        return double.isFinite ? double : nil
    }

    private static func integer(_ value: Any?) -> Int? {
        guard let double = number(value), double >= 0, double <= Double(Int.max), double.rounded() == double else {
            return nil
        }
        return Int(double)
    }

    private static func date(fromMs value: Any?) -> Date? {
        guard let ms = number(value), ms > 0 else { return nil }
        return Date(timeIntervalSince1970: ms / 1000)
    }
}

/// Outgoing HUD → PC frames on the `jorah-voice` WebSocket (`build/briefs/protocol.md`).
public enum VoiceMessageEncoding {
    public static func cardDecision(id: String, decision: String) -> [String: Any]? {
        guard !id.isEmpty, ApprovalRules.offered.contains(decision) else { return nil }
        return ["type": "card_decision", "id": id, "decision": decision]
    }

    public static func phraseStatusRequest() -> [String: Any] {
        ["type": "phrase_status_request"]
    }

    public static func phraseSet(phrase: String) -> [String: Any]? {
        let trimmed = phrase.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        return ["type": "phrase_set", "phrase": trimmed]
    }

    public static func phraseClear() -> [String: Any] {
        ["type": "phrase_clear"]
    }

    public static func settingsHello(token: String) -> [String: Any]? {
        guard !token.isEmpty else { return nil }
        return ["type": "hello", "token": token, "purpose": "settings"]
    }
}

/// Deduplicates voice cards against the Gateway's approval list so each card id is shown once.
public enum VoiceCardDedupe {
    public static func uniqueVoiceCards(
        voiceCards: [VoiceCard],
        gatewayApprovals: [ApprovalCard]
    ) -> [VoiceCard] {
        let gatewayIds = Set(gatewayApprovals.map(\.id))
        var seen: Set<String> = []
        return voiceCards.filter { card in
            guard !gatewayIds.contains(card.id) else { return false }
            return seen.insert(card.id).inserted
        }
    }
}

/// Result of checking the two confirmation-phrase `SecureField`s.
public enum PhraseMatch: Equatable, Sendable {
    case empty
    case mismatch
    case matched(String)

    public var isValid: Bool {
        if case .matched = self { return true }
        return false
    }

    public var trimmedPhrase: String? {
        if case .matched(let phrase) = self { return phrase }
        return nil
    }
}

public enum PhraseInput {
    public static func check(first: String, second: String) -> PhraseMatch {
        let a = first.trimmingCharacters(in: .whitespacesAndNewlines)
        let b = second.trimmingCharacters(in: .whitespacesAndNewlines)
        if a.isEmpty && b.isEmpty { return .empty }
        if a != b { return .mismatch }
        return .matched(a)
    }
}
