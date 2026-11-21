import Foundation
import HUDCore

/// Made-up frames for `JORAH_HUD_DEMO=1`, pushed through the same handlers as real Gateway frames,
/// so the layout can be checked without a connection. The HUD labels every panel
/// "DEMO DATA" while this runs. Nothing here is ever shown in a real session.
@MainActor
enum DemoFeed {
    static func start(_ model: HUDModel) {
        let now = Date().timeIntervalSince1970 * 1000
        model.applyHello(.object([
            "server": .object(["version": .string("demo")]),
            "auth": .object(["scopes": .array([.string("operator.read")])]),
            "snapshot": .object([
                "uptimeMs": .number(93_784_000),
                "presence": .array([
                    .object(["host": .string("demo-pc"), "mode": .string("gateway"), "platform": .string("linux"), "ts": .number(now)]),
                    .object(["host": .string("demo-phone"), "mode": .string("node"), "platform": .string("ios"), "ts": .number(now)]),
                ]),
                "health": .object([
                    "ok": .bool(true), "ts": .number(now), "heartbeatSeconds": .number(1800),
                    "channelOrder": .array([.string("telegram")]),
                    "plugins": .object(["loaded": .array([]), "errors": .array([])]),
                ]),
                "sessionDefaults": .object(["mainSessionKey": .string("agent:main:main")]),
            ]),
        ]))
        model.sessions = [
            SessionRow(key: "agent:main:main", title: "Main", updatedAt: Date(), active: true, model: nil, totalTokens: nil),
            SessionRow(key: "demo:1", title: "Demo: research thread", updatedAt: Date().addingTimeInterval(-1500), active: false, model: nil, totalTokens: nil),
            SessionRow(key: "demo:2", title: "Demo: morning brief", updatedAt: Date().addingTimeInterval(-30_000), active: false, model: nil, totalTokens: nil),
        ]
        model.sessionsAsOf = Date()
        model.currentModel = "demo/model"
        var running = SessionRow(key: "demo:sub1", title: "Demo: search the changelog", updatedAt: Date(), active: true, model: "demo/small", totalTokens: nil)
        running.status = "running"
        running.startedAt = Date().addingTimeInterval(-42)
        var done = SessionRow(key: "demo:sub2", title: "Demo: summarise three commits", updatedAt: Date(), active: false, model: "demo/small", totalTokens: nil)
        done.status = "done"
        done.startedAt = Date().addingTimeInterval(-300)
        done.endedAt = Date().addingTimeInterval(-262)
        model.subagents = [running, done]
        model.subagentsAsOf = Date()
        model.cron = [
            CronRow(id: "d1", name: "Demo: morning brief", enabled: true, nextRun: Date().addingTimeInterval(40_000), lastRun: nil, lastStatus: "ok", running: false),
            CronRow(id: "d2", name: "Demo: repo watch", enabled: true, nextRun: Date().addingTimeInterval(900), lastRun: nil, lastStatus: "error", running: false),
            CronRow(id: "d3", name: "Demo: weekly review", enabled: false, nextRun: nil, lastRun: nil, lastStatus: nil, running: false),
        ]
        model.cronAsOf = Date()
        model.lines = [
            ChatLine(id: "d-u1", role: .user, text: "Demo message: what changed in the repo today?", at: Date().addingTimeInterval(-60)),
        ]
        model.historyAsOf = Date()
        // A made-up approval card, to see its layout. Its buttons stay off in the demo.
        let cardRow: [String: Any] = [
            "id": "plugin:demo-0001",
            "createdAtMs": now - 20_000,
            "expiresAtMs": now + 280_000,
            "request": [
                "title": "Demo: install a tool",
                "description": "Demo card. Install demo-tool 1.2.3 into the toolbox (12 MB). Made up to show the layout.",
                "severity": "warning",
                "allowedDecisions": ["allow-once", "deny"],
                "pluginId": "jorah-guard",
                "toolName": "toolbox_install",
                "agentId": "main",
            ] as [String: Any],
        ]
        if let card = ApprovalParsing.card(fromRow: cardRow) {
            model.approvals = [card]
            model.approvalsAsOf = Date()
            model.approvalFirstShown[card.id] = Date()
        }
        // Made up, to see the full-message card's layout.
        model.fullReply = """
        I couldn't finish the demo card, so nothing is proposed.

        - **Blocker:** the demo source is unreachable.
        - **Version:** the newest release is too new for the 7-day rule.

        To finish, paste the value here, or allow me to fetch the page.
        """

        let script: [(Double, String, JSONValue)] = [
            (0.3, "agent", agent("lifecycle", ["phase": .string("start")])),
            (0.6, "agent", tool("t1", "exec", "start", ["command": .string("git log --since=midnight --oneline")])),
            (1.2, "agent", tool("t1", "exec", "result", [:])),
            (1.4, "agent", tool("t2", "web_search", "start", ["query": .string("demo query")])),
            (1.6, "agent", tool("t3", "read", "start", ["path": .string("docs/plan/10-roadmap.md")])),
            (2.0, "agent", tool("t3", "read", "result", [:])),
            (2.2, "chat", chat("delta", "Demo reply: three commits landed today. ")),
            (2.6, "chat", chat("delta", "This text is made up to show the layout.")),
            (2.8, "tick", .object(["ts": .number(now)])),
        ]
        for (delay, name, payload) in script {
            Task {
                try? await Task.sleep(for: .seconds(delay))
                model.apply(event: name, payload: payload)
            }
        }
    }

    private static func agent(_ stream: String, _ data: [String: JSONValue]) -> JSONValue {
        .object(["runId": .string("demo-run"), "seq": .number(1), "stream": .string(stream), "ts": .number(0), "data": .object(data)])
    }

    private static func tool(_ id: String, _ name: String, _ phase: String, _ args: [String: JSONValue]) -> JSONValue {
        agent("tool", ["toolCallId": .string(id), "name": .string(name), "phase": .string(phase), "args": .object(args)])
    }

    private static func chat(_ state: String, _ delta: String) -> JSONValue {
        .object(["runId": .string("demo-run"), "sessionKey": .string("agent:main:main"), "state": .string(state), "deltaText": .string(delta)])
    }
}
