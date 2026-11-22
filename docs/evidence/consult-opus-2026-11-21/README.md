# Haiku asks Opus: test, fix and Adam's test, 2026-11-21 and 22

Adam asked whether Jorah's main agent (Haiku 5.5) really asks `deep` (Opus 5.5) when it is unsure,
then: "make it that it doesn't need to ask my permission, just make it work".

## Before the fix [measured]

- `jorah-guard`'s decision log, 13 to 21 Nov: no `sessions_spawn` from `main` at all.
- Four test turns on live `main`, each in a throwaway session (`agent:main:consult-check-2026-11-21-*`):

| Case | Expected | Result |
|---|---|---|
| "what's 15% of 80?" | Haiku answers | Haiku answered, 3.6 s |
| "Think hard: capacitive or resistive soil sensor, 2 AA for a year?" | Opus | Haiku spawned `deep`; the guard asked with a card ("Jorah wants to start a job"), which expired with the CLI's 300 s timeout. Opus never ran |
| CSV script slower every day: best fix and trade-offs | Opus (rules: debugging, trade-offs) | Haiku answered itself, 11 s |
| Lithium AA in a smoke alarm or toy | Opus (rules: safety) | Haiku answered itself, 9 s |

- **The card reached Adam's Telegram** (14:58 and 15:03 local, two messages and an expiry notice). The test plan had said nothing would.
- Why the card: the guard asks before a spawn of `background` or `deep` from any chat that read outside text, and a spawn marks the chat itself (the answer comes back into it). Test sessions are never Adam's own chat, so they always count. In Adam's one long chat, every hand-off after the first would have asked.
- Why Haiku kept the questions: its rules said "don't hand off anything you can answer well in a sentence or two", which covers almost anything.

## The fix (`a7a630a`, deployed 2026-11-21 20:3x)

- `config/pc/deep-consult.patch.json5`: `deep` loses `exec`, `process`, file writes and the sessions tools. Its only `exec` calls (13 to 21 Nov) were its own heartbeats.
- `jorah-guard`: `matrix.consultAgents: ["deep"]`. A spawn of `deep` never needs a card. The brief's URLs are still checked, and the answer still marks the chat. In `deep`'s own sessions only read, search and url tools pass, so this holds if the config drifts. `background` keeps its card.
- `workspace/AGENTS.md`: "When to Ask Opus" near the top judges the question, not Haiku's confidence; the `deep` section has examples, "don't answer first", and what to say if the spawn fails.
- The guard deploy also put `d187870` live (the `dispatch_action` unwrapping, a superset of 10.9's `tool_call` reading): the new `policy.js` imports it.
- Gateway restarted through `jorah-gateway-recycle.service`: 16 plugins, "jorah-guard: matrix loaded; state ok".

## After the fix [measured]

The same four cases (`consult-check-2026-11-21b-*`): the easy one stayed with Haiku (3.7 s). In all three others Haiku said "Let me ask Opus" and spawned `deep`, the guard allowed it, and nothing went to Telegram. But OpenClaw refused each spawn: a sandboxed session (every session but `agent:main:main`) can't start `deep`. Haiku then said so and labelled its fallback "Haiku's answer, not Opus's". All test sessions were deleted and forgotten from memory.

## Adam's Telegram test, 2026-11-22 [Adam: "it worked"]

- Guard log: `sessions_spawn` from `agent:main:main`, `from: adam-typed`, allowed with no card at 08:41:43 (`background`, Sonnet) and 08:50:33 (`deep`).
- `deep`'s child `agent:deep:subagent:625c3319…` ran on Opus 5.5 (`model-fetch … model=claude-opus-5-5` 08:50:35, embedded runtime) and its answer came back to main at 08:50:57.
- **Found in the log:** the child's `exec` was blocked at 08:50:41 ("deep only thinks, reads and searches the web"). On the embedded runtime OpenClaw's auto Code Mode engages for Opus, so the model sees only `exec`/`wait` and reaches web_search through JavaScript. `deep` answered without the web.

## Code Mode off for `deep` (2026-11-22)

Code Mode's `exec` is JavaScript, not a shell, and its inner calls still pass the hooks. But its default Node executor "is not a security boundary" (`docs/tools/code-mode.md`) and runs on the Gateway host, outside Podman. So rather than let it through, `deep-consult.patch.json5` sets `agents.entries.deep.tools.codeMode: false`: `deep` gets Tool Search (`tool_call`), which the guard already unwraps per inner tool. Code Mode had engaged 7 times since 11-07, only on `deep`'s embedded Opus runs.

## Open

- Adam's re-test with a question that needs the web (see the runbook).
- Which credential a spawned `deep` uses on the embedded runtime: `models status --agent deep` says "indeterminate"; the session records no auth profile. If it's the API key, consults count against the monthly API cap, not the Max plan.
- `deep` can't be asked from sandboxed sessions (cron, heartbeats, `background`). Adam's own chat is direct, so this doesn't affect him today.
