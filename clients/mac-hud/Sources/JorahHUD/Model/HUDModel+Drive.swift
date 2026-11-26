import AppKit
import Foundation
import HUDCore

/// Drive mode (ADR 0012): Adam switches it on with the ⌨ button in the HUD's top bar (or the menu
/// bar item), and until Adam switches it off, forgets the pairing or quits the HUD, a command line on
/// this Mac can send messages in the open conversation, read it and its cards, and deny cards. It
/// can't allow a card, pair, pause or resume the PC, switch the brain or model, or open a
/// conversation. While it's on, the button and a bar are orange and every line it sent carries ⌨.
extension HUDModel {
    var isDriving: Bool { driveSince != nil && driveServer != nil }

    /// Only Adam's clicks call this: the top bar's ⌨ button and the menu bar item.
    func toggleDrive() {
        if driveSince == nil { armDrive() } else { stopDrive(reason: "you switched it off") }
    }

    func armDrive() {
        guard !isDemo else { driveError = "Drive mode is off in the demo."; return }
        stopDrive(reason: nil)
        let server = DriveServer { [weak self] command in
            guard let self else { return ["ok": false, "error": "The HUD is closing."] }
            return await self.drive(command)
        }
        do {
            try server.start()
        } catch {
            driveError = "Drive mode didn't start: \(error)"
            return
        }
        driveServer = server
        driveSince = Date()
        driveError = nil
        driveLog("switched on")
        lines.append(ChatLine(id: UUID().uuidString, role: .notice,
                              text: "Drive mode on: Claude Code can type here as you, read this chat and deny cards until you switch it off. It can't allow cards.",
                              at: Date()))
    }

    /// Ends drive mode and removes the socket. `reason` nil: say nothing (switching on again).
    func stopDrive(reason: String?) {
        driveServer?.stop()
        driveServer = nil
        guard driveSince != nil else { return }
        driveSince = nil
        if let reason {
            driveLog("stopped: \(reason)")
            lines.append(ChatLine(id: UUID().uuidString, role: .notice, text: "Drive mode off: \(reason).", at: Date()))
        }
    }

    /// One request from the socket. Refused unless drive mode is on at this moment.
    func drive(_ command: DriveCommand) async -> [String: Any] {
        guard isDriving else { return ["ok": false, "error": "Drive mode is off. Adam switches it on with the ⌨ button in the HUD's top bar."] }
        switch command {
        case .status:
            return driveStatus()
        case .send(let text):
            let result = await sendFromDrive(text)
            driveLog("send \(result.ok ? "ok" : "refused") (\(text.count) chars): \(text.prefix(300))")
            guard result.ok else { return ["ok": false, "error": result.message] }
            return ["ok": true, "sessionKey": result.message, "runId": result.runId ?? NSNull()]
        case .read(let limit):
            return ["ok": true, "lines": lines.suffix(limit).map(Self.lineJSON), "running": !activeRuns.isEmpty,
                    "sessionKey": currentSessionKey ?? NSNull(),
                    "historyAsOf": historyAsOf.map(Self.iso) ?? NSNull(), "sendError": sendError ?? NSNull()]
        case .cards:
            await refreshApprovals()
            return driveCards()
        case .deny(let id):
            let result = await denyApprovalFromDrive(id: id)
            driveLog("deny \(id) \(result.ok ? "ok" : "refused"): \(result.message)")
            return ["ok": result.ok, result.ok ? "note" : "error": result.message]
        case .wait(let seconds, let sent):
            return await driveWait(seconds: seconds, sent: sent)
        }
    }

    private func driveStatus() -> [String: Any] {
        [
            "ok": true,
            "onSince": driveSince.map(Self.iso) ?? NSNull(),
            "phase": String(describing: phase),
            "sessionKey": currentSessionKey ?? NSNull(),
            "canWrite": canWrite,
            "canAnswerCards": canAnswerApprovals,
            "running": !activeRuns.isEmpty,
            "cards": approvalsError == nil && approvalsAsOf != nil ? approvals.count as Any : NSNull(),
            "gatewayVersion": serverVersion ?? NSNull(),
        ]
    }

    private func driveCards() -> [String: Any] {
        guard canAnswerApprovals else { return ["ok": false, "error": "This HUD has no card access, so its cards are unknown."] }
        if let approvalsError { return ["ok": false, "error": approvalsError] }
        guard let asOf = approvalsAsOf else { return ["ok": false, "error": "Cards unknown: not loaded yet."] }
        let now = Date()
        return ["ok": true, "asOf": Self.iso(asOf), "cards": approvals.map { card -> [String: Any] in
            [
                "id": card.id, "title": card.title, "description": card.description,
                "severity": card.severity ?? NSNull(),
                "fields": card.fields.map { ["name": $0.name, "value": $0.value] },
                "allowedDecisions": card.allowedDecisions,
                "canDeny": card.allowedDecisions.contains("deny"),
                "secondsLeft": card.secondsLeft(at: now) ?? NSNull(),
            ]
        }]
    }

    /// Waits until Jorah has answered `sent` and stopped, a new card shows (the run is waiting on
    /// it), drive mode ends, or `seconds` pass.
    private func driveWait(seconds: Double, sent: String?) async -> [String: Any] {
        let start = Date()
        let cardsBefore = Set(approvals.map(\.id))
        // A card made after the sent line counts too, even if it showed before this wait began.
        let sentAt = sent.flatMap { text in
            lines.last(where: { $0.role == .user && DriveRules.sameText($0.text, text) })?.at
        }?.addingTimeInterval(-2)
        var settledSince: Date?
        while Date().timeIntervalSince(start) < seconds {
            guard isDriving else { return ["ok": false, "error": "Drive mode ended while waiting."] }
            let newCards = approvals.filter { card in
                !cardsBefore.contains(card.id) || (sentAt != nil && (card.createdAt ?? .distantPast) >= sentAt!)
            }
            if !newCards.isEmpty {
                return ["ok": true, "result": "card", "cards": newCards.map { ["id": $0.id, "title": $0.title] }]
            }
            let finished = DriveRules.replyFinished(lines: lines.map(Self.driveLine), sent: sent, running: !activeRuns.isEmpty)
            if finished {
                if let since = settledSince {
                    if Date().timeIntervalSince(since) >= 1.5 { return ["ok": true, "result": "done"] }
                } else {
                    settledSince = Date()
                }
            } else {
                settledSince = nil
            }
            try? await Task.sleep(for: .milliseconds(250))
        }
        return ["ok": true, "result": "timeout"]
    }

    /// History lines for messages sent through drive mode get their ⌨ mark back.
    func withDriveMarks(_ loaded: [ChatLine]) -> [ChatLine] {
        guard !driveSent.isEmpty else { return loaded }
        var out = loaded
        var used = Set<Int>()
        for index in out.indices.reversed() where out[index].role == .user && !out[index].viaDrive {
            if let match = driveSent.indices.reversed().first(where: { !used.contains($0) && DriveRules.sameText(out[index].text, driveSent[$0]) }) {
                used.insert(match)
                out[index].viaDrive = true
            }
        }
        return out
    }

    private static func driveLine(_ line: ChatLine) -> DriveLine {
        let role: DriveLine.Role = switch line.role {
        case .user: .user
        case .assistant: .assistant
        case .notice: .notice
        }
        return DriveLine(role: role, text: line.text, streaming: line.streaming)
    }

    private static func lineJSON(_ line: ChatLine) -> [String: Any] {
        [
            "role": driveLine(line).role.rawValue, "text": line.text, "at": line.at.map(iso) ?? NSNull(),
            "streaming": line.streaming, "viaDrive": line.viaDrive, "pictures": line.images.count,
        ]
    }

    static func iso(_ date: Date) -> String { date.formatted(.iso8601) }

    /// A local record of what drive mode did, in the HUD's private folder (mode 600).
    func driveLog(_ entry: String) {
        let path = DriveServer.logPath
        let line = "\(Self.iso(Date())) \(entry.replacingOccurrences(of: "\n", with: " "))\n"
        if !FileManager.default.fileExists(atPath: path) {
            FileManager.default.createFile(atPath: path, contents: nil, attributes: [.posixPermissions: 0o600])
        }
        guard let handle = FileHandle(forWritingAtPath: path) else { return }
        defer { try? handle.close() }
        _ = try? handle.seekToEnd()
        try? handle.write(contentsOf: Data(line.utf8))
    }
}
