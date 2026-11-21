import Foundation
import XCTest
@testable import HUDCore

final class ApprovalsTests: XCTestCase {
    private func parse(_ json: String) -> Any? {
        try? JSONSerialization.jsonObject(with: Data(json.utf8), options: [.fragmentsAllowed])
    }

    /// The shape `plugin.approval.list` returns on OpenClaw 2026.10.9, as the guard's card fills it.
    private let guardList = """
    [{"id":"plugin:abc123","approvalKind":"plugin","createdAtMs":1763700000000,"expiresAtMs":1763700300000,
      "request":{"title":"Install uv","description":"toolbox_install tb-cf6866267c: uv 0.13.8",
                 "severity":"warning","allowedDecisions":["allow-once","deny"],
                 "pluginId":"jorah-guard","toolName":"toolbox_install","agentId":"main",
                 "sessionKey":"agent:main:main","approvalReviewerDeviceIds":["dev1"],
                 "scope":{"kind":"install","target":"uv"},"twoPhase":true,"extra":null}}]
    """

    func testParsesGuardCard() throws {
        let cards = try XCTUnwrap(ApprovalParsing.cards(fromList: parse(guardList)))
        XCTAssertEqual(cards.count, 1)
        let card = cards[0]
        XCTAssertEqual(card.id, "plugin:abc123")
        XCTAssertEqual(card.title, "Install uv")
        XCTAssertEqual(card.description, "toolbox_install tb-cf6866267c: uv 0.13.8")
        XCTAssertEqual(card.severity, "warning")
        XCTAssertEqual(card.offeredDecisions, ["allow-once", "deny"])
        XCTAssertEqual(card.expiresAt, Date(timeIntervalSince1970: 1763700300))
        let names = card.fields.map(\.name)
        XCTAssertEqual(names, names.sorted())
        XCTAssertTrue(names.contains("toolName"))
        XCTAssertTrue(names.contains("scope.kind"))
        XCTAssertFalse(names.contains("title"))
        XCTAssertFalse(names.contains("extra"), "null fields are dropped")
        XCTAssertEqual(card.fields.first { $0.name == "twoPhase" }?.value, "true")
        XCTAssertEqual(card.fields.first { $0.name == "approvalReviewerDeviceIds" }?.value, "dev1")
    }

    func testNeverOffersAllowAlways() throws {
        let json = #"[{"id":"x","request":{"title":"t","allowedDecisions":["allow-always","allow-once","deny"]}}]"#
        let card = try XCTUnwrap(ApprovalParsing.cards(fromList: parse(json))?.first)
        XCTAssertEqual(card.offeredDecisions, ["allow-once", "deny"])
        let now = Date()
        XCTAssertFalse(ApprovalRules.mayAnswer(card: card, decision: "allow-always", firstShownAt: now.addingTimeInterval(-60), now: now))
    }

    func testOnlyDecisionsTheCardOffers() throws {
        let json = #"[{"id":"x","request":{"title":"t","allowedDecisions":["deny"]}}]"#
        let card = try XCTUnwrap(ApprovalParsing.cards(fromList: parse(json))?.first)
        XCTAssertEqual(card.offeredDecisions, ["deny"])
        let now = Date()
        XCTAssertFalse(ApprovalRules.mayAnswer(card: card, decision: "allow-once", firstShownAt: now.addingTimeInterval(-60), now: now))
        XCTAssertTrue(ApprovalRules.mayAnswer(card: card, decision: "deny", firstShownAt: now.addingTimeInterval(-60), now: now))
    }

    func testHoldAfterACardAppears() throws {
        let card = try XCTUnwrap(ApprovalParsing.cards(fromList: parse(guardList))?.first)
        let shown = Date(timeIntervalSince1970: 1763700010)
        XCTAssertFalse(ApprovalRules.mayAnswer(card: card, decision: "allow-once", firstShownAt: shown, now: shown.addingTimeInterval(0.4)))
        XCTAssertTrue(ApprovalRules.mayAnswer(card: card, decision: "allow-once", firstShownAt: shown, now: shown.addingTimeInterval(2)))
    }

    func testExpiredCardCannotBeAnswered() throws {
        let card = try XCTUnwrap(ApprovalParsing.cards(fromList: parse(guardList))?.first)
        let after = Date(timeIntervalSince1970: 1763700301)
        XCTAssertTrue(card.isExpired(at: after))
        XCTAssertEqual(card.secondsLeft(at: after), 0)
        XCTAssertEqual(card.secondsLeft(at: Date(timeIntervalSince1970: 1763700240)), 60)
        XCTAssertFalse(ApprovalRules.mayAnswer(card: card, decision: "deny", firstShownAt: .distantPast, now: after))
    }

    func testStripsControlAndDirectionCharacters() {
        // Right-to-left override, zero-width space, bell, escape: none may reach the screen.
        let text = "allow \u{202E}gnp.exe\u{202C} now\u{200B}\u{0007}\u{001B}[31m"
        XCTAssertEqual(PlainText.clean(text, limit: 100), "allow gnp.exe now[31m")
    }

    func testMarkdownAndLinksStayLiteral() throws {
        let json = #"[{"id":"x","request":{"title":"[click](https://evil.example)","description":"**yes** <b>ok</b>"}}]"#
        let card = try XCTUnwrap(ApprovalParsing.cards(fromList: parse(json))?.first)
        XCTAssertEqual(card.title, "[click](https://evil.example)")
        XCTAssertEqual(card.description, "**yes** <b>ok</b>")
    }

    func testClipsLongText() {
        let long = String(repeating: "a", count: 500)
        let clipped = PlainText.clean(long, limit: 300)
        XCTAssertEqual(clipped.count, 301)
        XCTAssertTrue(clipped.hasSuffix("…"))
    }

    func testRejectsNonList() {
        XCTAssertNil(ApprovalParsing.cards(fromList: parse(#"{"error":"x"}"#)))
        XCTAssertEqual(ApprovalParsing.cards(fromList: parse(#"[{"noid":1}]"#))?.count, 0)
    }

    func testResolvedEventId() {
        XCTAssertEqual(ApprovalParsing.resolvedId(fromEvent: parse(#"{"id":"plugin:1","decision":"deny"}"#)), "plugin:1")
        XCTAssertNil(ApprovalParsing.resolvedId(fromEvent: parse(#"{"decision":"deny"}"#)))
    }
}
