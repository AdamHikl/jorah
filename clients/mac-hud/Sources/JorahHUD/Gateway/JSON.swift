import Foundation

/// A loose JSON value. The Gateway's payloads change between releases, so the HUD
/// reads only the fields it shows and treats everything else as unknown.
enum JSONValue: Equatable, Sendable {
    case null
    case bool(Bool)
    case number(Double)
    case string(String)
    case array([JSONValue])
    case object([String: JSONValue])

    init(any: Any?) {
        switch any {
        case nil, is NSNull:
            self = .null
        case let n as NSNumber:
            if CFGetTypeID(n) == CFBooleanGetTypeID() {
                self = .bool(n.boolValue)
            } else {
                self = .number(n.doubleValue)
            }
        case let s as String:
            self = .string(s)
        case let a as [Any]:
            self = .array(a.map { JSONValue(any: $0) })
        case let o as [String: Any]:
            self = .object(o.mapValues { JSONValue(any: $0) })
        default:
            self = .null
        }
    }

    static func parse(_ text: String) -> JSONValue? {
        guard let data = text.data(using: .utf8),
              let any = try? JSONSerialization.jsonObject(with: data, options: [.fragmentsAllowed])
        else { return nil }
        return JSONValue(any: any)
    }

    var any: Any {
        switch self {
        case .null: return NSNull()
        case .bool(let b): return b
        case .number(let d):
            if d.rounded() == d, abs(d) < 9e15 { return Int64(d) }
            return d
        case .string(let s): return s
        case .array(let a): return a.map(\.any)
        case .object(let o): return o.mapValues(\.any)
        }
    }

    var serialized: String? {
        guard let data = try? JSONSerialization.data(withJSONObject: any, options: [.fragmentsAllowed]) else {
            return nil
        }
        return String(data: data, encoding: .utf8)
    }

    subscript(key: String) -> JSONValue {
        if case .object(let o) = self { return o[key] ?? .null }
        return .null
    }

    var string: String? {
        if case .string(let s) = self { return s }
        return nil
    }

    var double: Double? {
        if case .number(let d) = self { return d }
        return nil
    }

    var int: Int? {
        if case .number(let d) = self { return Int(d) }
        return nil
    }

    var bool: Bool? {
        if case .bool(let b) = self { return b }
        return nil
    }

    var array: [JSONValue]? {
        if case .array(let a) = self { return a }
        return nil
    }

    var object: [String: JSONValue]? {
        if case .object(let o) = self { return o }
        return nil
    }

    var isNull: Bool { self == .null }

    /// A date from a millisecond timestamp, or nil when the field is missing.
    var dateFromMs: Date? {
        guard let ms = double, ms > 0 else { return nil }
        return Date(timeIntervalSince1970: ms / 1000)
    }
}
