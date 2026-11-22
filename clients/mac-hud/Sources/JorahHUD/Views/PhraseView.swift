import HUDCore
import SwiftUI

/// Sheet to check, set, change, or remove Adam's voice confirmation phrase (ADR 0010).
/// The phrase is held only in temporary `@State` fields while typed, cleared immediately after
/// sending, and never written to UserDefaults, Keychain, or logs.
struct PhraseView: View {
    @Environment(HUDModel.self) private var model
    @Environment(\.dismiss) private var dismiss

    @State private var firstPhrase = ""
    @State private var secondPhrase = ""
    @State private var confirmingRemove = false

    var body: some View {
        let match = PhraseInput.check(first: firstPhrase, second: secondPhrase)
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .firstTextBaseline) {
                Text("VOICE CONFIRMATION PHRASE")
                    .font(.system(size: 14, weight: .bold, design: .monospaced))
                    .tracking(4)
                    .foregroundStyle(Theme.accent)
                Spacer()
                statusBadge
            }

            Text(verbatim: "Say it after 'yes' to confirm pushes, pull requests and schedules by voice. Anyone who hears it can use it with a recording of your voice.")
                .font(.system(size: 12))
                .foregroundStyle(Theme.text)
                .fixedSize(horizontal: false, vertical: true)

            if model.phraseState.isLocked {
                Text(verbatim: "Voice confirmation is off after 3 wrong phrases until you answer a card by click.")
                    .font(Theme.mono(11))
                    .foregroundStyle(Theme.red)
                    .fixedSize(horizontal: false, vertical: true)
            }

            VStack(alignment: .leading, spacing: 10) {
                VStack(alignment: .leading, spacing: 4) {
                    Text("NEW PHRASE OR PIN").font(Theme.label(9)).tracking(1.2).foregroundStyle(Theme.dim)
                    SecureField("Enter phrase or PIN", text: $firstPhrase)
                        .textFieldStyle(.roundedBorder)
                        .disabled(model.phraseBusy || model.isDemo)
                }
                VStack(alignment: .leading, spacing: 4) {
                    Text("ENTER IT AGAIN").font(Theme.label(9)).tracking(1.2).foregroundStyle(Theme.dim)
                    SecureField("Re-enter to confirm", text: $secondPhrase)
                        .textFieldStyle(.roundedBorder)
                        .disabled(model.phraseBusy || model.isDemo)
                }
                if match == .mismatch && !secondPhrase.isEmpty {
                    Text(verbatim: "The two entries do not match.")
                        .font(Theme.mono(10))
                        .foregroundStyle(Theme.red)
                }
                Text(verbatim: "Say numbers digit by digit, like 'four seven one nine'.")
                    .font(.system(size: 11))
                    .foregroundStyle(Theme.dim)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if let error = model.phraseError {
                Text(verbatim: error)
                    .font(Theme.mono(11))
                    .foregroundStyle(Theme.red)
                    .fixedSize(horizontal: false, vertical: true)
            }

            if confirmingRemove {
                VStack(alignment: .leading, spacing: 8) {
                    Text(verbatim: "Remove the voice confirmation phrase? Cards that leave the PC will need a tap until you set a new one.")
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.amber)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 10) {
                        Button("Confirm remove", role: .destructive) {
                            confirmingRemove = false
                            firstPhrase = ""
                            secondPhrase = ""
                            model.clearVoicePhrase()
                        }
                        .tint(Theme.red)
                        .disabled(model.phraseBusy || model.isDemo)
                        Button("Cancel") {
                            confirmingRemove = false
                        }
                    }
                }
                .padding(10)
                .overlay(Rectangle().stroke(Theme.red.opacity(0.5), lineWidth: 0.75))
            }

            HStack(spacing: 10) {
                Button("Save") {
                    guard case .matched(let phrase) = match else { return }
                    firstPhrase = ""
                    secondPhrase = ""
                    confirmingRemove = false
                    model.setVoicePhrase(phrase)
                }
                .disabled(!match.isValid || model.phraseBusy || model.isDemo)

                Button("Remove", role: .destructive) {
                    confirmingRemove = true
                }
                .disabled(model.phraseBusy || model.isDemo || model.phraseState.isSet == false || confirmingRemove)

                Button("Check status") {
                    confirmingRemove = false
                    model.requestVoicePhraseStatus()
                }
                .disabled(model.phraseBusy || model.isDemo)

                if model.phraseBusy {
                    ProgressView().controlSize(.mini)
                }

                Spacer()
                Button("Close") { dismiss() }
            }
        }
        .padding(22)
        .frame(width: 520)
        .background(Theme.background)
        .preferredColorScheme(.dark)
        .onAppear {
            if !model.isDemo && !model.phraseBusy {
                model.requestVoicePhraseStatus()
            }
        }
        .onDisappear {
            firstPhrase = ""
            secondPhrase = ""
            confirmingRemove = false
        }
    }

    private var statusBadge: some View {
        HStack(spacing: 6) {
            Circle().fill(statusColor).frame(width: 6, height: 6)
            Text(verbatim: model.phraseBusy ? "CHECKING…" : model.phraseState.summaryText.uppercased())
                .font(Theme.label(10))
                .foregroundStyle(statusColor)
        }
        .accessibilityElement(children: .combine)
    }

    private var statusColor: Color {
        if model.phraseBusy { return Theme.dim }
        if model.phraseState.isLocked { return Theme.red }
        switch model.phraseState {
        case .set: return Theme.green
        case .notSet, .unknown: return Theme.dim
        }
    }
}
