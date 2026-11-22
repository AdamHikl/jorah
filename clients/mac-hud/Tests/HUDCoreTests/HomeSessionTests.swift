import XCTest
@testable import HUDCore

final class HomeSessionTests: XCTestCase {
    func testHomeAndConversationCreateParams() {
        XCTAssertEqual(
            HomeSessionRules.homeCreateParams(idempotencyKey: "idem-1"),
            ["label": "jorah-hud-home", "idempotencyKey": "idem-1"]
        )

        let withHome = HomeSessionRules.conversationCreateParams(
            idempotencyKey: "idem-2",
            homeSessionKey: "  agent:main:dashboard:home-uuid  "
        )
        XCTAssertTrue(withHome.hasParent)
        XCTAssertEqual(withHome.params, [
            "idempotencyKey": "idem-2",
            "parentSessionKey": "agent:main:dashboard:home-uuid",
        ])

        for blank in [nil, "", "   \n"] {
            let fallback = HomeSessionRules.conversationCreateParams(
                idempotencyKey: "idem-3",
                homeSessionKey: blank
            )
            XCTAssertFalse(fallback.hasParent)
            XCTAssertEqual(fallback.params, ["idempotencyKey": "idem-3"])
        }
    }

    func testExtractsKeysFromCreateAndResolveResults() {
        XCTAssertEqual(
            HomeSessionRules.sessionKey(fromCreateResult: ["key": "agent:main:dashboard:1"]),
            "agent:main:dashboard:1"
        )
        XCTAssertEqual(
            HomeSessionRules.sessionKey(fromCreateResult: ["session": ["key": "agent:main:dashboard:2"]]),
            "agent:main:dashboard:2"
        )
        XCTAssertEqual(
            HomeSessionRules.sessionKey(fromCreateResult: ["sessionKey": "agent:main:dashboard:3"]),
            "agent:main:dashboard:3"
        )
        XCTAssertNil(HomeSessionRules.sessionKey(fromCreateResult: ["key": "   "]))
        XCTAssertNil(HomeSessionRules.sessionKey(fromCreateResult: "not-a-dict"))

        XCTAssertEqual(
            HomeSessionRules.resolvedKey(fromResolveResult: ["ok": true, "key": "agent:main:dashboard:4"]),
            "agent:main:dashboard:4"
        )
        XCTAssertEqual(
            HomeSessionRules.resolvedKey(fromResolveResult: ["key": "agent:main:dashboard:5"]),
            "agent:main:dashboard:5"
        )
        XCTAssertNil(HomeSessionRules.resolvedKey(fromResolveResult: ["ok": false, "key": "agent:main:dashboard:5"]))
        XCTAssertNil(HomeSessionRules.resolvedKey(fromResolveResult: ["ok": true]))
    }

    func testHidingRuleByKeyOrLabel() {
        let homeKey = "agent:main:dashboard:home-1"
        XCTAssertTrue(HomeSessionRules.isHomeSession(key: homeKey, label: nil, homeSessionKey: homeKey))
        XCTAssertTrue(HomeSessionRules.isHomeSession(key: "agent:main:dashboard:other", label: "jorah-hud-home", homeSessionKey: homeKey))
        XCTAssertTrue(HomeSessionRules.isHomeSession(key: "agent:main:dashboard:other", label: " jorah-hud-home ", homeSessionKey: nil))

        XCTAssertFalse(HomeSessionRules.isHomeSession(key: "agent:main:main", label: nil, homeSessionKey: homeKey))
        XCTAssertFalse(HomeSessionRules.isHomeSession(key: "agent:main:dashboard:chat-1", label: "JORAH-HUD-HOME", homeSessionKey: nil))
        XCTAssertFalse(HomeSessionRules.isHomeSession(key: "", label: nil, homeSessionKey: "   "))
    }

    func testFindsSessionKeyByLabelFromSessionsList() {
        let wrapped: [String: Any] = [
            "sessions": [
                ["key": "agent:main:main", "title": "Main"],
                ["key": "   ", "label": "jorah-hud-home"],
                ["key": "agent:main:dashboard:other", "label": "JORAH-HUD-HOME"],
                ["key": "agent:main:dashboard:home-2", "label": "jorah-hud-home"],
            ],
        ]
        XCTAssertEqual(
            HomeSessionRules.findSessionKey(inSessionsList: wrapped),
            "agent:main:dashboard:home-2"
        )

        let bareArray: [[String: Any]] = [
            ["key": "agent:main:dashboard:home-3", "label": " jorah-hud-home "],
        ]
        XCTAssertEqual(
            HomeSessionRules.findSessionKey(inSessionsList: bareArray),
            "agent:main:dashboard:home-3"
        )

        XCTAssertNil(HomeSessionRules.findSessionKey(inSessionsList: ["sessions": [["key": "agent:main:main"]]]))
        XCTAssertNil(HomeSessionRules.findSessionKey(inSessionsList: "not-a-list"))
    }

    func testMatchesLabelAlreadyInUseErrors() {
        XCTAssertTrue(HomeSessionRules.isLabelAlreadyInUseError("label already in use: jorah-hud-home"))
        XCTAssertTrue(HomeSessionRules.isLabelAlreadyInUseError("INVALID_REQUEST: label already in use: jorah-hud-home"))
        XCTAssertTrue(HomeSessionRules.isLabelAlreadyInUseError("Label Already In Use"))
        XCTAssertFalse(HomeSessionRules.isLabelAlreadyInUseError("INVALID_REQUEST: permission denied"))
        XCTAssertFalse(HomeSessionRules.isLabelAlreadyInUseError(""))
    }
}
