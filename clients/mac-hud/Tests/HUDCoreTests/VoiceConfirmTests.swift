import Foundation
import XCTest
@testable import HUDCore

final class VoiceConfirmTests: XCTestCase {
    func testParsesCardAndSanitisesText() throws {
        let json = """
        {"type":"card","id":"plugin:v1\\u202e","title":"**Push** to [main](https://evil.example)\\u200b",
         "description":"Push branch feat/x\\u0007 to origin","leaves_pc":true,"expires_at_ms":1763700300000,
         "needs_phrase":true,"phrase_set":true}
        """
        guard case .card(let card) = VoiceMessageParsing.parse(json) else {
            return XCTFail("Expected .card")
        }
        XCTAssertEqual(card.id, "plugin:v1")
        XCTAssertEqual(card.title, "**Push** to [main](https://evil.example)")
        XCTAssertEqual(card.description, "Push branch feat/x to origin")
        XCTAssertTrue(card.leavesPC)
        XCTAssertTrue(card.needsPhrase)
        XCTAssertTrue(card.phraseSet)
        XCTAssertEqual(card.expiresAt, Date(timeIntervalSince1970: 1763700300))
        XCTAssertEqual(card.offeredDecisions, ["allow-once", "deny"])
    }

    func testCardRejectsMissingIdAndClipsLongTitle() throws {
        XCTAssertNil(VoiceMessageParsing.parse(#"{"type":"card","title":"Push"}"#))
        XCTAssertNil(VoiceMessageParsing.parse(#"{"type":"card","id":"   ","title":"Push"}"#))

        let longTitle = String(repeating: "x", count: 200)
        let json = #"{"type":"card","id":"c1","title":"\#(longTitle)","leaves_pc":false,"needs_phrase":false,"phrase_set":false}"#
        guard case .card(let card) = VoiceMessageParsing.parse(json) else {
            return XCTFail("Expected .card")
        }
        XCTAssertEqual(card.title.count, ApprovalRules.maxTitle + 1)
        XCTAssertTrue(card.title.hasSuffix("…"))
    }

    func testParsesCardClosed() {
        guard case .cardClosed(let id, let outcome) = VoiceMessageParsing.parse(
            #"{"type":"card_closed","id":"plugin:1","outcome":"allowed"}"#
        ) else {
            return XCTFail("Expected .cardClosed")
        }
        XCTAssertEqual(id, "plugin:1")
        XCTAssertEqual(outcome, "allowed")
        XCTAssertNil(VoiceMessageParsing.parse(#"{"type":"card_closed","outcome":"denied"}"#))
    }

    func testParsesPhraseStatusAndError() {
        guard case .phraseStatus(let setStatus) = VoiceMessageParsing.parse(
            #"{"type":"phrase_status","set":true,"words":4,"locked":false}"#
        ) else {
            return XCTFail("Expected .phraseStatus")
        }
        XCTAssertEqual(setStatus, PhraseStatus(isSet: true, words: 4, locked: false))
        XCTAssertEqual(PhraseState(status: setStatus).summaryText, "set, 4 words")

        guard case .phraseStatus(let unsetStatus) = VoiceMessageParsing.parse(
            #"{"type":"phrase_status","set":false,"words":null,"locked":false}"#
        ) else {
            return XCTFail("Expected .phraseStatus")
        }
        XCTAssertEqual(unsetStatus, PhraseStatus(isSet: false, words: nil, locked: false))
        XCTAssertEqual(PhraseState(status: unsetStatus).summaryText, "not set")

        guard case .phraseStatus(let lockedStatus) = VoiceMessageParsing.parse(
            #"{"type":"phrase_status","set":true,"words":3,"locked":true}"#
        ) else {
            return XCTFail("Expected .phraseStatus")
        }
        XCTAssertTrue(lockedStatus.locked)
        XCTAssertEqual(PhraseState(status: lockedStatus).summaryText, "locked")
        XCTAssertEqual(PhraseState(status: lockedStatus).isSet, true)

        guard case .phraseError(let reason) = VoiceMessageParsing.parse(
            #"{"type":"phrase_error","reason":"Use at least 3 words or 6 digits."}"#
        ) else {
            return XCTFail("Expected .phraseError")
        }
        XCTAssertEqual(reason, "Use at least 3 words or 6 digits.")

        // Non-boolean `set` is rejected; unknown type is ignored cleanly.
        XCTAssertNil(VoiceMessageParsing.parse(#"{"type":"phrase_status","set":1,"words":3,"locked":false}"#))
        XCTAssertEqual(VoiceMessageParsing.parse(#"{"type":"something_new","x":1}"#), .unknown)
        XCTAssertNil(VoiceMessageParsing.parse("not json"))

        // Session switch reply parsing.
        XCTAssertEqual(
            VoiceMessageParsing.parse(#"{"type":"session","session_key":"agent:main:main","ok":true}"#),
            .session(ok: true)
        )
        XCTAssertEqual(
            VoiceMessageParsing.parse(#"{"type":"session","session_key":null,"ok":false}"#),
            .session(ok: false)
        )
        XCTAssertNil(VoiceMessageParsing.parse(#"{"type":"session","session_key":"agent:main:main","ok":"yes"}"#))
    }

    func testPhraseStateSummaryVariants() {
        XCTAssertEqual(PhraseState.unknown.summaryText, "unknown")
        XCTAssertNil(PhraseState.unknown.isSet)
        XCTAssertEqual(PhraseState.notSet(locked: false).summaryText, "not set")
        XCTAssertEqual(PhraseState.set(words: 1, locked: false).summaryText, "set, 1 word")
        XCTAssertEqual(PhraseState.set(words: nil, locked: false).summaryText, "set")
        XCTAssertEqual(PhraseState.set(words: 5, locked: true).summaryText, "locked")
    }

    func testVoiceCardHoldExpiryAndLinkClosedRules() {
        let shown = Date(timeIntervalSince1970: 1_763_700_000)
        let expiry = shown.addingTimeInterval(30)
        let card = VoiceCard(
            id: "v1", title: "Push branch", description: "Push to origin",
            leavesPC: true, expiresAt: expiry, needsPhrase: true, phraseSet: true
        )

        XCTAssertFalse(ApprovalRules.mayAnswer(voiceCard: card, decision: "allow-always", firstShownAt: shown, now: shown.addingTimeInterval(5)))
        XCTAssertFalse(ApprovalRules.mayAnswer(voiceCard: card, decision: "allow-once", firstShownAt: shown, now: shown.addingTimeInterval(0.8)))
        XCTAssertTrue(ApprovalRules.mayAnswer(voiceCard: card, decision: "allow-once", firstShownAt: shown, now: shown.addingTimeInterval(1.6)))
        XCTAssertTrue(ApprovalRules.mayAnswer(voiceCard: card, decision: "deny", firstShownAt: shown, now: shown.addingTimeInterval(2.0)))
        XCTAssertFalse(ApprovalRules.mayAnswer(voiceCard: card, decision: "allow-once", firstShownAt: shown, now: shown.addingTimeInterval(2.0), linkOpen: false))
        XCTAssertEqual(card.secondsLeft(at: shown.addingTimeInterval(10)), 20)
        XCTAssertTrue(card.isExpired(at: expiry))
        XCTAssertFalse(ApprovalRules.mayAnswer(voiceCard: card, decision: "deny", firstShownAt: shown, now: expiry.addingTimeInterval(1)))
    }

    func testOutgoingEncoding() {
        let allow = VoiceMessageEncoding.cardDecision(id: "c1", decision: "allow-once")
        XCTAssertEqual(allow?["type"] as? String, "card_decision")
        XCTAssertEqual(allow?["id"] as? String, "c1")
        XCTAssertEqual(allow?["decision"] as? String, "allow-once")

        XCTAssertNil(VoiceMessageEncoding.cardDecision(id: "c1", decision: "allow-always"))
        XCTAssertNil(VoiceMessageEncoding.cardDecision(id: "", decision: "deny"))

        let hello = VoiceMessageEncoding.settingsHello(token: "tok")
        XCTAssertEqual(hello?["type"] as? String, "hello")
        XCTAssertEqual(hello?["purpose"] as? String, "settings")
        XCTAssertNil(VoiceMessageEncoding.settingsHello(token: ""))

        XCTAssertEqual(VoiceMessageEncoding.phraseSet(phrase: "  red river stone  ")?["phrase"] as? String, "red river stone")
        XCTAssertNil(VoiceMessageEncoding.phraseSet(phrase: "   "))
        XCTAssertEqual(VoiceMessageEncoding.phraseStatusRequest()["type"] as? String, "phrase_status_request")
        XCTAssertEqual(VoiceMessageEncoding.phraseClear()["type"] as? String, "phrase_clear")

        let dash = "agent:main:dashboard:01234567-89ab-cdef-0123-456789abcdef"
        let voiceHelloWithKey = VoiceMessageEncoding.hello(token: "tok", bargeIn: false, followUp: true, sessionKey: dash)
        XCTAssertEqual(voiceHelloWithKey?["type"] as? String, "hello")
        XCTAssertEqual(voiceHelloWithKey?["token"] as? String, "tok")
        XCTAssertEqual(voiceHelloWithKey?["barge_in"] as? Bool, false)
        XCTAssertEqual(voiceHelloWithKey?["follow_up"] as? Bool, true)
        XCTAssertEqual(voiceHelloWithKey?["session_key"] as? String, dash)

        let voiceHelloNoKey = VoiceMessageEncoding.hello(token: "tok", bargeIn: false, followUp: false, sessionKey: nil)
        XCTAssertNil(voiceHelloNoKey?["session_key"])
        XCTAssertNil(VoiceMessageEncoding.hello(token: "", bargeIn: false, followUp: false, sessionKey: dash))

        let sessionMsg = VoiceMessageEncoding.session(key: dash)
        XCTAssertEqual(sessionMsg?["type"] as? String, "session")
        XCTAssertEqual(sessionMsg?["session_key"] as? String, dash)
        XCTAssertNil(VoiceMessageEncoding.session(key: ""))
    }

    func testDedupeWithGatewayList() {
        let gw1 = ApprovalCard(
            id: "plugin:shared", title: "Gateway copy", description: "",
            severity: "warning", fields: [], allowedDecisions: ["allow-once", "deny"],
            createdAt: nil, expiresAt: nil
        )
        let vShared = VoiceCard(
            id: "plugin:shared", title: "Voice copy", description: "",
            leavesPC: false, expiresAt: nil, needsPhrase: false, phraseSet: false
        )
        let vOnly = VoiceCard(
            id: "plugin:voice-only", title: "Voice only", description: "",
            leavesPC: true, expiresAt: nil, needsPhrase: true, phraseSet: true
        )

        let deduped = VoiceCardDedupe.uniqueVoiceCards(
            voiceCards: [vShared, vOnly, vOnly],
            gatewayApprovals: [gw1]
        )
        XCTAssertEqual(deduped, [vOnly])
    }

    func testPhraseMatchCheck() {
        XCTAssertEqual(PhraseInput.check(first: "", second: ""), .empty)
        XCTAssertEqual(PhraseInput.check(first: "   ", second: "\n"), .empty)
        XCTAssertFalse(PhraseInput.check(first: "", second: "").isValid)

        XCTAssertEqual(PhraseInput.check(first: "red fox run", second: "red fox"), .mismatch)
        XCTAssertEqual(PhraseInput.check(first: "123456", second: ""), .mismatch)
        XCTAssertFalse(PhraseInput.check(first: "red fox run", second: "red fox").isValid)

        XCTAssertEqual(PhraseInput.check(first: "red fox run", second: "red fox run"), .matched("red fox run"))
        XCTAssertEqual(PhraseInput.check(first: "  red fox run ", second: "red fox run"), .matched("red fox run"))
        XCTAssertTrue(PhraseInput.check(first: "123456", second: "123456").isValid)
        XCTAssertEqual(PhraseInput.check(first: " 123456 ", second: "123456").trimmedPhrase, "123456")
    }
}
