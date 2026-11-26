import Foundation
import XCTest
@testable import HUDCore

/// Drive mode (ADR 0012): what the socket accepts, what it never accepts, and when it may deny.
final class DriveTests: XCTestCase {
    private func parse(_ json: String) -> Result<DriveCommand, DriveRefusal> {
        DriveRequest.parse(Data(json.utf8))
    }

    private func command(_ json: String) -> DriveCommand? {
        if case .success(let command) = parse(json) { return command }
        return nil
    }

    private func refusal(_ json: String) -> String? {
        if case .failure(let refusal) = parse(json) { return refusal.message }
        return nil
    }

    func testAcceptsEachCommand() {
        XCTAssertEqual(command(#"{"cmd":"status"}"#), .status)
        XCTAssertEqual(command(#"{"cmd":"cards"}"#), .cards)
        XCTAssertEqual(command(#"{"cmd":"send","text":"  /jorah-status \n"}"#), .send(text: "/jorah-status"))
        XCTAssertEqual(command(#"{"cmd":"read"}"#), .read(limit: DriveRules.defaultReadLines))
        XCTAssertEqual(command(#"{"cmd":"read","limit":3}"#), .read(limit: 3))
        XCTAssertEqual(command(#"{"cmd":"deny","id":"plugin:abc123"}"#), .deny(id: "plugin:abc123"))
        XCTAssertEqual(command(#"{"cmd":"wait"}"#), .wait(seconds: DriveRules.defaultWaitSeconds, sent: nil))
        XCTAssertEqual(command(#"{"cmd":"wait","seconds":30,"sent":"hi"}"#), .wait(seconds: 30, sent: "hi"))
    }

    func testNeverAllowsOrPowerOrModel() {
        for word in ["allow", "allow-once", "allow-always", "approve", "resolve", "answer", "pair", "power",
                     "brain", "model", "new", "kill", "pause", "resume", "ALLOW"] {
            let message = refusal(#"{"cmd":"\#(word)","id":"plugin:abc"}"#)
            XCTAssertNotNil(message, word)
            XCTAssertTrue(message?.contains("only Adam allows cards") == true, word)
        }
        XCTAssertTrue(refusal(#"{"cmd":"shell"}"#)?.contains("Unknown command") == true)
    }

    func testDenyCannotCarryADecision() {
        XCTAssertNotNil(refusal(#"{"cmd":"deny","id":"plugin:abc","decision":"allow-once"}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"send","text":"hi","sessionKey":"agent:main:other"}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"status","x":1}"#))
    }

    func testRefusesBadText() {
        XCTAssertNotNil(refusal(#"{"cmd":"send"}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"send","text":"   "}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"send","text":5}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"send","text":"a\u0000b"}"#))
        let long = String(repeating: "a", count: DriveRules.maxText + 1)
        XCTAssertNotNil(refusal(#"{"cmd":"send","text":"\#(long)"}"#))
        XCTAssertNotNil(command(#"{"cmd":"send","text":"\#(String(repeating: "a", count: DriveRules.maxText))"}"#))
    }

    func testRefusesBadIdsAndNumbers() {
        XCTAssertNotNil(refusal(#"{"cmd":"deny"}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"deny","id":""}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"deny","id":"has space"}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"deny","id":"\#(String(repeating: "x", count: DriveRules.maxCardId + 1))"}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"read","limit":0}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"read","limit":41}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"read","limit":2.5}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"read","limit":true}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"wait","seconds":0}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"wait","seconds":601}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"wait","seconds":false}"#))
        XCTAssertNotNil(refusal(#"{"cmd":"wait","sent":3}"#))
    }

    func testRefusesNonRequests() {
        XCTAssertNotNil(refusal("not json"))
        XCTAssertNotNil(refusal("[]"))
        XCTAssertNotNil(refusal(#"{"text":"hi"}"#))
        let huge = Data(repeating: 0x20, count: DriveRules.maxRequestBytes + 1)
        if case .success = DriveRequest.parse(huge) { XCTFail("an oversized request parsed") }
    }

    func testArmingLastsThirtyMinutes() {
        let click = Date(timeIntervalSince1970: 1_800_000_000)
        let until = DriveRules.armedUntil(clickedAt: click)
        XCTAssertEqual(until.timeIntervalSince(click), 30 * 60)
        XCTAssertTrue(DriveRules.isArmed(until: until, now: click.addingTimeInterval(60)))
        XCTAssertFalse(DriveRules.isArmed(until: until, now: until))
        XCTAssertFalse(DriveRules.isArmed(until: nil, now: click))
    }

    private func card(_ decisions: String, expiresAtMs: Int = 1763700300000) throws -> ApprovalCard {
        let json = #"[{"id":"plugin:x","createdAtMs":1763700000000,"expiresAtMs":\#(expiresAtMs),"request":{"title":"t","allowedDecisions":\#(decisions)}}]"#
        let list = try JSONSerialization.jsonObject(with: Data(json.utf8))
        return try XCTUnwrap(ApprovalParsing.cards(fromList: list)?.first)
    }

    func testMayDenyKeepsTheHoldAndExpiry() throws {
        let shown = Date(timeIntervalSince1970: 1763700010)
        let both = try card(#"["allow-once","deny"]"#)
        XCTAssertFalse(DriveRules.mayDeny(card: both, firstShownAt: shown, now: shown.addingTimeInterval(0.5)))
        XCTAssertTrue(DriveRules.mayDeny(card: both, firstShownAt: shown, now: shown.addingTimeInterval(2)))
        XCTAssertFalse(DriveRules.mayDeny(card: both, firstShownAt: shown, now: Date(timeIntervalSince1970: 1763700301)))
        let allowOnly = try card(#"["allow-once"]"#)
        XCTAssertFalse(DriveRules.mayDeny(card: allowOnly, firstShownAt: shown, now: shown.addingTimeInterval(2)))
    }

    func testSameText() {
        XCTAssertTrue(DriveRules.sameText("  /jorah-status\n", "/jorah-status"))
        XCTAssertTrue(DriveRules.sameText("[Mon 2026-11-25 21:30] save a note", "save a note"))
        XCTAssertFalse(DriveRules.sameText("save a note saying test", "save a note"))
        XCTAssertFalse(DriveRules.sameText("anything", "  "))
    }

    func testReplyFinished() {
        let sent = "save a note"
        let answered: [DriveLine] = [
            .init(role: .user, text: "earlier"), .init(role: .assistant, text: "ok"),
            .init(role: .user, text: sent), .init(role: .assistant, text: "Saved."),
        ]
        XCTAssertTrue(DriveRules.replyFinished(lines: answered, sent: sent, running: false))
        XCTAssertFalse(DriveRules.replyFinished(lines: answered, sent: sent, running: true))
        var streaming = answered
        streaming[3] = .init(role: .assistant, text: "Sav", streaming: true)
        XCTAssertFalse(DriveRules.replyFinished(lines: streaming, sent: sent, running: false))
        XCTAssertFalse(DriveRules.replyFinished(lines: Array(answered.prefix(3)), sent: sent, running: false))
        XCTAssertFalse(DriveRules.replyFinished(lines: Array(answered.prefix(2)), sent: sent, running: false))
        let notice = Array(answered.prefix(3)) + [.init(role: .notice, text: "Careful mode is on until 21:40.")]
        XCTAssertTrue(DriveRules.replyFinished(lines: notice, sent: sent, running: false))
        XCTAssertTrue(DriveRules.replyFinished(lines: [], sent: nil, running: false))
        XCTAssertFalse(DriveRules.replyFinished(lines: [], sent: nil, running: true))
    }
}
