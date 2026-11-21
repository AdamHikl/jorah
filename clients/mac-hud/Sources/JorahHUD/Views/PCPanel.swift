import HUDCore
import SwiftUI

/// The PC's load, read from the reader on Windows (docs/adr/0008-hud-pc-stats.md).
/// A missing value says "unknown" and its reason shows on hover. A reading older than
/// 10 seconds is not shown at all.
struct PCPanel: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        HUDPanel(title: "PC", asOf: model.pcStatsAsOf, isDemo: model.isDemo) {
            TimelineView(.periodic(from: .now, by: 1)) { timeline in
                if let stats = model.freshPCStats(at: timeline.date) {
                    rows(stats)
                } else {
                    UnknownText(text: model.pcStatsError.map { "unknown: \($0)" } ?? "unknown: no reading yet")
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
        }
        .onAppear { model.startPCStats() }
        .onDisappear { model.stopPCStats() }
    }

    @ViewBuilder
    private func rows(_ stats: PCStats) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            let cpu = stats.cpu
            MeterRow(label: "CPU", fraction: cpu?.percent.map { $0 / 100 },
                     value: join(PCFormat.percent(cpu?.percent), temperature(cpu?.temperatureC, warm: 75, hot: 85,
                                                                         reason: stats.unknown["cpu.temperatureC"])),
                     hot: Self.level(cpu?.temperatureC, warm: 75, hot: 85),
                     help: cpu?.temperatureSource ?? stats.unknown["cpu.temperatureC"] ?? stats.unknown["cpu.percent"])
            MeterRow(label: "RAM", fraction: PCFormat.fraction(stats.memory?.usedBytes, of: stats.memory?.totalBytes),
                     value: PCFormat.usage(stats.memory?.usedBytes, of: stats.memory?.totalBytes),
                     help: stats.unknown["memory"])
            let gpu = stats.gpu
            MeterRow(label: "GPU", fraction: gpu?.percent.map { $0 / 100 },
                     value: gpu == nil ? nil : join(PCFormat.percent(gpu?.percent),
                                                    temperature(gpu?.temperatureC, warm: 75, hot: 83, reason: nil),
                                                    gpu?.powerW.map { String(format: "%.0f W", $0) }),
                     hot: Self.level(gpu?.temperatureC, warm: 75, hot: 83),
                     help: gpu?.name ?? stats.unknown["gpu"])
            MeterRow(label: "VRAM", fraction: PCFormat.fraction(gpu?.memoryUsedBytes, of: gpu?.memoryTotalBytes),
                     value: PCFormat.usage(gpu?.memoryUsedBytes, of: gpu?.memoryTotalBytes),
                     help: stats.unknown["gpu"])
            TextRow(label: "NET",
                    value: stats.network.flatMap { network in
                        guard let down = PCFormat.rate(network.downBytesPerSec),
                              let up = PCFormat.rate(network.upBytesPerSec) else { return nil }
                        return "↓ \(down)  ↑ \(up)"
                    },
                    help: stats.network.map { $0.adapters.joined(separator: ", ") } ?? stats.unknown["network"])
            if stats.disks.isEmpty {
                TextRow(label: "DISK", value: nil, help: stats.unknown["disks"])
            }
            ForEach(Array(stats.disks.enumerated()), id: \.element.id) { index, disk in
                let key = "disks.\(disk.drives.joined()).temperatureC"
                MeterRow(label: disk.drives.joined(separator: " "),
                         fraction: PCFormat.fraction(disk.usedBytes, of: disk.totalBytes),
                         value: join(PCFormat.usage(disk.usedBytes, of: disk.totalBytes),
                                     temperature(disk.temperatureC, warm: 60, hot: 70, reason: stats.unknown[key])),
                         hot: Self.level(disk.temperatureC, warm: 60, hot: 70),
                         help: [disk.model, disk.kind?.uppercased()].compactMap { $0 }.joined(separator: " · "))
                if index == 0 {
                    TextRow(label: "I/O",
                            value: join(PCFormat.rate(disk.readBytesPerSec).map { "R \($0)" },
                                        PCFormat.rate(disk.writeBytesPerSec).map { "W \($0)" }),
                            help: "\(disk.drives.joined(separator: " ")) reads and writes. Active "
                                + (PCFormat.percent(disk.busyPercent) ?? "unknown") + " of the time")
                }
            }
        }
    }

    /// "48°C", or "temp unknown" when the PC gave a reason it couldn't read one.
    private func temperature(_ value: Double?, warm: Double, hot: Double, reason: String?) -> String? {
        if let text = PCFormat.celsius(value) { return text }
        return reason == nil ? nil : "temp unknown"
    }

    /// Joins the known parts with " · ". Nil when none is known.
    private func join(_ parts: String?...) -> String? {
        let known = parts.compactMap { $0 }
        return known.isEmpty ? nil : known.joined(separator: " · ")
    }

    static func level(_ temperature: Double?, warm: Double, hot: Double) -> MeterRow.Heat {
        guard let temperature else { return .normal }
        if temperature >= hot { return .hot }
        if temperature >= warm { return .warm }
        return .normal
    }
}

struct MeterRow: View {
    enum Heat { case normal, warm, hot }

    let label: String
    let fraction: Double?
    let value: String?
    var hot: Heat = .normal
    var help: String?

    var body: some View {
        HStack(spacing: 6) {
            Text(label).font(Theme.label(9)).foregroundStyle(Theme.dim)
                .frame(width: 34, alignment: .leading)
            Meter(fraction: fraction)
                .frame(width: 54, height: 5)
            Text(value ?? "unknown")
                .font(Theme.mono(10))
                .foregroundStyle(value == nil ? Theme.dim : color)
                .lineLimit(1)
                .truncationMode(.tail)
            Spacer(minLength: 0)
        }
        .help(help ?? "")
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label): \(value ?? "unknown")")
    }

    private var color: Color {
        switch hot {
        case .normal: return Theme.text
        case .warm: return Theme.amber
        case .hot: return Theme.red
        }
    }
}

struct TextRow: View {
    let label: String
    let value: String?
    var help: String?

    var body: some View {
        HStack(spacing: 6) {
            Text(label).font(Theme.label(9)).foregroundStyle(Theme.dim)
                .frame(width: 34, alignment: .leading)
            Text(value ?? "unknown")
                .font(Theme.mono(10))
                .foregroundStyle(value == nil ? Theme.dim : Theme.text)
                .lineLimit(1)
            Spacer(minLength: 0)
        }
        .help(help ?? "")
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(label == "I/O" ? "Disk activity" : label): \(value ?? "unknown")")
    }
}

/// A thin bar. Empty, with no fill, when the value is unknown; amber from 90%.
struct Meter: View {
    let fraction: Double?

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.dim.opacity(0.18))
                if let fraction {
                    Capsule()
                        .fill(fraction >= 0.9 ? Theme.amber : Theme.accent)
                        .frame(width: max(2, geometry.size.width * min(1, max(0, fraction))))
                }
            }
        }
        .accessibilityHidden(true)
    }
}
