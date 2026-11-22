import Foundation

/// What Jorah's Claude models bill, as `scripts/pc/brain-lane.sh` reads it on the PC
/// (docs/adr/0009-hud-brain-switch.md).
public enum BrainLane: String, Equatable, Sendable {
    /// Every agent on Jorah's Console key.
    case api
    /// main and deep on Jorah's Claude login, Adam's Max plan. background stays on the key.
    case max
    /// Some settings on one lane, some on the other: a switch stopped part way.
    case mixed
    /// Not read, or not readable.
    case unknown
}

public enum BrainLaneParsing {
    /// The lane from a run's output: the word after the last "LANE: " line. Anything else is unknown.
    public static func lane(in lines: [String]) -> BrainLane {
        guard let word = lastValue(of: "LANE:", in: lines) else { return .unknown }
        return BrainLane(rawValue: word) ?? .unknown
    }

    /// The route a test turn took: "api", "max", "failed" or "unknown"; nil when no test ran.
    public static func probe(in lines: [String]) -> String? {
        lastValue(of: "PROBE:", in: lines)
    }

    private static func lastValue(of prefix: String, in lines: [String]) -> String? {
        for line in lines.reversed() {
            let trimmed = line.trimmingCharacters(in: .whitespacesAndNewlines)
            guard trimmed.hasPrefix(prefix) else { continue }
            let rest = trimmed.dropFirst(prefix.count).trimmingCharacters(in: .whitespaces)
            return rest.split(separator: " ").first.map(String.init) ?? ""
        }
        return nil
    }
}
