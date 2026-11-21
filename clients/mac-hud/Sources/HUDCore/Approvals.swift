import Foundation

/// One pending plugin approval ("card") as the Gateway lists it, cleaned for plain-text display.
///
/// Card text can carry outside text (a tool's arguments, a page title), so everything here is
/// shown as plain text: no Markdown, no links, no control or direction-changing characters.
public struct ApprovalCard: Identifiable, Equatable, Sendable {
    public struct Field: Equatable, Sendable {
        public let name: String
        public let value: String
    }

    public let id: String
    public let title: String
    public let description: String
    public let severity: String?
    /// Every other scalar the request carried, flattened (`scope.kind`), sorted by name.
    public let fields: [Field]
    /// What the Gateway will accept for this card. The HUD offers at most `allow-once` and `deny`.
    public let allowedDecisions: [String]
    public let createdAt: Date?
    public let expiresAt: Date?

    /// The decisions the HUD shows as buttons, in order. Never `allow-always`.
    public var offeredDecisions: [String] {
        ApprovalRules.offered.filter { allowedDecisions.contains($0) }
    }

    public func secondsLeft(at now: Date) -> Int? {
        guard let expiresAt else { return nil }
        return max(0, Int(expiresAt.timeIntervalSince(now).rounded(.down)))
    }

    public func isExpired(at now: Date) -> Bool {
        guard let expiresAt else { return false }
        return expiresAt <= now
    }
}

public enum ApprovalRules {
    /// The only decisions the HUD can send.
    public static let offered = ["allow-once", "deny"]
    /// A card's buttons stay disabled this long after the card first shows, so a click aimed at
    /// something else cannot land on a card that just appeared.
    public static let holdSeconds: TimeInterval = 1.5
    public static let maxFieldValue = 300
    public static let maxFields = 30
    public static let maxTitle = 120
    public static let maxDescription = 1200

    /// Whether a click may send `decision` for `card`. Pure, so it can be tested.
    public static func mayAnswer(card: ApprovalCard, decision: String, firstShownAt: Date, now: Date) -> Bool {
        guard offered.contains(decision), card.allowedDecisions.contains(decision) else { return false }
        guard !card.isExpired(at: now) else { return false }
        return now.timeIntervalSince(firstShownAt) >= holdSeconds
    }
}

public enum ApprovalParsing {
    /// Parses `plugin.approval.list`'s result: an array of `{ id, request, createdAtMs, expiresAtMs }`.
    /// Rows without an id are dropped. Returns nil when the result is not a list at all.
    public static func cards(fromList result: Any?) -> [ApprovalCard]? {
        let rows: [Any]
        if let array = result as? [Any] {
            rows = array
        } else if let object = result as? [String: Any], let array = object["approvals"] as? [Any] ?? object["items"] as? [Any] {
            rows = array
        } else {
            return nil
        }
        return rows.compactMap { card(fromRow: $0) }
    }

    public static func card(fromRow row: Any) -> ApprovalCard? {
        guard let row = row as? [String: Any], let rawId = row["id"] as? String else { return nil }
        let id = PlainText.clean(rawId, limit: 200)
        guard !id.isEmpty else { return nil }
        let request = row["request"] as? [String: Any] ?? [:]
        let title = PlainText.clean(request["title"] as? String ?? "", limit: ApprovalRules.maxTitle)
        let description = PlainText.clean(request["description"] as? String ?? "", limit: ApprovalRules.maxDescription)
        let severity = (request["severity"] as? String).map { PlainText.clean($0, limit: 20) }
        let allowed = (request["allowedDecisions"] as? [Any])?.compactMap { $0 as? String }
            ?? ["allow-once", "allow-always", "deny"]

        var fields: [ApprovalCard.Field] = []
        flatten(request, prefix: "", into: &fields,
                skip: ["title", "description", "severity", "allowedDecisions"])
        fields.sort { $0.name < $1.name }
        if fields.count > ApprovalRules.maxFields {
            let hidden = fields.count - ApprovalRules.maxFields
            fields = Array(fields.prefix(ApprovalRules.maxFields))
            fields.append(.init(name: "…", value: "\(hidden) more fields not shown"))
        }

        return ApprovalCard(
            id: id, title: title.isEmpty ? "(no title)" : title, description: description,
            severity: severity, fields: fields, allowedDecisions: allowed,
            createdAt: date(fromMs: row["createdAtMs"]), expiresAt: date(fromMs: row["expiresAtMs"]))
    }

    /// The id a `plugin.approval.resolved` event names, if any.
    public static func resolvedId(fromEvent payload: Any?) -> String? {
        guard let payload = payload as? [String: Any] else { return nil }
        return payload["id"] as? String ?? (payload["approval"] as? [String: Any])?["id"] as? String
    }

    private static func flatten(_ object: [String: Any], prefix: String, into fields: inout [ApprovalCard.Field], skip: Set<String>) {
        for (key, value) in object {
            if prefix.isEmpty, skip.contains(key) { continue }
            let name = PlainText.clean(prefix.isEmpty ? key : "\(prefix).\(key)", limit: 80)
            switch value {
            case let nested as [String: Any]:
                flatten(nested, prefix: name, into: &fields, skip: [])
            case let list as [Any]:
                let parts = list.map { item -> String in
                    if let string = item as? String { return string }
                    if let data = try? JSONSerialization.data(withJSONObject: item, options: [.sortedKeys, .fragmentsAllowed]) {
                        return String(decoding: data, as: UTF8.self)
                    }
                    return "\(item)"
                }
                fields.append(.init(name: name, value: PlainText.clean(parts.joined(separator: ", "), limit: ApprovalRules.maxFieldValue)))
            case is NSNull:
                continue
            case let number as NSNumber:
                // JSONSerialization gives booleans as NSNumber too.
                let text = CFGetTypeID(number) == CFBooleanGetTypeID() ? (number.boolValue ? "true" : "false") : number.stringValue
                fields.append(.init(name: name, value: text))
            case let string as String:
                fields.append(.init(name: name, value: PlainText.clean(string, limit: ApprovalRules.maxFieldValue)))
            default:
                fields.append(.init(name: name, value: PlainText.clean("\(value)", limit: ApprovalRules.maxFieldValue)))
            }
        }
    }

    private static func date(fromMs value: Any?) -> Date? {
        guard let number = value as? NSNumber else { return nil }
        let ms = number.doubleValue
        guard ms > 0 else { return nil }
        return Date(timeIntervalSince1970: ms / 1000)
    }
}

public enum PlainText {
    /// Keeps letters, digits, punctuation, spaces and line breaks. Drops control characters and
    /// format characters (bidi overrides, zero-width joiners, invisible separators), which could
    /// make a card read differently from what it says. Then clips to `limit` characters.
    public static func clean(_ text: String, limit: Int) -> String {
        var scalars = String.UnicodeScalarView()
        for scalar in text.unicodeScalars {
            if scalar == "\n" || scalar == "\t" { scalars.append(scalar == "\t" ? " " : scalar); continue }
            switch scalar.properties.generalCategory {
            case .control, .format, .surrogate, .privateUse, .unassigned, .lineSeparator, .paragraphSeparator:
                continue
            default:
                scalars.append(scalar)
            }
        }
        var out = String(scalars)
        while out.contains("\n\n\n") { out = out.replacingOccurrences(of: "\n\n\n", with: "\n\n") }
        out = out.trimmingCharacters(in: .whitespacesAndNewlines)
        if out.count > limit { out = String(out.prefix(limit)) + "…" }
        return out
    }
}
