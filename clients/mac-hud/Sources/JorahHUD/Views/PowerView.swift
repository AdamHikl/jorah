import SwiftUI

/// The kill switch sheet: says exactly what will happen, waits for a yes, then shows each step.
struct PowerView: View {
    @Environment(HUDModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var backupFirst = true

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(model.pausedAt == nil ? "KILL SWITCH" : "JORAH IS PAUSED")
                .font(.system(size: 14, weight: .bold, design: .monospaced))
                .tracking(4)
                .foregroundStyle(model.pausedAt == nil ? Theme.red : Theme.amber)

            if model.powerBusy {
                Text("Working. Do not quit the HUD until this finishes.")
                    .font(.system(size: 12)).foregroundStyle(Theme.amber)
            } else if let pausedAt = model.pausedAt {
                resumeBody(pausedAt)
            } else {
                pauseBody
            }

            if !model.powerLog.isEmpty {
                ScrollViewReader { proxy in
                    ScrollView {
                        VStack(alignment: .leading, spacing: 2) {
                            ForEach(Array(model.powerLog.enumerated()), id: \.offset) { index, line in
                                Text(line)
                                    .font(Theme.mono(11))
                                    .foregroundStyle(line.hasPrefix("FAILED") ? Theme.red : Theme.text)
                                    .frame(maxWidth: .infinity, alignment: .leading)
                                    .textSelection(.enabled)
                                    .id(index)
                            }
                        }
                    }
                    .frame(height: 170)
                    .padding(8)
                    .overlay(Rectangle().stroke(Theme.stroke, lineWidth: 0.5))
                    .onChange(of: model.powerLog.count) {
                        proxy.scrollTo(model.powerLog.count - 1, anchor: .bottom)
                    }
                }
            }

            HStack {
                Button("Check what is running") { model.runPower(.status) }
                    .disabled(model.powerBusy)
                Spacer()
                Button("Close") { dismiss() }.disabled(model.powerBusy)
            }
        }
        .padding(22)
        .frame(width: 560)
        .background(Theme.background)
        .preferredColorScheme(.dark)
    }

    private var pauseBody: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("This frees the PC's GPU, memory and CPU by stopping Jorah there. In order:")
                .font(.system(size: 12)).foregroundStyle(Theme.text)
            step("1", backupFirst ? "Save: make a verified backup of Jorah's state (a few minutes)" : "Save: skipped")
            step("2", "Stop the Gateway, both voice services and agentmemory cleanly")
            step("3", "Stop the jorah WSL distro and turn off the task that restarts it")
            step("4", "End Ollama's processes on Windows")
            Toggle("Make the verified backup first", isOn: $backupFirst)
                .font(.system(size: 12))
            VStack(alignment: .leading, spacing: 4) {
                if !model.activeRuns.isEmpty {
                    warning("\(model.activeRuns.count) run\(model.activeRuns.count == 1 ? " is" : "s are") in progress and will be cut off.")
                }
                warning("While paused, Telegram, the iPhone, voice and scheduled jobs get no answer. Messages sent meanwhile may all be answered at once on resume.")
                warning("Other WSL distros are left running. Ollama is not started again on resume.")
            }
            Button("Pause Jorah on the PC now") {
                model.runPower(.pause, backup: backupFirst)
            }
            .keyboardShortcut(.defaultAction)
            .tint(Theme.red)
        }
    }

    private func resumeBody(_ pausedAt: Date) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Paused from this Mac at \(pausedAt.formatted(date: .abbreviated, time: .shortened)). Whether it is still paused is unknown until you check.")
                .font(.system(size: 12)).foregroundStyle(Theme.text)
                .fixedSize(horizontal: false, vertical: true)
            step("1", "Turn the restart task back on and start the jorah distro")
            step("2", "Wait for the Gateway, then list each service's state")
            step("3", "Reconnect the HUD")
            Button("Resume Jorah") { model.runPower(.resume) }
                .keyboardShortcut(.defaultAction)
        }
    }

    private func step(_ number: String, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(number).font(Theme.label(10)).foregroundStyle(Theme.accent).frame(width: 14)
            Text(text).font(.system(size: 12)).foregroundStyle(Theme.text)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func warning(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 6) {
            Image(systemName: "exclamationmark.triangle").font(.system(size: 10)).foregroundStyle(Theme.amber)
            Text(text).font(.system(size: 11)).foregroundStyle(Theme.dim)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}
