import HUDCore
import SwiftUI

/// The Max plan / API key switch (docs/adr/0009-hud-brain-switch.md): says which lane the PC is on,
/// what each one means, and switches only on a click of that lane's button.
struct BrainView: View {
    @Environment(HUDModel.self) private var model
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text("WHAT JORAH BILLS")
                    .font(.system(size: 14, weight: .bold, design: .monospaced))
                    .tracking(4)
                    .foregroundStyle(Theme.accent)
                Spacer()
                current
            }

            if model.brainBusy {
                Text("Working on the PC. Leave the HUD open until this finishes.")
                    .font(.system(size: 12)).foregroundStyle(Theme.amber)
            }

            HStack(alignment: .top, spacing: 12) {
                lane(.max,
                     title: "MAX PLAN",
                     points: [
                        "main (chat, voice, the iPhone), deep, heartbeats and Dreaming run on Jorah's Claude login, which is your own Max account.",
                        "They share your 5-hour and weekly limits with your own Claude Code sessions.",
                        "background stays on the key: its shell needs it.",
                     ],
                     button: "Switch to the Max plan")
                lane(.api,
                     title: "API KEY",
                     points: [
                        "Every agent bills Jorah's Console key, in the jorah workspace, capped at $80 a month.",
                        "When that credit runs out, Jorah stops answering until you add credit or switch back. Nothing falls back by itself.",
                        "Claude Code coding jobs stay on the Max plan either way.",
                     ],
                     button: "Switch to the API key")
            }

            VStack(alignment: .leading, spacing: 4) {
                note("A switch backs up the config, does a dry run, applies it without a restart, sets main's and deep's key order, then reads it all back. It takes about a minute.")
                note("Chats carry over. A reply already being written may finish on the old lane.")
            }

            if !model.brainLog.isEmpty {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 2) {
                            ForEach(Array(model.brainLog.enumerated()), id: \.offset) { index, line in
                                Text(verbatim: line)
                                    .font(Theme.mono(11))
                                    .foregroundStyle(color(of: line))
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .textSelection(.enabled)
                                    .id(index)
                            }
                        }
                    }
                    .frame(height: 150)
                    .padding(8)
                    .overlay(Rectangle().stroke(Theme.stroke, lineWidth: 0.5))
                    .onChange(of: model.brainLog.count) {
                        proxy.scrollTo(model.brainLog.count - 1, anchor: .bottom)
                    }
                }
            }

            HStack {
                Button("Check now") { model.runBrain(.status) }
                    .disabled(model.brainBusy)
                    .help("Read the lane on the PC. Changes nothing")
                Button("Run a test turn") { model.runBrain(.probe) }
                    .disabled(model.brainBusy)
                    .help("Send Jorah one short test message in a throwaway session, deleted afterwards. Uses a little credit or quota")
                if let probe = model.brainProbe {
                    Text(verbatim: "Last test: \(probeText(probe.route)) at \(probe.at.formatted(date: .omitted, time: .shortened))")
                        .font(Theme.mono(10))
                        .foregroundStyle(probe.route == model.brainLane.rawValue ? Theme.green : Theme.amber)
                }
                Spacer()
                Button("Close") { dismiss() }.disabled(model.brainBusy)
            }
        }
        .padding(22)
        .frame(width: 640)
        .background(Theme.background)
        .preferredColorScheme(.dark)
        .onAppear {
            // Read-only, so the sheet never offers a switch from a stale reading.
            if !model.brainBusy { model.runBrain(.status) }
        }
    }

    private var current: some View {
        let (text, colour) = laneLabel
        return VStack(alignment: .trailing, spacing: 2) {
            Text(text).font(Theme.label(11)).foregroundStyle(colour)
            Text(model.brainCheckedAt.map { "read \($0.formatted(date: .omitted, time: .shortened))" } ?? "not read")
                .font(Theme.mono(9)).foregroundStyle(Theme.dim)
        }
    }

    private var laneLabel: (String, Color) {
        if model.brainBusy { return ("CHECKING…", Theme.dim) }
        switch model.brainLane {
        case .api: return ("NOW: API KEY", Theme.green)
        case .max: return ("NOW: MAX PLAN", Theme.green)
        case .mixed: return ("NOW: MIXED", Theme.red)
        case .unknown: return ("NOW: UNKNOWN", Theme.amber)
        }
    }

    private func lane(_ target: BrainLane, title: String, points: [String], button: String) -> some View {
        let isCurrent = model.brainLane == target && !model.brainBusy
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(title).font(Theme.label(11)).tracking(2).foregroundStyle(isCurrent ? Theme.green : Theme.text)
                if isCurrent {
                    Text("IN USE").font(Theme.label(8)).foregroundStyle(Theme.green)
                }
            }
            ForEach(points, id: \.self) { point in
                HStack(alignment: .top, spacing: 6) {
                    Text("·").font(.system(size: 12)).foregroundStyle(Theme.dim)
                    Text(point).font(.system(size: 11)).foregroundStyle(Theme.text)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            Spacer(minLength: 0)
            // Never the default button and no shortcut: a switch is a click on this button only.
            Button(button) { model.runBrain(target == .api ? .api : .max) }
                .disabled(model.brainBusy || isCurrent || model.pausedAt != nil)
        }
        .padding(12)
        .frame(maxWidth: .infinity, minHeight: 190, alignment: .topLeading)
        .overlay(Rectangle().stroke(isCurrent ? Theme.green.opacity(0.6) : Theme.stroke, lineWidth: isCurrent ? 1 : 0.5))
    }

    private func note(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 6) {
            Image(systemName: "info.circle").font(.system(size: 10)).foregroundStyle(Theme.dim)
            Text(text).font(.system(size: 11)).foregroundStyle(Theme.dim)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func color(of line: String) -> Color {
        if line.hasPrefix("FAILED") || line.hasPrefix("REFUSED") || line.hasPrefix("The switch did not") { return Theme.red }
        if line.hasPrefix("WARNING") { return Theme.amber }
        if line.hasPrefix("LANE:") || line.hasPrefix("SWITCHED") || line.hasPrefix("PROBE:") { return Theme.accent }
        return Theme.text
    }

    private func probeText(_ route: String) -> String {
        switch route {
        case "api": return "ran on the API key"
        case "max": return "ran on the Max plan"
        case "failed": return "failed"
        default: return "route unknown"
        }
    }
}
