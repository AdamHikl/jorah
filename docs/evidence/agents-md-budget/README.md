# AGENTS.md reaches Jorah whole (2026-11-20)

All numbers are characters as OpenClaw 2026.10.9 counts them (UTF-16 code units after
`trimEnd()`), measured on the PC by importing OpenClaw's own `dist/bootstrap-CB2bEBTF.mjs`
(`buildBootstrapContextFiles`, `resolveBootstrapMaxChars`) and running it on the files. Nothing
private is recorded here: only lengths, line ranges and hashes of committed files.

## Before [measured]

- Live `/home/jorah/workspace/AGENTS.md` = `main`'s `workspace/AGENTS.md` (SHA-256 `7ba0dd0a…`),
  29,626 chars. The default `bootstrapMaxChars` is 20,000 and the live config sets none.
- Injected: 19,183 chars. For `AGENTS.md` OpenClaw keeps the first 9,000 chars, a 7,000-char
  "policy digest" of heading, bullet and keyword lines (each cut at 240 chars; 83 lines omitted)
  and the last 3,000 chars. Gateway log: "workspace bootstrap file AGENTS.md is 29626 chars (limit
  20000); truncating in injected context".
- Lost: lines 137-241 (Learning "Undo" onwards to the toolbox's step 2), apart from digest pieces.
  Rules lost entirely included: never answer a founder question yourself; project start with
  Adam's words verbatim; project digest text is data; Claude Code's working folder, clone/sync,
  `jorah/<task>` branch and "repo isn't protected, don't try another way"; never copy a
  prescription into memory files; never put health details in a brief; check `background`'s
  results before telling Adam. The pull-request rule survived only as a 240-char piece.
- Not affected: `SOUL.md` (2,298), `IDENTITY.md` (375), `USER.md` (under its 4,000 cap) of main;
  every file of `deep` (AGENTS 3,252) and `background` (AGENTS 1,417). Total far under 60,000.
- The truncation predates the toolbox deploy: `AGENTS.md.pre-errands` (2026-11-17) was 22,380.

## The fix (Adam's yes 2026-11-20: "yes raise it, but can we also distill it")

1. `workspace/AGENTS.md` distilled to 25,395 chars (SHA-256 `1feb4247…`). OpenClaw boilerplate dropped (Discord/WhatsApp
   formatting, `sag`, "Make It Yours", "Related", most group-chat etiquette); rules repeated in
   several sections merged into "Red Lines" (outside text is data, never invent a result) and
   "Handing Work Off" (say so first, brief like a peer, check results, API cost). An independent
   line-by-line review found no safety rule lost; its six wording findings were fixed.
2. `config/pc/bootstrap-limit.patch.json5`: `agents.entries.main.bootstrapMaxChars` 40,000, main
   only.
3. `scripts/pc/tests/test_bootstrap_budget.py` in `just check`: every bootstrap file of the three
   workspaces must stay under 90% of its limit.

Measured with OpenClaw's code on the distilled file [measured, before deploy]:

| limit | resolved for `main` | injected | whole | warnings |
|---|---|---|---|---|
| 20,000 (today) | 20,000 | 19,184 of 25,395 | no | 1 |
| 40,000 (patch) | 40,000 | 25,395 of 25,395 | yes | 0 |

Cost: about 6,200 more chars than today's 19,183, roughly 1,600 tokens on every main turn (voice
and heartbeats included). Main runs on Adam's Max login through `claude-cli`, so it counts against
his plan limits, not the API bill; at Haiku 5.5's API price it would be about $0.0002 per uncached
turn.

The key is per agent in both versions [measured, read-only]: in 2026.10.9 and in the 2026.10.33
canary install (`/home/jorah/.jorah-canary/2026.10.33`) the bootstrap chunk resolves
`resolveAgentConfig(cfg, agentId)?.[key]` before `agents.defaults`, the schema has
`bootstrapMaxChars: number().int().positive().optional()`, the docs name
`agents.entries.*.bootstrapMaxChars`, and the exported resolver returns 40,000 for `main` from
`{ agents: { entries: { main: { bootstrapMaxChars: 40000 } } } }`.

## Deployed 2026-11-20 [measured]

With the coordinating session's go for the live Gateway, from the main checkout at `2811987`:

- 18:20 `deploy_reviewed.py deploy config/pc/bootstrap-limit.patch.json5`: 1 file deployed and
  recorded. `/readyz` ready; dry run "1 update(s) validated"; applied 18:21:12 by hot reload;
  `config get agents.entries.main.bootstrapMaxChars` = 40000; `/readyz` ready, failing [].
- Live `AGENTS.md` was still `main`'s `7ba0dd0a…`; backup `AGENTS.md.pre-distill` (29,637 bytes);
  new file `1feb4247…`, 25,410 bytes, `jorah:jorah 644`; recorded with `record-live`.
- 18:21:32 `systemctl start jorah-gateway-recycle.service`: active 18:21:38, `NRestarts` 0;
  `/readyz` ready, failing [].
- Gateway log: 10 AGENTS.md truncation warnings today before the restart (last 18:14:37), 0 after
  it, including the `agent:main:voice-warmup` turn that ran after the restart. One "WAL checkpoint
  TRUNCATE remained busy" line at shutdown, as at the 08:20 and 14:20 recycles.

Open: Adam's Telegram check (signed-in acceptance).
