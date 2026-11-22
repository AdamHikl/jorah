import XCTest
@testable import HUDCore

final class BrainLaneTests: XCTestCase {
    /// brain-lane.sh status on the PC, 2026-11-21, after the switch to the key.
    private let status = """
    Gateway: active
    Claude models for main, heartbeats and Dreaming: 11 on the API key, 0 on the Max login
    deep (Opus): API key
    Default key order: anthropic:jorah-store
    main key order: anthropic:jorah-store
    deep key order: anthropic:jorah-store
    background: API key, on both lanes
    LANE: api
    """.components(separatedBy: "\n")

    func testReadsTheLaneFromARealStatus() {
        XCTAssertEqual(BrainLaneParsing.lane(in: status), .api)
        XCTAssertNil(BrainLaneParsing.probe(in: status))
    }

    func testTheLastLaneLineWins() {
        let lines = ["1/6 Checking", "Now: max", "LANE: max", "6/6 Validating", "LANE: api\r", "SWITCHED to api."]
        XCTAssertEqual(BrainLaneParsing.lane(in: lines), .api)
    }

    func testEveryLaneAndAnythingElse() {
        XCTAssertEqual(BrainLaneParsing.lane(in: ["LANE: max"]), .max)
        XCTAssertEqual(BrainLaneParsing.lane(in: ["LANE: mixed"]), .mixed)
        XCTAssertEqual(BrainLaneParsing.lane(in: ["LANE: unknown"]), .unknown)
        XCTAssertEqual(BrainLaneParsing.lane(in: ["LANE: API"]), .unknown)
        XCTAssertEqual(BrainLaneParsing.lane(in: ["LANE:"]), .unknown)
        XCTAssertEqual(BrainLaneParsing.lane(in: ["  LANE: max (checked)"]), .max)
        XCTAssertEqual(BrainLaneParsing.lane(in: ["The lane is LANE: api"]), .unknown)
    }

    func testNoLaneLineIsUnknown() {
        XCTAssertEqual(BrainLaneParsing.lane(in: []), .unknown)
        XCTAssertEqual(BrainLaneParsing.lane(in: ["FAILED: can't reach the PC over SSH"]), .unknown)
    }

    func testProbe() {
        let lines = ["Test turn on main (session lane-probe-1).", "  reply: PROBE-OK",
                     "  runner: embedded, credential: profile, model: claude-haiku-5-5", "PROBE: api", "LANE: api"]
        XCTAssertEqual(BrainLaneParsing.probe(in: lines), "api")
        XCTAssertEqual(BrainLaneParsing.probe(in: ["PROBE: failed"]), "failed")
    }
}
