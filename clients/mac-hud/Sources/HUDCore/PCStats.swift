import Foundation

/// One reading of the PC's load from `scripts/pc/pcstats.ps1` (contract: `docs/contracts/jorah-pcstats-v1.md`).
///
/// Every number is optional: the reader sends null when a source failed, with the reason in
/// `unknown`, and the HUD shows that as unknown, never as 0.
public struct PCStats: Equatable, Sendable {
    public struct CPU: Equatable, Sendable {
        public var name: String?
        public var percent: Double?
        public var temperatureC: Double?
        public var temperatureSource: String?

        public init(name: String?, percent: Double?, temperatureC: Double?, temperatureSource: String?) {
            self.name = name; self.percent = percent
            self.temperatureC = temperatureC; self.temperatureSource = temperatureSource
        }
    }

    public struct Memory: Equatable, Sendable {
        public var usedBytes: Double?
        public var totalBytes: Double?

        public init(usedBytes: Double?, totalBytes: Double?) {
            self.usedBytes = usedBytes; self.totalBytes = totalBytes
        }
    }

    public struct GPU: Equatable, Sendable {
        public var name: String?
        public var percent: Double?
        public var memoryUsedBytes: Double?
        public var memoryTotalBytes: Double?
        public var temperatureC: Double?
        public var powerW: Double?
        public var fanPercent: Double?

        public init(name: String?, percent: Double?, memoryUsedBytes: Double?, memoryTotalBytes: Double?,
                    temperatureC: Double?, powerW: Double?, fanPercent: Double?) {
            self.name = name; self.percent = percent
            self.memoryUsedBytes = memoryUsedBytes; self.memoryTotalBytes = memoryTotalBytes
            self.temperatureC = temperatureC; self.powerW = powerW; self.fanPercent = fanPercent
        }
    }

    public struct Network: Equatable, Sendable {
        public var downBytesPerSec: Double?
        public var upBytesPerSec: Double?
        public var adapters: [String]

        public init(downBytesPerSec: Double?, upBytesPerSec: Double?, adapters: [String]) {
            self.downBytesPerSec = downBytesPerSec; self.upBytesPerSec = upBytesPerSec; self.adapters = adapters
        }
    }

    public struct Disk: Equatable, Sendable, Identifiable {
        public var id: String { drives.joined(separator: " ") }
        public var drives: [String]
        public var model: String?
        /// "ssd", "hdd", or nil when Windows does not say.
        public var kind: String?
        public var usedBytes: Double?
        public var totalBytes: Double?
        public var readBytesPerSec: Double?
        public var writeBytesPerSec: Double?
        public var busyPercent: Double?
        public var temperatureC: Double?
        public var temperatureAt: Date?

        public init(drives: [String], model: String?, kind: String?, usedBytes: Double?, totalBytes: Double?,
                    readBytesPerSec: Double?, writeBytesPerSec: Double?, busyPercent: Double?,
                    temperatureC: Double?, temperatureAt: Date?) {
            self.drives = drives; self.model = model; self.kind = kind
            self.usedBytes = usedBytes; self.totalBytes = totalBytes
            self.readBytesPerSec = readBytesPerSec; self.writeBytesPerSec = writeBytesPerSec
            self.busyPercent = busyPercent; self.temperatureC = temperatureC; self.temperatureAt = temperatureAt
        }
    }

    public var at: Date?
    public var cpu: CPU?
    public var memory: Memory?
    public var gpu: GPU?
    public var network: Network?
    public var disks: [Disk]
    /// Why a value is missing, keyed by its path, e.g. `cpu.temperatureC`.
    public var unknown: [String: String]

    public init(at: Date?, cpu: CPU?, memory: Memory?, gpu: GPU?, network: Network?, disks: [Disk], unknown: [String: String]) {
        self.at = at; self.cpu = cpu; self.memory = memory; self.gpu = gpu
        self.network = network; self.disks = disks; self.unknown = unknown
    }

    public static let schema = "jorah-pcstats/1"
}

public enum PCStatsParsing {
    public enum Failure: Error, Equatable {
        case notJSON
        case wrongSchema(String?)
    }

    /// Parses a response body. Wrong types read as missing, so one odd field never hides the rest.
    public static func parse(_ data: Data) throws -> PCStats {
        guard let root = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            throw Failure.notJSON
        }
        let schema = root["schema"] as? String
        guard schema == PCStats.schema else { throw Failure.wrongSchema(schema) }

        let cpu = (root["cpu"] as? [String: Any]).map {
            PCStats.CPU(name: text($0["name"]), percent: number($0["percent"]),
                        temperatureC: number($0["temperatureC"]), temperatureSource: text($0["temperatureSource"]))
        }
        let memory = (root["memory"] as? [String: Any]).map {
            PCStats.Memory(usedBytes: number($0["usedBytes"]), totalBytes: number($0["totalBytes"]))
        }
        let gpu = (root["gpu"] as? [String: Any]).map {
            PCStats.GPU(name: text($0["name"]), percent: number($0["percent"]),
                        memoryUsedBytes: number($0["memoryUsedBytes"]), memoryTotalBytes: number($0["memoryTotalBytes"]),
                        temperatureC: number($0["temperatureC"]), powerW: number($0["powerW"]),
                        fanPercent: number($0["fanPercent"]))
        }
        let network = (root["network"] as? [String: Any]).map {
            PCStats.Network(downBytesPerSec: number($0["downBytesPerSec"]), upBytesPerSec: number($0["upBytesPerSec"]),
                            adapters: ($0["adapters"] as? [Any])?.compactMap(text) ?? [])
        }
        let disks = ((root["disks"] as? [Any]) ?? []).compactMap { item -> PCStats.Disk? in
            guard let row = item as? [String: Any] else { return nil }
            let drives = ((row["drives"] as? [Any]) ?? []).compactMap(text)
            guard !drives.isEmpty else { return nil }
            return PCStats.Disk(drives: drives, model: text(row["model"]), kind: text(row["kind"]),
                                usedBytes: number(row["usedBytes"]), totalBytes: number(row["totalBytes"]),
                                readBytesPerSec: number(row["readBytesPerSec"]), writeBytesPerSec: number(row["writeBytesPerSec"]),
                                busyPercent: number(row["busyPercent"]), temperatureC: number(row["temperatureC"]),
                                temperatureAt: date(row["temperatureAt"]))
        }
        var unknown: [String: String] = [:]
        for (key, value) in (root["unknown"] as? [String: Any]) ?? [:] {
            if let reason = text(value) { unknown[String(key.prefix(80))] = reason }
        }
        return PCStats(at: date(root["at"]), cpu: cpu, memory: memory, gpu: gpu, network: network,
                       disks: disks, unknown: unknown)
    }

    static func number(_ value: Any?) -> Double? {
        guard let value = value as? NSNumber, CFGetTypeID(value) != CFBooleanGetTypeID() else { return nil }
        let double = value.doubleValue
        return double.isFinite ? double : nil
    }

    /// Plain text only, short, with control characters dropped: the PC names its own hardware.
    static func text(_ value: Any?) -> String? {
        guard let value = value as? String else { return nil }
        let cleaned = String(String.UnicodeScalarView(value.unicodeScalars.filter {
            !CharacterSet.controlCharacters.contains($0) && $0.properties.generalCategory != .format
        })).trimmingCharacters(in: .whitespaces)
        return cleaned.isEmpty ? nil : String(cleaned.prefix(120))
    }

    static func date(_ value: Any?) -> Date? {
        guard let value = value as? String else { return nil }
        let formatter = ISO8601DateFormatter()
        formatter.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let date = formatter.date(from: value) { return date }
        formatter.formatOptions = [.withInternetDateTime]
        return formatter.date(from: value)
    }
}

/// Short labels for the PC panel. Nil in, nil out, so the view can say "unknown".
public enum PCFormat {
    public static func percent(_ value: Double?) -> String? {
        value.map { String(format: "%.0f%%", $0) }
    }

    public static func celsius(_ value: Double?) -> String? {
        value.map { String(format: "%.0f°C", $0) }
    }

    /// "14.2 / 31.8 GB". Both must be known.
    public static func usage(_ used: Double?, of total: Double?) -> String? {
        guard let used, let total, total > 0 else { return nil }
        let gb = 1_000_000_000.0
        if total >= 1_000 * gb {
            return String(format: "%.2f / %.2f TB", used / (1_000 * gb), total / (1_000 * gb))
        }
        let digits = total >= 100 * gb ? "%.0f / %.0f GB" : "%.1f / %.1f GB"
        return String(format: digits, used / gb, total / gb)
    }

    /// "1.2 MB/s", "840 KB/s", "0 B/s". Decimal units, as Task Manager shows disk speeds.
    public static func rate(_ bytesPerSecond: Double?) -> String? {
        guard let value = bytesPerSecond else { return nil }
        let units = ["B/s", "KB/s", "MB/s", "GB/s"]
        var scaled = max(0, value)
        var index = 0
        while scaled >= 1000, index < units.count - 1 {
            scaled /= 1000
            index += 1
        }
        let format = index == 0 || scaled >= 100 ? "%.0f %@" : "%.1f %@"
        return String(format: format, scaled, units[index])
    }

    /// 0...1 for a bar, or nil when either side is unknown.
    public static func fraction(_ used: Double?, of total: Double?) -> Double? {
        guard let used, let total, total > 0 else { return nil }
        return min(1, max(0, used / total))
    }
}
