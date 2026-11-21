import AppKit
import HUDCore
import SwiftUI

/// Jorah's approval cards (ADR 0007). Every string from a card is drawn with `Text(verbatim:)`,
/// so Markdown and links in it stay literal text. The two buttons are the only way an answer
/// leaves the HUD: no keyboard shortcut, no default button, not focusable, held for
/// `ApprovalRules.holdSeconds` after a card appears. Telegram keeps getting the same cards, and
/// the first answer anywhere wins.
struct ApprovalsPanel: View {
    @Environment(HUDModel.self) private var model

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            status
            if !model.approvals.isEmpty {
                ScrollView {
                    VStack(spacing: 8) {
                        ForEach(model.approvals) { card in
                            ApprovalCardView(card: card)
                        }
                    }
                }
                .frame(maxHeight: 380)
                .fixedSize(horizontal: false, vertical: true)
            }
            if let note = model.approvalNote {
                Text(verbatim: note).font(Theme.mono(10)).foregroundStyle(Theme.dim).lineLimit(1)
            }
        }
        .frame(maxWidth: 520)
    }

    @ViewBuilder private var status: some View {
        if model.isDemo {
            line("CARDS · DEMO DATA, BUTTONS OFF", Theme.amber)
        } else if model.phase != .connected {
            line("CARDS UNKNOWN · NOT LINKED · ANSWER IN TELEGRAM", Theme.red)
        } else if !model.canAnswerApprovals {
            VStack(alignment: .leading, spacing: 6) {
                HStack(spacing: 8) {
                    line("THIS HUD CAN'T ANSWER CARDS · NO operator.approvals · ANSWER IN TELEGRAM", Theme.amber)
                    if model.cardAccessRequestId == nil {
                        Button("Ask for card access") { model.requestCardAccess() }
                            .font(Theme.label(9))
                            .help("Files a request to add operator.approvals to this HUD. Nothing changes until you approve it on the PC.")
                    }
                }
                if let requestId = model.cardAccessRequestId {
                    let command = "openclaw --profile jorah devices approve \(requestId)"
                    Text(verbatim: "Waiting for you. On the PC, as Jorah's user, check the request shows \"Jorah HUD\" asking for operator.approvals, operator.read, operator.write, then run:")
                        .font(.system(size: 11)).foregroundStyle(Theme.text)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack {
                        Text(verbatim: command).font(Theme.mono(10)).foregroundStyle(Theme.text).textSelection(.enabled)
                        Button("Copy") {
                            NSPasteboard.general.clearContents()
                            NSPasteboard.general.setString(command, forType: .string)
                        }
                        .font(Theme.label(9))
                    }
                }
                if let error = model.cardAccessError {
                    Text(verbatim: error).font(Theme.mono(10)).foregroundStyle(Theme.red)
                }
            }
        } else if let error = model.approvalsError {
            line(error.uppercased() + " · ANSWER IN TELEGRAM", Theme.red)
        } else if model.approvalsAsOf == nil {
            line("CARDS UNKNOWN · CHECKING", Theme.dim)
        } else if model.approvals.isEmpty {
            line("NO CARDS WAITING", Theme.dim)
        } else {
            line("\(model.approvals.count) CARD\(model.approvals.count == 1 ? "" : "S") WAITING FOR YOU", Theme.amber)
        }
    }

    private func line(_ text: String, _ color: Color) -> some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 6, height: 6)
            Text(verbatim: text).font(Theme.label(9)).foregroundStyle(color)
                .fixedSize(horizontal: false, vertical: true)
        }
        .accessibilityElement(children: .combine)
    }
}

struct ApprovalCardView: View {
    @Environment(HUDModel.self) private var model
    let card: ApprovalCard

    var body: some View {
        TimelineView(.periodic(from: .now, by: 0.5)) { timeline in
            let now = timeline.date
            let expired = card.isExpired(at: now)
            VStack(alignment: .leading, spacing: 7) {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text(verbatim: "APPROVAL").font(Theme.label(9)).foregroundStyle(severityColor)
                    if let severity = card.severity {
                        Text(verbatim: severity.uppercased()).font(Theme.label(8)).foregroundStyle(severityColor)
                    }
                    Spacer()
                    Text(verbatim: timeLeft(now)).font(Theme.mono(10))
                        .foregroundStyle(expired ? Theme.red : Theme.dim)
                }
                Text(verbatim: card.title)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(Theme.text)
                    .textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
                if !card.description.isEmpty {
                    Text(verbatim: card.description)
                        .font(.system(size: 12))
                        .foregroundStyle(Theme.text)
                        .textSelection(.enabled)
                        .fixedSize(horizontal: false, vertical: true)
                }
                VStack(alignment: .leading, spacing: 2) {
                    ForEach(Array(card.fields.enumerated()), id: \.offset) { _, field in
                        HStack(alignment: .firstTextBaseline, spacing: 6) {
                            Text(verbatim: field.name).foregroundStyle(Theme.dim)
                                .frame(width: 150, alignment: .leading)
                            Text(verbatim: field.value).foregroundStyle(Theme.text)
                                .textSelection(.enabled)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        .font(Theme.mono(10))
                    }
                    HStack(alignment: .firstTextBaseline, spacing: 6) {
                        Text(verbatim: "id").foregroundStyle(Theme.dim).frame(width: 150, alignment: .leading)
                        Text(verbatim: card.id).foregroundStyle(Theme.dim).textSelection(.enabled)
                    }
                    .font(Theme.mono(10))
                }
                if let error = model.approvalCardErrors[card.id] {
                    Text(verbatim: error).font(Theme.mono(10)).foregroundStyle(Theme.red)
                        .fixedSize(horizontal: false, vertical: true)
                }
                HStack(spacing: 10) {
                    ForEach(card.offeredDecisions, id: \.self) { decision in
                        Button {
                            model.answerApprovalFromClick(id: card.id, decision: decision)
                        } label: {
                            Text(verbatim: decision == "deny" ? "Deny" : "Allow once")
                                .font(Theme.label(11))
                                .frame(minWidth: 90)
                        }
                        .tint(decision == "deny" ? Theme.red : Theme.green)
                        .focusable(false)
                        .disabled(!canClick(decision, now: now))
                        .accessibilityLabel(decision == "deny" ? "Deny \(card.title)" : "Allow once: \(card.title)")
                    }
                    if model.approvalBusy.contains(card.id) {
                        ProgressView().controlSize(.mini)
                    }
                    Spacer()
                    Text(verbatim: "also in Telegram · first answer wins").font(Theme.label(8)).foregroundStyle(Theme.dim)
                }
            }
            .padding(10)
            .background(Theme.surface, in: RoundedRectangle(cornerRadius: 8))
            .overlay(RoundedRectangle(cornerRadius: 8).stroke(severityColor.opacity(0.7), lineWidth: 1))
            .opacity(expired ? 0.5 : 1)
        }
    }

    private func canClick(_ decision: String, now: Date) -> Bool {
        guard !model.isDemo, model.phase == .connected, model.canAnswerApprovals,
              !model.approvalBusy.contains(card.id),
              let shown = model.approvalFirstShown[card.id]
        else { return false }
        return ApprovalRules.mayAnswer(card: card, decision: decision, firstShownAt: shown, now: now)
    }

    private func timeLeft(_ now: Date) -> String {
        guard let left = card.secondsLeft(at: now) else { return "time left unknown" }
        if left == 0 { return "expired" }
        return String(format: "%d:%02d left", left / 60, left % 60)
    }

    private var severityColor: Color {
        switch card.severity {
        case "critical": return Theme.red
        case "info": return Theme.accent
        default: return Theme.amber
        }
    }
}
