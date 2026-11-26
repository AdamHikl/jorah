import Foundation

/// Drive mode (ADR 0012). While Adam has it switched on in the HUD, a command line on
/// this Mac may type in the open conversation, read it and its cards, and deny cards. There is no
/// command to allow a card, pair, run power or brain actions, change the model or start a
/// conversation, so the socket can't ask for them. Pure, so it can be tested.
public enum DriveRules {
    public static let maxText = 4000
    public static let maxRequestBytes = 16 * 1024
    public static let maxCardId = 200
    public static let defaultReadLines = 12
    public static let maxReadLines = 40
    public static let defaultWaitSeconds: Double = 120
    public static let maxWaitSeconds: Double = 600

    /// The command line can only deny, under the same hold time and expiry as a click.
    public static func mayDeny(card: ApprovalCard, firstShownAt: Date, now: Date) -> Bool {
        ApprovalRules.mayAnswer(card: card, decision: "deny", firstShownAt: firstShownAt, now: now)
    }

    /// Put in front of every line drive mode types (ADR 0011 and 0012, 2026-11-26). HUD typing
    /// counts as Adam's own chat in jorah-guard; a turn whose text starts with this doesn't, so
    /// it keeps its cards. Jorah and the transcript see it; the HUD shows ⌨ CLAUDE CODE instead.
    public static let marker = "[Typed by Claude Code in HUD drive mode.]"
    static let markerStart = "[Typed by Claude Code"

    /// Commands drive mode may send as they are. OpenClaw runs a command only when the message
    /// starts with "/", so a marked line never runs one. None of these starts a turn for Jorah or
    /// lifts a check: the guard refuses `/jorah-careful off` from the HUD.
    public static let commands = ["/jorah-status", "/jorah-today", "/jorah-careful", "/jorah-careful on",
                                  "/jorah-careful off", "/status", "/help", "/commands", "/whoami"]

    /// What drive mode sends for `text`: an allowed command as it is, any other line with the
    /// marker in front, and nothing (nil) for any other line starting with "/".
    public static func wireText(_ text: String) -> String? {
        let t = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !t.isEmpty else { return nil }
        if t.hasPrefix("/") {
            let command = t.split(whereSeparator: \.isWhitespace).joined(separator: " ")
            return commands.contains(command) ? command : nil
        }
        return marker + "\n\n" + t
    }

    /// A history line without the marker, and whether it had one (near the start: the Gateway
    /// may put a timestamp first).
    public static func unmarked(_ text: String) -> (text: String, marked: Bool) {
        guard let start = text.range(of: markerStart),
              text.distance(from: text.startIndex, to: start.lowerBound) < 120,
              let end = text[start.upperBound...].firstIndex(of: "]")
        else { return (text, false) }
        let words = (text[..<start.lowerBound] + text[text.index(after: end)...])
            .trimmingCharacters(in: .whitespacesAndNewlines)
        return (words, true)
    }

    /// Whether a transcript line is the text that was sent. History may carry a prefix the Gateway
    /// added, so the end of the line counts too.
    public static func sameText(_ line: String, _ sent: String) -> Bool {
        let a = line.trimmingCharacters(in: .whitespacesAndNewlines)
        let b = sent.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !b.isEmpty else { return false }
        return a == b || a.hasSuffix(b)
    }

    /// Jorah has answered `sent` and stopped: nothing is running or streaming, and a reply or
    /// note follows the last line with that text. With no `sent`, only "nothing is running".
    public static func replyFinished(lines: [DriveLine], sent: String?, running: Bool) -> Bool {
        guard !running, !lines.contains(where: \.streaming) else { return false }
        guard let sent, !sent.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return true }
        guard let index = lines.lastIndex(where: { $0.role == .user && sameText($0.text, sent) }) else { return false }
        return lines[(index + 1)...].contains { $0.role != .user }
    }
}

/// A transcript line as drive mode sees it.
public struct DriveLine: Equatable, Sendable {
    public enum Role: String, Sendable { case user, assistant, notice }
    public let role: Role
    public let text: String
    public let streaming: Bool

    public init(role: Role, text: String, streaming: Bool = false) {
        self.role = role
        self.text = text
        self.streaming = streaming
    }
}

/// Everything the drive socket accepts. Nothing else parses.
public enum DriveCommand: Equatable, Sendable {
    case status
    case send(text: String)
    case read(limit: Int)
    case cards
    case deny(id: String)
    case wait(seconds: Double, sent: String?)
}

public struct DriveRefusal: Error, Equatable, Sendable {
    public let message: String
    public init(_ message: String) { self.message = message }
}

public enum DriveRequest {
    static let keys: [String: Set<String>] = [
        "status": ["cmd"], "send": ["cmd", "text"], "read": ["cmd", "limit"], "cards": ["cmd"],
        "deny": ["cmd", "id"], "wait": ["cmd", "seconds", "sent"],
    ]
    static let neverWords: Set<String> = [
        "allow", "allow-once", "allow-always", "approve", "resolve", "answer", "pair", "power", "brain",
        "model", "new", "kill", "pause", "resume",
    ]

    /// One request: a JSON object with "cmd" and only that command's own keys.
    public static func parse(_ data: Data) -> Result<DriveCommand, DriveRefusal> {
        guard data.count <= DriveRules.maxRequestBytes else { return .failure(DriveRefusal("The request is too long.")) }
        guard let object = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let cmd = object["cmd"] as? String
        else { return .failure(DriveRefusal("Not a drive request: send one JSON object with \"cmd\".")) }
        guard let allowed = keys[cmd] else {
            if neverWords.contains(cmd.lowercased()) {
                return .failure(DriveRefusal("Drive mode can't \(cmd): only Adam allows cards, pairs, runs power or brain actions and changes the model, by clicking in the HUD."))
            }
            return .failure(DriveRefusal("Unknown command \"\(cmd.prefix(40))\". Drive mode can: status, send, read, cards, deny, wait."))
        }
        let extra = Set(object.keys).subtracting(allowed)
        guard extra.isEmpty else {
            return .failure(DriveRefusal("\"\(cmd)\" doesn't take: \(extra.sorted().joined(separator: ", "))."))
        }
        switch cmd {
        case "status": return .success(.status)
        case "cards": return .success(.cards)
        case "send":
            guard let raw = object["text"] as? String else { return .failure(DriveRefusal("send needs \"text\".")) }
            let text = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !text.isEmpty else { return .failure(DriveRefusal("send needs some text.")) }
            guard text.count <= DriveRules.maxText else { return .failure(DriveRefusal("The text is over \(DriveRules.maxText) characters.")) }
            guard !text.unicodeScalars.contains(where: { $0.value == 0 }) else { return .failure(DriveRefusal("The text has a NUL character.")) }
            guard DriveRules.wireText(text) != nil else {
                return .failure(DriveRefusal("Drive mode sends only these commands: \(DriveRules.commands.joined(separator: ", ")). Other lines starting with \"/\" are Adam's."))
            }
            return .success(.send(text: text))
        case "read":
            guard let limit = intValue(object["limit"], default: DriveRules.defaultReadLines),
                  (1...DriveRules.maxReadLines).contains(limit)
            else { return .failure(DriveRefusal("read takes \"limit\" from 1 to \(DriveRules.maxReadLines).")) }
            return .success(.read(limit: limit))
        case "deny":
            guard let id = object["id"] as? String, !id.isEmpty, id.count <= DriveRules.maxCardId,
                  id.unicodeScalars.allSatisfy({ $0.isASCII && $0.value > 32 && $0.value < 127 })
            else { return .failure(DriveRefusal("deny needs the card's \"id\".")) }
            return .success(.deny(id: id))
        case "wait":
            guard let seconds = doubleValue(object["seconds"], default: DriveRules.defaultWaitSeconds),
                  seconds >= 1, seconds <= DriveRules.maxWaitSeconds
            else { return .failure(DriveRefusal("wait takes \"seconds\" from 1 to \(Int(DriveRules.maxWaitSeconds)).")) }
            let sent = object["sent"] as? String
            if object["sent"] != nil, sent == nil { return .failure(DriveRefusal("\"sent\" must be text.")) }
            guard (sent?.count ?? 0) <= DriveRules.maxText else { return .failure(DriveRefusal("\"sent\" is too long.")) }
            return .success(.wait(seconds: seconds, sent: sent))
        default:
            return .failure(DriveRefusal("Unknown command."))
        }
    }

    private static func intValue(_ value: Any?, default fallback: Int) -> Int? {
        guard let value else { return fallback }
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        let double = number.doubleValue
        guard double.rounded() == double, abs(double) < 1e6 else { return nil }
        return Int(double)
    }

    private static func doubleValue(_ value: Any?, default fallback: Double) -> Double? {
        guard let value else { return fallback }
        guard let number = value as? NSNumber, CFGetTypeID(number) != CFBooleanGetTypeID() else { return nil }
        let double = number.doubleValue
        return double.isFinite ? double : nil
    }
}
