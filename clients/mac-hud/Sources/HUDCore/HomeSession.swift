import Foundation

/// Rules for the HUD's hidden home session (`jorah-hud-home`).
///
/// OpenClaw defaults parentless `sessions.create` calls to Main (`agent:main:main`), so speaking
/// or typing in them makes Main watch the child and wake up (replying in Telegram). Creating HUD
/// conversations as children of an unused home session keeps them isolated from Main.
public enum HomeSessionRules {
    public static let label = "jorah-hud-home"
    public static let defaultsKey = "hud.homeSessionKey"
    public static let fallbackWarning = "This conversation may wake Jorah's main chat (couldn't set its parent)."

    /// Trims whitespace from a session key and drops empty strings.
    public static func usableKey(_ key: String?) -> String? {
        guard let trimmed = key?.trimmingCharacters(in: .whitespacesAndNewlines), !trimmed.isEmpty else {
            return nil
        }
        return trimmed
    }

    /// Parameters for creating the home session with no parent (its parent is Main, which is safe
    /// because the HUD never opens it or sends messages to it).
    public static func homeCreateParams(idempotencyKey: String) -> [String: String] {
        [
            "label": label,
            "idempotencyKey": idempotencyKey,
        ]
    }

    /// Parameters for creating a HUD conversation, and whether its home parent was set.
    public static func conversationCreateParams(
        idempotencyKey: String,
        homeSessionKey: String?
    ) -> (params: [String: String], hasParent: Bool) {
        if let parent = usableKey(homeSessionKey) {
            return (["idempotencyKey": idempotencyKey, "parentSessionKey": parent], true)
        }
        return (["idempotencyKey": idempotencyKey], false)
    }

    /// Extracts a session key from a `sessions.create` response payload.
    public static func sessionKey(fromCreateResult result: Any?) -> String? {
        guard let object = result as? [String: Any] else { return nil }
        if let key = usableKey(object["key"] as? String) { return key }
        if let session = object["session"] as? [String: Any],
           let key = usableKey(session["key"] as? String) {
            return key
        }
        return usableKey(object["sessionKey"] as? String)
    }

    /// Extracts a session key from a `sessions.resolve` response payload, returning nil when
    /// `ok` is false (e.g. `allowMissing: true` on a deleted session).
    public static func resolvedKey(fromResolveResult result: Any?) -> String? {
        guard let object = result as? [String: Any] else { return nil }
        if let ok = object["ok"] as? Bool, !ok { return nil }
        if let key = usableKey(object["key"] as? String) { return key }
        if let session = object["session"] as? [String: Any],
           let key = usableKey(session["key"] as? String) {
            return key
        }
        return nil
    }

    /// Finds a session key in a `sessions.list` payload by exact (trimmed, case-sensitive) label.
    public static func findSessionKey(withLabel targetLabel: String = label, inSessionsList result: Any?) -> String? {
        let rows: [Any]
        if let array = result as? [Any] {
            rows = array
        } else if let object = result as? [String: Any], let array = object["sessions"] as? [Any] {
            rows = array
        } else {
            return nil
        }
        for case let row as [String: Any] in rows {
            guard let rawLabel = row["label"] as? String,
                  rawLabel.trimmingCharacters(in: .whitespacesAndNewlines) == targetLabel,
                  let key = usableKey(row["key"] as? String)
            else { continue }
            return key
        }
        return nil
    }

    /// True when a `sessions.create` error means another session already owns the label.
    public static func isLabelAlreadyInUseError(_ text: String) -> Bool {
        text.localizedCaseInsensitiveContains("label already in use")
    }

    /// True for the HUD home session (by key or label), so it stays hidden and unopened.
    public static func isHomeSession(key: String, label rowLabel: String?, homeSessionKey: String?) -> Bool {
        if let home = usableKey(homeSessionKey), usableKey(key) == home {
            return true
        }
        if let rowLabel, rowLabel.trimmingCharacters(in: .whitespacesAndNewlines) == label {
            return true
        }
        return false
    }
}
