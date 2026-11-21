# ADR 0005: a native Mac HUD, with roadmap hard gate 8 waived

**Decision:** Adam waived roadmap hard gate 8 ("No native app before the two-week A7 log names a trigger", `docs/plan/10-roadmap.md` section 4) on 2026-11-10, for one app: a native macOS dashboard for Jorah at `clients/mac-hud/`. Adam's words in the build session, after being shown the gate and a web-first alternative: "okay, then build the mac app, I want it to be native".

This is a waived gate in the sense of the roadmap: it is written here, it belongs in the trust report, and the next stop point says what is absent.

## What is absent

- The A7 log does not exist, and no trigger from `docs/plan/07-apps-and-devices.md` 7.2 has fired. The reason for the app is that Adam wants it. 7.2 says cosmetic preference is not a trigger, so the gate is waived, not met.
- `docs/adr/native-app-decision.md` (the go or no-go that 7.1 asks for) is not written. This ADR stands in for it for the Mac HUD only.

## What the waiver covers

- A new native Mac app that Adam uses to type to Jorah and watch what it is doing.
- It supersedes one line of `07` 5.1 for the Mac: "A Jarvis-style HUD is a hosted page in the widget panel, for display only".

## What it does not cover

| Still in force | Why |
|---|---|
| An own iPhone or Android app stays behind gate 8 and M31 | The waiver names the Mac HUD only |
| Never fork OpenClaw's Mac app (`07` 5.1) | The HUD is a new, small app with its own Gateway client |
| The HUD is an operator client, never a node | Hard gate 2: no node besides the iPhone before M3 |
| Voice never approves (gate 9) | Unchanged |
| ~~The HUD does not ask for `operator.approvals`~~ Replaced by ADR 0007 (2026-11-21): the HUD may ask for it, by Adam's choice and approval | Answering approvals makes it a new approval surface. ADR 0007 is that decision and lists its tests |
| The HUD does not ask for `operator.admin` or `operator.pairing` | Least privilege |
| Adam enters the Gateway token, approves the pairing and grants macOS permissions | `CLAUDE.md`, "Adam's yes" |
| Nothing private connects before M3's gate | Unchanged. The HUD shows only what the Gateway already sends an operator, except the PC panel's load figures, read from a reader on Windows (ADR 0008, 2026-11-21) |
| Unknown is shown as unknown, never 0 | `CLAUDE.md`, "Never" |

## Scopes

Adam picks the access in the HUD's pairing sheet, and his approval of the pairing request on the PC is the yes.

| Choice in the pairing sheet | Scopes requested |
|---|---|
| Watch only | `operator.read` |
| Watch and type (the default, since Adam asked to type) | `operator.read`, `operator.write` |

Changing the choice later is a new pairing request, approved again. Talking is not built: the PC's `jorah-voice` service has its own token and allows one voice session at a time, and it gets its own yes.

## Re-check

Before anything is published, signed for distribution or shared: the Apple team (kept apart from Mizyun, `07` 5.4), and this waiver.
