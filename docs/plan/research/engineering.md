# Jorah research track: engineering, operations and business

Date: 2026-11-02. Status: research only. Nothing was installed, no account was created, no config changed, and the gateway was not touched. The only file written is this one. This is the second pass; see "Research passes" below. A later independent skeptic pass corrected this file in place; see "Verification" at the end.

## How to read the labels

| Label | Meaning |
|---|---|
| `[verified: URL]` | I read that page or API response today (2026-11-02), in this pass or the first pass. A vendor page is still the vendor's own claim. |
| `[verified: command]` | A read-only command on this Mac this session. Names the command. |
| `[docs-only: path]` | OpenClaw's bundled docs say so and nobody has exercised it on Adam's setup. Paths are relative to `DOCS` = `/opt/homebrew/lib/node_modules/openclaw/docs`. |
| `[secondary: URL]` | Press, a blog or an aggregator, found by search. No primary source confirmed it. Check before relying on it. |
| `[peer: file §n]` | Taken from another research track in this folder. Check its own labels there. |
| `[inference]` | My reasoning, estimate or proposal. Treat as a hypothesis. |
| `[unconfirmed]` | From memory or one weak source. Check before relying on it. |
| `[unverified]` | The skeptic pass tried to confirm this and could not. Do not rely on it. |

Evidence tiers for all later work, from Adam's rule: **source check, then fixtures and tests, then install, then launch with PID, then signed-in device acceptance, then soak.** Nothing in this file is above the source-check tier unless it says it was measured.

**Research passes.** The first pass (about 18:00 CET) had no web search, because the shared budget was used up, and the robotics, UX, connectors and apps tracks were not finished. This second pass (about 21:30 CET, after Adam asked to try again) had search. It ran the competitor scan, closed most unconfirmed items, merged those four tracks, re-checked key local and web claims, and fixed errors in the first pass (section 16.2 lists them). Section 18 marks which pages were reopened in this pass. Search here is a weak discovery tool and returns many aggregators, so market claims are mostly `[secondary]`, and a product missing from section 13 is not evidence that none exists.

---

## 1. Recommendation in one page

**Build a single private monorepo. Keep OpenClaw pinned and treat it as a dependency you do not modify. Put only thin policy and adapter code inside the Gateway process. Run everything heavy or real-time as a separate supervised service. Check most things on this machine, use GitHub Actions only for cheap checks, and do not start a business until Jorah has been in daily use for months.**

Fifteen findings that shape the plan:

1. **The repo and the live agent are the same directory today.** The Gateway's workspace is `~/Documents/jorah/workspace` [verified: `openclaw --profile jorah backup create --dry-run --json`, paths only]. Once git is in use, switching branches in the main checkout silently changes Jorah's live instructions. Fix: all development in worktrees, and the main checkout stays on `main` until the macOS user move separates runtime from repo (section 3.3).
2. **GitHub gives no server-side secret protection on a private repo for this account type.** Secret scanning and push protection need GitHub Secret Protection, $19 per active committer per month, sold to Team and Enterprise Cloud [verified: https://docs.github.com/en/code-security/getting-started/github-security-features, https://github.blog/changelog/2025-03-04-introducing-github-secret-protection-and-github-code-security/]. User-level push protection covers public repos only [verified: https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection]. So scanning has to run locally and in CI. `gitleaks` is still the pick, but it is now frozen at security patches only, and its maintainer has moved to Betterleaks (section 4.1).
3. **GitHub Free cannot protect `main` on a private repo.** Protected branches and required reviewers on private repos are Pro features [verified: https://docs.github.com/en/get-started/learning-about-github/githubs-plans], and Pro is about $4 a month [secondary: https://creditforstartups.com/resources/github-pro-pricing]. Enforce locally at first, and buy Pro before any unattended session is allowed to push (section 4.4).
4. **All OpenClaw plugin APIs are officially experimental, and native plugins run unsandboxed inside the Gateway.** A bug can crash the Gateway, and a bad plugin equals code execution in that process [docs-only: `plugins/sdk-overview.md`, `plugins/architecture.md`]. So plugins stay thin (section 6).
5. **OpenClaw's plugin test helpers are not available to outside plugins.** They are repo-local source entries, not published exports [docs-only: `plugins/sdk-testing.md`]. Jorah's plugins need their own fake `api`, plus a real install proof through `npm-pack:` on a throwaway profile (section 9).
6. **`openclaw backup` does not cover everything Jorah needs.** The dry run lists two assets, `~/.openclaw-jorah` and the workspace [verified: command above]. `~/.claude-jorah` (39 MB and growing, Claude CLI transcripts) and `~/.jorah-brain` are outside it. So a restore loses Jorah's Claude transcripts unless they are backed up separately (section 10).
7. **Cost per day cannot be one number.** CLI and subscription runtimes report tokens only unless given an explicit local price, and session cost totals describe local session history and not a provider invoice [docs-only: `reference/api-usage-costs.md`]. Anthropic's Admin API is unavailable for individual accounts [verified: https://platform.claude.com/docs/en/build-with-claude/usage-cost-api]. Show three separate columns and print "unknown" rather than zero (section 8).
8. **OpenClaw exports no per-stage voice latency for native Talk.** The Talk metrics are an event counter, an event duration and audio bytes [docs-only: `gateway/opentelemetry/model-calls-and-metrics.md`]. Pipecat provides per-turn STT, LLM and TTS spans once `jorah-voice` exists. Real mouth-to-ear delay still needs an acoustic loopback test (section 8.3).
9. **Pipecat tracing puts private words into spans by default.** Its docs list `transcript`, `text`, LLM `input` and `output` as span attributes, and describe no switch to turn them off [verified: https://docs.pipecat.ai/server/utilities/opentelemetry]. Turning on tracing naively would write Adam's conversations into telemetry. Use an allowlist exporter and a test that fails on those keys (section 8.2).
10. **A self-hosted CI runner on this Mac is the wrong trade now.** It would execute workflow code on the machine that holds everything. GitHub-hosted Linux is enough for cheap checks: Free includes $12 of compute, about 2,000 Linux minutes, and macOS costs $0.062 per minute, so about 193 minutes [verified: https://docs.github.com/en/billing/concepts/product-billing/github-actions]. Mac, device and hardware checks stay local behind `just` targets (section 9.3).
11. **Python services must not share one `uv` workspace.** A workspace has one lockfile and one `requires-python`, and uv's docs say it does not suit members with conflicting requirements [verified: https://docs.astral.sh/uv/concepts/projects/workspaces/]. Pipecat, LeRobot and a vision stack will conflict. Use independent projects linked by path (section 3.2).
12. **Building Jorah with Claude Code draws from the same weekly limit as Jorah's brain and Adam's Mizyun work** [peer: brain.md §3]. Anthropic's 2026-10-07 update says `claude -p` and the Agent SDK still draw from subscription limits when signed in with the plan [verified: https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan]. Three parallel build sessions could starve the assistant. Measure a week before planning parallel work (section 12).
13. **The exec gap becomes a physical safety problem once an arm is on USB.** Exec could open the serial port and rewrite servo limits. So the arm sits behind a dedicated Pi or an ESP32 firewall, and no autonomous motion runs before that boundary exists [peer: robotics.md §1]. This is a release gate in section 15.2. CI never drives real motion unattended (section 9.6).
14. **The agent shell is free, and a general assistant is a poor business.** OpenClaw is MIT with 393,749 stars and a non-profit behind it. Claude Cowork, ChatGPT Work and Perplexity Personal Computer all sell the same "agent on your computer" shape. Poke relayed about 100 million messages and was then absorbed by Cognition in July 2026, with its founders moving to work on Devin [secondary: https://www.techwyse.com/?p=76542, https://runtimewire.com/article/cognition-acquires-poke-interaction-consumer-ai-agents]. That Poke was unprofitable is [unverified], so this is a weak signal rather than proof. OpenClaw hosting and setup gigs are already crowded. What could be worth something is a testable safety and growth layer: the one published OpenClaw-to-SO-101 guide I found documents no E-stop or motion limits [verified: https://wiki.seeedstudio.com/ai_robotics_control_soarm_by_openclaw_on_jetson_thor/] (sections 13, 14).
15. **Realistic time through the mobile base is about 13 months at 12.5 hours a week** (10 to 12 months at 15 hours, 15 to 18 at 10 hours). Real-time conversation on the Mac arrives around week 9, always-on around week 31, a voice-commanded arm around week 49. New money through the mobile base is about €1,650 to €4,810 plus unknown PC parts, and about €980 if the PC passes, there is no UPS, and Adam stops at the arm. The Max plan Adam already pays adds about €1,160 over the same 13 months before tax, and about €1,420 if 23% VAT is charged [inference, section 15].

---

## 2. Decision table

| # | Decision | Pick | Why | Runner-up | What would change it | Rough cost |
|---|---|---|---|---|---|---|
| E1 | Repo shape | Private monorepo `AdamHikl/jorah` | One developer, contracts cross languages, Claude Code sees all of it | Polyrepo (plugin, firmware, apps separate) | A part goes open source: split it by filtered export | €0 |
| E2 | Toolchain pin | `mise` + `just` + `pnpm` + `uv`, with one `uv` project and lockfile per Python service | Same commands on Mac, WSL and CI. A shared uv workspace forces one lock across conflicting ML stacks [verified: https://docs.astral.sh/uv/concepts/projects/workspaces/] | Plain README commands | `mise` fails on native Windows for `jorah-desk` | €0 |
| E3 | Secrets scanning | `gitleaks` in pre-commit, pre-push and CI, plus a full-history scan before first push | MIT, single binary, no server dependency, stable CLI. Frozen except for security patches, so our own rules must cover new token shapes | Betterleaks (MIT, same original author, active, but its v2 is changing CLI and config). TruffleHog third (AGPL-3.0, heavier) | Rules miss real tokens in the planted-secret test; gitleaks stops shipping security patches; Betterleaks ships a stable v2 | €0 |
| E4 | First remote | Private GitHub, with a `git bundle` to an encrypted disk as the second copy | Issues and CI in one place | Bundle only, no remote | Adam does not want research notes on GitHub | €0 |
| E5 | `main` protection | Local hook plus Claude Code deny rule on Free now. Buy GitHub Pro before any unattended or `claude -p` session can push | Local rules stop mistakes, but they can be bypassed; a server rule cannot be bypassed by a session | Pro from day one | Any other person or bot gets write access | €0 now, then about $4 a month [secondary] |
| E6 | OpenClaw upgrades | Stable channel, exact pin, canary profile first, every 2 to 4 weeks or within 48 h of a relevant high advisory | 17 stable releases in October alone [peer: openclaw-fit.md §9]; rollback needs a snapshot | `extended-stable` | Voice settles; two breaking updates in a quarter | €0 |
| E7 | Custom code location | Thin plugins in-process; services and MCP servers outside | Plugins are unsandboxed; Python ML does not belong in Node | Everything as plugins | SDK gains out-of-process plugins | €0 |
| E8 | Client to Gateway | `@openclaw/gateway-client` pinned exact, tested with the host | Stable packages, `traceparent` per request | Raw WebSocket | Package lag blocks an upgrade | €0 |
| E9 | Supervision | launchd on Mac; systemd user units in WSL; Scheduled Task at logon for anything needing audio or GUI on Windows | Matches what OpenClaw installs; Windows services cannot reach the desktop session | WinSW for all Windows parts | A headless bridge must start before logon: WinSW for that one | €0 |
| E10 | Observability | Stage 1: built-in commands plus one JSONL ledger. Stage 2: `diagnostics-otel` to `grafana/otel-lgtm` on demand. Pipecat spans only through an attribute allowlist | No new daemon until a question needs it. Pipecat records words by default | Jaeger + Prometheus; Langfuse | Always-on dashboards are actually wanted | €0 |
| E11 | CI | GitHub-hosted Linux for lint, unit tests, scan. Local `just` gates for the rest | Cheap, nothing private leaves | Self-hosted runner on Mac | HIL bench exists: a runner on the PC under its own user | €0 inside allowance |
| E12 | Simulator | MuJoCo with `robotstudio_so101` from Menagerie | Apache-2.0; SO-101 model exists | Gazebo, Isaac Sim | The arm design leaves SO-101 | €0 |
| E13 | ESP32 tests | Safety logic in plain C++ with host tests; `arduino-cli compile` in CI; real bench for timing | Matches robotics' Arduino core pick; no paid CI minutes; QEMU only helps once on ESP-IDF | Wokwi Pro at €20 a month; ESP-IDF plus Espressif QEMU | Robotics moves to ESP-IDF, or peripheral bugs reach the bench | €0 |
| E14 | Backups | `openclaw backup` for state; `restic` for what it skips and for media; offsite at Hetzner Storage Box BX11 | Encrypted, BSD-2-Clause; EU storage, 1 TB, native SFTP and restic support [verified: https://www.hetzner.com/storage/storage-box/] | Cloudflare R2 or Backblaze B2 | Media needs more than 1 TB, or Adam wants no offsite | About €4 a month with VAT [inference on VAT], plus a one-off setup fee whose amount the page does not state |
| E15 | Parallel sessions | At most 2 at once, one issue per session, one worktree per session, one session owns the live Gateway | Limits quota burn and collisions | Agent teams | Week of `/usage` shows plenty of headroom | Shared Max plan |
| E16 | Claude GitHub App | Do not install | Requires a broad permission set including Workflows, Actions and Repository hooks write | Custom app with Contents, Issues, PRs only | Adam wants `@claude` from the phone | €0 |
| E17 | Business timing | Personal first. At most 10% of time, gates at about month 4 and month 9 | Moat appears only after real use; Mizyun and Cognio already compete for time | Start now on a Slovak angle | A stranger offers money before the gate | €0 |
| E18 | Public release | Nothing public now. Later: firmware safety core, robot protocol, injection corpus under Apache-2.0 | Patent grant; reputation; contains no private data | MIT | Decision at the business gate | €0 |
| E19 | Public name | Keep "Jorah" private until a registry check. No "Jarvis" or "Claw" in any public name | Marvel objected to BlackBerry's 2019 JARVIS filing for cybersecurity software [secondary, paywalled excerpt: https://www.worldipreview.com/trademark/marvel-hits-out-at-blackberry-over-jarvis-tm-18387]. A Marvel registration covering voice assistants is [unverified]. Jorah is also a well-known fictional character [inference] | Pick a new name at gate G3 | Lawyer clears it | €0 now |

---

## 3. Repository

### 3.1 Monorepo or not

**Pick: one private monorepo.** Reasons [inference]:

- One person plus Claude Code. A session needs to change a robot protocol schema, its plugin tool, its bridge and its firmware in one reviewable diff.
- Contracts cross four languages (TypeScript, Python, C, Swift). Separate repos would need versioned packages for a project with one user.
- CI is path-filtered, so a firmware change does not run plugin tests.

**Exceptions that stay out of the monorepo:**

| Thing | Where | Why |
|---|---|---|
| `~/.jorah-brain` | Local git, no remote | Already that way; holds learned memory [verified: `README.md`] |
| Real audio, photos, Adam's voice | Private fixture store outside git (section 9.4) | Personal data; bloats history |
| Eval holdout cases and graders | `~/.jorah-lab/graders/` | Jorah must not be able to read them [peer: growth.md §8, §9] |
| A fork of OpenClaw's iOS or Mac app, if ever | Own repo | Follows upstream's history |
| Public parts, later | Filtered export (`git subtree split`) to a new public repo | Never flip this repo public |

**No Git LFS.** Claude Code worktrees show LFS pointer files rather than content when LFS was set up with `--local`, and it skips the repo's own filter drivers on purpose [verified: https://code.claude.com/docs/en/worktrees]. Keep binaries in a manifest-plus-hash store instead.

### 3.2 Layout

Existing paths stay where they are. New directories are added only when a real issue needs them.

```text
jorah/
  README.md
  CLAUDE.md               # under 200 lines; rules for build sessions
  AGENTS.md               # symlink to CLAUDE.md, for Codex and Antigravity
  LICENSE                 # "All rights reserved" until the public decision
  mise.toml               # node, python, uv, pnpm, just, gitleaks versions
  justfile                # the only commands people and agents should need
  lefthook.yml            # pre-commit and pre-push
  .gitleaks.toml
  pnpm-workspace.yaml
  .github/workflows/      # ci.yml only at first

  workspace/              # Jorah's rules (existing). Private files stay ignored
  config/                 # existing, plus versions.env (OpenClaw pin)
  scripts/                # existing ops scripts
  ops/
    launchd/  systemd/  pi/  windows/  otel/
  packages/
    contracts/            # JSON Schema: robot protocol, voice events, capability.yaml
  plugins/                # TS, each a thin OpenClaw plugin
    jorah-guard/          # approvals and policy [peer: security.md, growth.md]
    jorah-robot/          # tool definitions only, calls robot-bridge
    jorah-voice-provider/ # if V2 plugs in as a realtime provider [peer: voice.md]
  services/               # Each is its own uv project and lockfile; Rust only where timing demands it
    jorah-voice/          # [peer: voice.md]
    jorah-eyes/           # [peer: vision.md]
    robot-bridge/         # Python 3.12, LeRobot at a pinned tag; runs on the arm's Pi [peer: robotics.md §5]
    mcp-edupage/          # runs under a reader agent
  firmware/               # Arduino core 3.x on ESP32-S3 first [peer: robotics.md §4]
    common/               # Plain C++ with no Arduino headers: protocol, deadman, limits. Host-tested
    safety-supervisor/  bus-firewall/  cam-node/
  robots/                 # MJCF, URDF, build123d CAD, bench fixtures
  apps/                   # only if OpenClaw's apps fail a named requirement
  capabilities/           # [peer: growth.md §10]
  evals/
    runner/  suites/{safety,routing,memory,acquisition,injection}/
  fixtures/
    synthetic/            # committed, generated, safe
    manifest.yaml         # hashes for private fixtures, no content
  docs/
    plan/  runbooks/  adr/  evidence/<issue>/
```

Rules [inference]:

- `packages/contracts` is the source of truth. TypeScript, Python and C types are generated from it. A protocol change that does not regenerate fails CI.
- Python services are independent `uv` projects linked by path to `packages/contracts`, each with its own lockfile and virtual environment. uv recommends this over a workspace when members have conflicting requirements or need separate environments [verified: https://docs.astral.sh/uv/concepts/projects/workspaces/]. Robotics already needs a dedicated Python 3.12 environment [peer: robotics.md §9 R0].
- `just` targets are the interface: `just check`, `just test`, `just plugin-proof <name>`, `just smoke`, `just perf`, `just hil`, `just evals <suite>`. CI calls the same targets.
- Every decision that outlives a session goes in `docs/adr/NNNN-title.md` with pick, why, runner-up and what would change it. This is the same shape as this file.
- `docs/evidence/<issue>/` holds command output, screenshots and timings with private content removed. It is how a later session knows what was proven.

### 3.3 The workspace problem

Today `workspace/` is both repo content and Jorah's live state, and Jorah writes there.

| Risk | Example | Fix |
|---|---|---|
| Branch switch changes live behavior | `git checkout feature` swaps `AGENTS.md` under a running Jorah | Develop only in worktrees. The main checkout stays on `main` [inference] |
| Jorah's writes dirty the tree | Dreaming, skills, `DREAMS.md` | Ignore rules for runtime files; review Jorah's own edits as a diff before commit |
| Self-modification | Jorah commits a change to its own safety rules | Jorah has no git push credential for this repo, and `workspace/AGENTS.md` changes need a PR Adam merges [peer: security.md rule 26, T4 for `main`] |
| Claude project key depends on the path | Moving the workspace resets `--resume` history | Known [peer: topology.md §7] |

**When Gateway moves to macOS user `jorah`:** runtime workspace becomes `~/jorah/workspace` [peer: topology.md §7]. From then on, deploy from the repo with an explicit script: `scripts/deploy-workspace.sh --diff` shows the change, a second run with `--yes` applies it. This matches Adam's rule to preview changes [inference].

### 3.4 First commit

The repo has no commits and nothing tracked yet [verified: `git status`]. A names-only regex scan for Anthropic, GitHub, AWS, Google and Telegram token shapes and private-key headers, over `README.md config scripts docs .gitignore workspace/{AGENTS,SOUL,IDENTITY}.md`, matched no files in this pass [verified: `grep -rl`]. `workspace/USER.md`, `workspace/DREAMS.md` and `workspace/memory/` are correctly ignored [verified: `git status --ignored`]. **That is a quick check, not a proof. Run gitleaks before the first push.**

`.gitignore` additions needed [inference]:

```gitignore
# Build and dependency output
node_modules/
.venv/
dist/
build/
*.tgz
__pycache__/

# Claude Code: worktrees (recommended by Anthropic). settings.local.json is already caught by *.local.json
.claude/worktrees/

# More secrets and state
.env.*
*.pem
*.key
*.p12
*.mobileprovision
**/*.sqlite
**/*.sqlite-*
**/credentials/

# Personal media and fixtures
fixtures/private/
*.wav
*.m4a
!fixtures/synthetic/**/*.wav
```

Comments must stay on their own lines. Git treats text after a pattern as part of that pattern.

`.claude/worktrees/` advice [verified: https://code.claude.com/docs/en/worktrees].

**Steps (each needs Adam's yes; do not run from this research session):**

```bash
brew install gitleaks                               # preview first; latest release is v8.30.1 [verified: GitHub API]
gitleaks dir . --config .gitleaks.toml --redact     # working tree, including ignored private files; output redacted
git add .gitignore README.md config scripts docs \
        workspace/AGENTS.md workspace/SOUL.md workspace/IDENTITY.md
git status --short                                  # Adam reads this list
git diff --cached --stat
gitleaks git --staged --config .gitleaks.toml --redact
git commit                                          # message ends with the attribution lines
gh repo create AdamHikl/jorah --private --source . --remote origin
gitleaks git . --config .gitleaks.toml --redact     # full history before first push
git push -u origin main
git bundle create <encrypted-disk>/jorah-$(date +%F).bundle --all
```

Subcommands checked: `git`, `dir` and `stdin` are current, `detect` and `protect` have been hidden and deprecated since v8.19.0 [verified: https://raw.githubusercontent.com/gitleaks/gitleaks/master/README.md]. `--staged` and `--pre-commit` exist on `git` [verified: https://raw.githubusercontent.com/gitleaks/gitleaks/master/cmd/git.go]. `--redact` matters because a scan otherwise prints the secret into a terminal that an agent may be reading [verified flag: same README; inference on the risk]. The account is `AdamHikl` [verified: `gh api user`]. Its plan could not be read with the current token scope.

Deliberately not added: `workspace/USER.md`, `MEMORY.md`, `memory/`, `DREAMS.md`, `sandbox/`.

`SOUL.md` and `IDENTITY.md` would be tracked. They are small (1,533 and 1,432 bytes) [verified: `wc`]. They are fine for a private repo, but must be excluded from any public export.

**`docs/plan/research/` describes real vulnerabilities in the current setup** (for example exec with no approval, unauthenticated loopback) [peer: security.md §2]. This is another reason the repo must never go public as it is, and any public export must use an allowlist of paths.

---

## 4. Secrets and supply chain

### 4.1 Why local scanning is the control

| Option | Status for this account | Evidence |
|---|---|---|
| GitHub secret scanning on private repo | Needs Secret Protection, $19 per active committer per month, sold to Team and Enterprise Cloud. Not offered for personal Free or Pro | [verified: https://docs.github.com/en/code-security/getting-started/github-security-features, https://github.blog/changelog/2025-03-04-introducing-github-secret-protection-and-github-code-security/] |
| User-level push protection | Public repos only | [verified: https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection] |
| Dependabot alerts, version and security updates | Free on any plan | [verified: same features page] |
| `gitleaks` | MIT, 30,604 stars, latest release v8.30.1 from 2026-03-21. **The README says it is feature complete, future releases are security patches only, and the maintainer is shifting to Betterleaks.** The recent commits I read are Dependabot merges, so the "pushed 2026-10-28" date does not mean active development | [verified: GitHub API, https://raw.githubusercontent.com/gitleaks/gitleaks/master/README.md] |
| Betterleaks | MIT, 2,754 stars, v1.9.0 from 2026-09-29, maintained by the people who made gitleaks. `main` is v2 development, with a migration guide for CLI and config changes. Detection makes no provider requests by default; `--validate` and `--analyze` do | [verified: GitHub API, https://github.com/betterleaks/betterleaks] |
| `gitleaks-action` | Licence changed at v2; key needed for organizations, not personal accounts | [verified: https://github.com/gitleaks/gitleaks-action README] |
| TruffleHog | AGPL-3.0, v3.99.7, verifies whether keys are live | [verified: GitHub API] |

**Pick:** run the `gitleaks` binary directly in all three places, pinned by version and checksum. This avoids the action's separate licence and works the same if the repo ever moves to an organization [inference]. A frozen scanner is acceptable here because the job is simple and the planted-secret test proves it still catches what matters, but nobody will add new token rules for us [inference]. Do not move to Betterleaks until its v2 is stable, and when it is, re-run the planted-secret test on it and never set `BETTERLEAKS_VALIDATE`, since validation sends found secrets to providers [inference; flag names verified on its README].

### 4.2 Configuration

`.gitleaks.toml` starts with an `[extend]` block with `useDefault = true`, so built-in rules stay on [verified: gitleaks README]. It adds [inference]:

- ElevenLabs keys and Tailscale auth keys, which have no default rule. The default config already has `anthropic-api-key`, `anthropic-admin-api-key`, `openai-api-key`, `gcp-api-key` and `telegram-bot-api-token` [verified: `config/gitleaks.toml` on master, last changed 2025-11-20 by GitHub API]. Still test all of them, because those rules are frozen too.
- OpenClaw gateway token if it has a recognizable shape (read `security.md` S0.4 first).
- A stopword allowlist for documentation examples, with **no** allowlisted paths, so docs are scanned too.

**Always pass `--redact`** in hooks, CI and `just` targets, so findings never print a real value.

**Test the scanner itself:** a fixture commit on a throwaway branch with a fake token of each shape must be refused. Store the expected refusals under `fixtures/synthetic/secrets/`, using values that match the shape but are obviously fake. This test goes in `just check`.

Two more local guards [inference]:

- A pre-commit check that refuses any file matching `workspace/(USER|MEMORY|DREAMS)\.md`, `workspace/memory/`, `*.sqlite`, and audio files outside `fixtures/synthetic`, even if `.gitignore` is bypassed with `git add -f`.
- A check that scripts never print values from `openclaw.json`. Secrets are read by path through `openclaw --profile jorah config get`, and only for non-secret paths.

### 4.3 Where secrets live

Pick from the security track: macOS Keychain `exec` SecretRef now, 1Password service account when the PC arrives [peer: security.md §13]. Engineering additions [inference]:

- No secret ever in GitHub Actions secrets at first. CI needs none.
- No `CLAUDE_CODE_OAUTH_TOKEN` in Actions. It works and runs on the subscription [verified: https://code.claude.com/docs/en/github-actions], but it is a long-lived credential tied to Adam's plan, for little benefit on a one-person repo.
- `.worktreeinclude` must never list secret files, because it copies them into every worktree [verified: https://code.claude.com/docs/en/worktrees].
- Approvals saved with "don't ask again" in a worktree land in the main checkout's `.claude/settings.local.json` and apply everywhere [verified: same page]. So avoid blanket approvals, and review that file weekly.

### 4.4 Protecting `main`

GitHub Free for personal accounts does not list protected branches for private repos, and the pricing page shows repository rules as public-only on Free [verified: https://docs.github.com/en/get-started/learning-about-github/githubs-plans, https://github.com/pricing]. Pro includes protected branches, required reviewers and code owners on private repos [verified: same plans page], at about $4 a month [secondary: https://creditforstartups.com/resources/github-pro-pricing; the anonymous pricing page does not show Pro]. GitHub's features page separately lists repository rulesets under "all plans" [verified: https://docs.github.com/en/code-security/getting-started/github-security-features]. These two pages disagree for private repos, so test it after the repo exists instead of trusting either: create one ruleset on the private repo and see whether it enforces. GitHub's rulesets and protected-branches articles state no plan for personal private repos [verified: fetched both on 2026-11-02], so plan on the pricing page's reading, public only on Free, until the test says otherwise [inference].

**Pick: Free now, Pro at a named trigger.** Add:

1. `lefthook` pre-push hook refusing a push to `main` unless `JORAH_ALLOW_MAIN=1` is set by Adam.
2. Claude Code project settings with a deny rule on `git push origin main` and force pushes.
3. PRs from worktree branches, merged by Adam.

These stop mistakes, not a determined process, since `--no-verify` and the GitHub API both go around them. **Trigger for Pro:** before any unattended or `claude -p` build session holds a credential that can push. At about €43 a year that is cheap for a repo holding Jorah's own safety rules [inference]. Real isolation stays the same either way: Jorah's runtime account has no credential for this repo.

### 4.5 Dependencies

| Area | Rule [inference unless noted] |
|---|---|
| npm | `pnpm` with a committed lockfile and exact versions. Set `minimumReleaseAge: 10080` (the unit is minutes, so 7 days; the default is 1440), `trustPolicy: no-downgrade`, and keep `blockExoticSubdeps` at its default of true [verified: https://pnpm.io/settings/dependency-resolution]. Use `strictDepBuilds` and `allowBuilds` so lifecycle scripts run from an allowlist only [verified names: https://pnpm.io/settings; check syntax at setup]. |
| Python | One `uv.lock` per service, hashes on. Same 7-day delay by review, or `exclude-newer` if it fits [inference]. |
| GitHub Actions | Pin by full commit SHA. Dependabot for Actions only at first, with `cooldown: default-days: 7`. Cooldown does not delay security updates [verified: https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference]. |
| OpenClaw | Exact pin, **excluded from Dependabot** through `ignore: dependency-name` [verified: same Dependabot page]. Upgraded only by the procedure in section 5. |
| Gateway client | Exact, same train as host. The bundled docs name `2026.8.1` as verified stable with wire version 4 and say current wire is 4 [docs-only: `gateway/clients.md`]. npm also has `@openclaw/gateway-client@2026.10.9` as `latest`, matching the host, and it pins `gateway-protocol` 2026.10.9 [verified: `npm view`]. Test the matching version first and keep 2026.8.1 as the documented fallback. Operator clients must negotiate the exact wire version, and only node clients get the N-1 window [docs-only: same], so a wire bump breaks `jorah-voice` until its client moves. |
| Vulnerability scan | `osv-scanner` (Apache-2.0) [verified: GitHub API] in `just check`, weekly review by hand. |
| ClawHub skills and plugins | Nothing third-party without source review. 341 of 2,857 audited skills were malicious in one study [peer: security.md §3]. |
| Licence check | `just licenses` fails on a new AGPL, GPL, NC or unknown licence until an ADR accepts it (section 14.4). |

---

## 5. OpenClaw pinning and upgrades

### 5.1 Facts

- Pinned 2026.10.9, which is the latest stable as of today. npm dist-tags: `latest` 2026.10.9, `beta` 2026.10.10-beta.5, `extended-stable` 2026.9.36 [verified: `openclaw --version`, `npm view openclaw dist-tags`, GitHub releases API].
- Stable-labelled releases: 17 in October 2026, and 722 published advisories [verified: GitHub API]. The newest published advisory is dated 2026-09-11, although the 2026.10.9 notes mention security dependency patches [verified: GitHub API]. So an empty advisory feed does not mean nothing changed. Read release notes as well as advisories [inference].
- A raw `npm i -g` replacement does not keep the previous package or run recovery. `openclaw update` validates the target, runs Doctor migrations and verifies the activated Gateway [docs-only: `install/updating/rollback-and-recovery.md`].
- Downgrading a package does not reverse config or database migrations. Recovery after a migration means restoring a verified backup with its matching release [docs-only: same].
- Headless nodes **auto-update by default**, checking hourly [docs-only: `install/updating/automatic-updates.md`]. This must be switched off (`nodeHost.autoUpdate.enabled: false`) [peer: topology.md §13].
- `gateway install` accepts `--runtime-path`, so the service can use a pinned Node instead of whatever Homebrew last installed [docs-only: `cli/daemon.md`]. This Mac runs Homebrew Node 26.13.0 today [verified: `node -v`].
- The minimum is Node 24.22.1+ or 26.12.1+ [docs-only: `plugins/building-plugins.md`].

### 5.2 Procedure

Single pin in `config/versions.env`, read by `configure.sh`. Combines openclaw-fit.md §9 with a canary step [inference]:

| Step | Command or action | Stop if |
|---|---|---|
| 1. Read | Release notes for every skipped version; advisories for enabled surfaces | A breaking note touches a used surface: open an issue first |
| 2. Canary install | Install candidate into a private prefix, for example `npm i --prefix ~/.jorah-canary/<ver> openclaw@<ver>`. Profile `jorah-canary`, own port | Install scripts or size look wrong |
| 3. Plugin proof | `just plugin-proof` against the canary: pack, `plugins install npm-pack:`, `plugins inspect <id> --runtime --json` | Any plugin fails to load |
| 4. Canary smoke | Fresh test Telegram bot; fake provider or Haiku turn; memory search; ACP delegation; sandbox containment check | Any failure |
| 5. Evals | Safety and injection suites, on request [peer: growth.md §8] | Safety below 100% |
| 6. Backup | `openclaw --profile jorah backup create --verify`, plus section 10 extras | Verification fails |
| 7. Dry run | `openclaw update --tag <ver> --dry-run` | Named preflight failure |
| 8. Upgrade | **Adam's yes.** `openclaw update --tag <ver>`, Gateway first, then nodes. N-1 protocol is accepted for nodes [peer: topology.md §13] | Readiness fails |
| 9. Smoke live | `just smoke`, `openclaw doctor`, `openclaw security audit --json`, `/readyz`, one voice turn | Roll back |
| 10. Soak and close | 24 h watching logs; later `openclaw update cleanup`; update pin; note in `docs/evidence/` | |

**Ports:** keep at least 120 between base ports so derived ports do not collide [docs-only: `gateway/multiple-gateways.md`]. Proposal: `jorah` 43181 (existing), `jorah-dev` 43301, `jorah-canary` 43421, `jorah-eval` 43541, rescue 43661 [inference].

**Cadence:** every 2 to 4 weeks, or within 48 hours of a critical or high advisory on an enabled surface [peer: openclaw-fit.md §9]. Budget about 1 to 2 hours each time [inference]. That is 2 to 4 hours a month, about 4% to 7% of Adam's time. **Put this in the plan.**

**Rollback order:** managed `openclaw update --tag <known-good>` when state is still compatible. Otherwise restore the pre-update backup with its matching release [docs-only: rollback-and-recovery]. Rehearse once before it matters (section 10.3).

**Upstream relationship:** do not patch OpenClaw in place. (Governance and exit plan are in section 5.3.) Any local patch will be lost in the next update and breaks package verification. If something is truly needed, open an issue upstream and use a plugin [inference]. Test against beta tags only if a plugin starts breaking often; the beta window is typically a few hours [docs-only: `plugins/building-plugins.md`].

### 5.3 Upstream risk and exit plan

OpenClaw moved into a US 501(c)(3) foundation, announced 2026-07-09, with OpenAI, Microsoft, NVIDIA and Tencent among sponsors. It stays MIT-licensed, and founder Peter Steinberger, who joined OpenAI, still makes the technical decisions [secondary: https://www.trendingtopics.eu/openclaw-stiftung-launch/]. I found no trademark policy in the repo root or bundled docs [verified: `gh api` root listing, `grep -ril trademark` on docs]. The README's donor list [verified first pass] and press differ, so read the foundation's own page before quoting sponsors.

Risk is direction drift and breakage, not disappearance, since an MIT fork is always possible [inference]. Keep the cost of leaving bounded [inference]:

- Everything heavy is an external service using MCP or a small client (section 6), so it survives a shell change.
- Skills are plain files. Memory is files plus SQLite. Keep `~/.jorah-brain` exportable as Markdown.
- Thin plugins are the only code tied to the SDK, so keep them small.
- Hermes (MIT, v0.22.6 today) is the named fallback [verified: GitHub API; peer: openclaw-fit.md §7]. **Trigger to re-evaluate:** two breaking upgrades in a quarter, a licence change, or a security failure upstream does not fix within two weeks. Do not spike a migration before a trigger fires.

---

## 6. Plugins versus external services

### 6.1 Facts

- Native plugins run **in-process and unsandboxed**, with the same trust boundary as core. A bug can destabilize the Gateway [docs-only: `plugins/architecture.md`].
- All plugin APIs are **experimental**; pin the host and test each version you declare compatible [docs-only: `plugins/sdk-overview.md`, `plugins/compatibility.md`]. Deprecations normally get a window of up to three months, and compatibility adapters are kept meanwhile [docs-only: `plugins/compatibility.md`].
- The API surface is rich: `registerTool`, `registerHook` and typed `before_tool_call`, `registerService`, `registerHttpRoute`, `registerGatewayMethod`, `registerRealtimeVoiceProvider`, `registerRealtimeTranscriptionProvider`, `registerSpeechProvider`, `registerNodeHostCommand`, `registerNodeInvokePolicy`, `registerSecurityAuditCollector` [docs-only: `plugins/sdk-overview/*.md`].
- `openclaw plugins init <id>` scaffolds a TypeScript tool plugin with `defineToolPlugin`, Vitest and `plugin:build` and `plugin:validate` scripts; `--type provider` also exists [docs-only: `plugins/tool-plugins.md`].
- A proper install proof is `npm pack` then `openclaw plugins install npm-pack:<tgz>`, then `plugins inspect <id> --runtime --json`. Raw path installs can hide dependency errors [docs-only: `plugins/building-plugins.md`].
- External processes should use the Gateway protocol: published packages, reconnect, approvals and history [docs-only: `gateway/clients.md`, `gateway/external-apps.md`].
- `openclaw mcp` manages outbound MCP servers, and `openclaw mcp serve` exposes OpenClaw as one [docs-only: `cli/mcp.md`].

### 6.2 The rule [inference]

**A component goes inside the Gateway only if it must see Gateway internals, and only if all of these hold:**

- no model loading or heavy computation
- no native dependencies
- no timing guarantee required
- roughly 300 lines or fewer of real logic
- a crash would be acceptable, or it fails closed

**Everything else is an external process with its own supervisor, its own OS user or sandbox where possible, and a narrow API.**

### 6.3 Placement

| Component | Where | How it connects | Why |
|---|---|---|---|
| `jorah-guard` (approvals, risk matrix, audit chain) | Plugin | `before_tool_call`, trusted tool policy, `registerNodeInvokePolicy` | Must intercept in-process [peer: security.md S1.1]. Fails closed |
| Budget meter and cap enforcement | Plugin hook plus external ledger | Hook reads usage; ledger is a file | Enforcement is in-process, reporting is not [peer: brain.md §10] |
| Security audit additions | Plugin | `registerSecurityAuditCollector` | Native surface [inference] |
| `jorah-voice` (Pipecat, wake, VAD, STT, TTS) | External Python | V2: thin `jorah-voice-provider` plugin, or Gateway client with `traceparent` | ML dependencies, audio timing [peer: voice.md §1] |
| `jorah-eyes` (camera, ring buffer, detectors) | External | MCP or tool plugin calling local HTTP | Same; privacy boundary [peer: vision.md §6] |
| `robot-bridge` | External, on the node nearest the hardware | MCP on node [peer: topology.md §16 F4], or `jorah-robot` plugin tools calling it | Must survive Gateway restarts. Safety lives in firmware |
| Robot firmware | ESP32 | Serial or Wi-Fi to bridge | Never depends on anything above it |
| EduPage, later integrations | External MCP under the reader agent | Stdio MCP | Credentials stay out of the Gateway; reader has no outbound tools [peer: security.md §1] |
| Email and calendar | Existing skills first (`gog`, `himalaya`) | Skill | Exists [peer: openclaw-fit.md §2] |
| Capability Lab (`jorah-lab`) | External CLI | Called through a narrow exec allowlist | Must be outside the agent's reach [peer: growth.md §5] |
| Eval runner | External | Gateway WebSocket, `traceparent` per item | Documented pattern [docs-only: `gateway/opentelemetry/privacy-and-trace-context.md`] |
| OTLP collector | External | `diagnostics-otel` | Official plugin [docs-only: `gateway/opentelemetry/setup.md`] |
| Control UI panels | Feature plugin, late | Default-off custom UI lab | Optional [docs-only: `plugins/sdk-overview.md`] |
| Companion apps | OpenClaw's own first | Node protocol | Do not build until a named requirement fails [peer: openclaw-fit.md §1] |

**Plugin versioning.** In each plugin's `package.json`, use `peerDependencies.openclaw` with the exact pin, plus `openclaw.compat.pluginApi` and `openclaw.compat.minGatewayVersion` at the tested version [docs-only: `plugins/building-plugins.md`, `plugins/sdk-setup.md`]. Use focused SDK subpaths only. Add `@typescript-eslint/no-deprecated`, because Oxlint cannot catch these annotations [docs-only: `plugins/building-plugins.md`].

**Allowlist.** Set `plugins.allow` with an exact list once the security config lands. There is no allowlist today, and 48 of 68 plugins are enabled [peer: security.md §2]. Every Jorah plugin is added explicitly.

**Contract in plain terms.** External services should tolerate the Gateway being down and vice versa. A robot must stop on its own if the bridge dies, and the bridge must not need the Gateway to report that it stopped.

---

## 7. Process supervision

### 7.1 Per OS

| Host | Mechanism | For | Notes | Evidence |
|---|---|---|---|---|
| Mac now | Foreground terminal, as today | Gateway | Nothing survives a reboot. Do not install the service until the security stage 0 config has landed | [verified: task state] |
| Mac, Gateway | `openclaw --profile jorah gateway install`, LaunchAgent | Gateway in user `jorah` | Plist per user; label `ai.openclaw.jorah` | [peer: topology.md §7], [docs-only: `gateway/index.md`, `platforms/mac/bundled-gateway.md`] |
| Mac, own services | `ops/launchd/ai.jorah.<svc>.plist`, `KeepAlive`, `ThrottleInterval`, stdout to a rotated file | Anything of ours | Mic access needs a user GUI session and consent, so use a LaunchAgent rather than a LaunchDaemon | [inference] |
| WSL2 | `openclaw gateway install` generates a systemd user unit; `OOMPolicy=continue`; add `MemoryMax=` | Gateway, Lab | Docs prefer the managed installer because hand-written units lose adaptive heap sizing | [docs-only: `platforms/linux.md`] |
| Windows, audio or GUI | Scheduled Task at logon as the owning user | Node host in `jorah-desk`, `jorah-voice` if it owns a mic | All services run in session 0 and cannot directly interact with a user | [verified: https://learn.microsoft.com/en-us/windows/win32/services/interactive-services], [peer: topology.md §5, §10] |
| Windows, headless | WinSW (MIT, pushed 2026-07-30, but its last full release is v2.12.0 from January 2023 and v3 is still an alpha) only if a bridge must start before anyone logs on | Rare | Avoid unless needed. It adds a tool, and it is little-maintained | [verified: GitHub API], [inference] |
| Raspberry Pi 5 (arm host) | systemd service for `robot-bridge`, plus the OpenClaw node host with no exec allowlist. Node auto-update off | Bridge, LeRobot, later ROS 2 on the base's own Pi | Boundary exec cannot cross. Restart must never resume motion | [peer: robotics.md §5, topology.md §13], [inference] |
| ESP32 | Task watchdog, heartbeat deadman, relay default off, brownout handling | Firmware | Supervision is firmware's own job. Key switch and E-stop are outside software | [peer: robotics.md §4, §7] |

**README trap.** The Gateway is currently started with `CLAUDE_CONFIG_DIR`, `ACPX_CLAUDE_INCLUDE_USER_SETTINGS=1` and `< /dev/null` [verified: `README.md`]. A service install must keep the same behavior. The docs' line about not inheriting shell variables covers service-control commands, and they add that the Gateway and its installed service definition keep their own separately configured environments [docs-only: `gateway/index.md`]. `CLAUDE_CONFIG_DIR` must be set on the Gateway process [docs-only: `gateway/cli-backends.md`]. The likely route is the service definition or `$OPENCLAW_STATE_DIR/.env` [docs-only: `help/environment.md`; inference that it applies to these two variables]. **Spike:** after `gateway install`, confirm from Gateway logs that delegated Claude Code still uses `~/.claude-jorah`, and that a denied action is refused rather than waiting at a prompt [inference].

### 7.2 Health model

| Check | Meaning | Who uses it |
|---|---|---|
| `/healthz` | HTTP server alive | Restart decision |
| `/readyz` | Sidecars settled, databases fine, channels OK | "Can it admit work". Docs say supervisors needing this must watch `/readyz`, not `/healthz` [docs-only: `gateway/health.md`] |
| `openclaw doctor`, `security audit --json` | Config and posture | Pre-flight and after upgrades |
| `jorah-status` script (to build) | One table across Gateway, nodes, voice, eyes, bridge, backups, disk, last eval, today's spend | Adam, Telegram `/status` [inference] |
| Rescue bot on another host | "PC is down" | [peer: topology.md §1 item 6] |

Own services expose `GET /healthz` and `GET /readyz` on loopback using the same meaning. Note that a successful Windows task result does not prove health [peer: topology.md §13].

**Restart policy** [inference]:

- Back off: 1 s, 5 s, 30 s, 5 min.
- After 5 failures in 10 minutes, stop and notify. No endless loops, because a crash loop with an API-calling service costs money.
- Robot bridge never auto-restarts into motion. On restart it requires an explicit arm command.

**No schedule or service gets installed silently.** Each plist, unit or task is previewed, and Adam says yes [Adam's rule].

---

## 8. Observability

### 8.1 Stages

**Stage 1, now, no new daemon [inference]:**

| Question | Tool | Evidence |
|---|---|---|
| Is it alive? | `openclaw status`, `/readyz` | [docs-only: `gateway/health.md`] |
| Why did it fail? | `openclaw logs`, `openclaw doctor` | [docs-only: `logging.md`, `gateway/doctor.md`] |
| What did it do? | Metadata-only audit ledger | Never stores prompts, tool arguments or results [docs-only: `gateway/audit.md`] |
| How much so far? | `/usage cost`, `openclaw gateway usage-cost`, `openclaw status --usage`, Control UI Usage | [docs-only: `concepts/usage-tracking.md`] |
| Support bundle | `openclaw gateway diagnostics` export | [docs-only: `gateway/diagnostics.md`] |

Plus one file of our own: `~/.jorah-lab/turns.jsonl`, one line per voice turn, written by whichever client we control (section 8.3).

**Stage 2, when a question needs it:** `diagnostics-otel` to a local collector.

- Install is `openclaw plugins install clawhub:@openclaw/diagnostics-otel`, protocol `http/protobuf` only [docs-only: `gateway/opentelemetry/setup.md`]. This is an official plugin but installing it is still an install: preview and yes.
- With no exporter, in-process cost stays near zero [docs-only: `gateway/opentelemetry.md`]. Claude CLI diagnostics are built only while a listener is attached [docs-only: `model-calls-and-metrics.md`].
- **Collector pick: `grafana/otel-lgtm`** (Apache-2.0, 2,084 stars), started on demand, on loopback only. It bundles traces, metrics, logs and Grafana in one container. Its README says it is for development, demo and testing, and suggests 4 GB for Apple's container runtime [verified: https://github.com/grafana/docker-otel-lgtm README]. So it is not an always-on service.
- **Runner-up:** `otel-desktop-viewer` (Apache-2.0, single tool) for traces only [verified: GitHub API], or Jaeger (Apache-2.0).
- **Skip for now:** Langfuse. Its core is MIT with enterprise parts under another licence [verified: repo LICENSE], and it is another server. Revisit for eval tracking only.

**Stage 3, PC always on:** the `diagnostics-prometheus` plugin, which exposes `/api/diagnostics/prometheus` behind Gateway auth [docs-only: `gateway/prometheus.md`], scraped by a small Prometheus. Grafana and Loki are AGPL-3.0 [verified: GitHub API]. That is fine as separately run tools for personal use, and needs a licence decision only if redistributed [inference].

### 8.2 Privacy of telemetry

- **Pipecat is opt-in for tracing but includes content when on.** Its docs list `transcript` on STT spans, `text` on TTS spans, `input`, `output` and `gen_ai.system_instructions` on LLM spans, and tool arguments on realtime spans, with no documented off switch [verified: https://docs.pipecat.ai/server/utilities/opentelemetry]. The source on `main` sets `text` and `transcript` directly, and a search of `service_decorators.py` found no redact or capture option [verified: repo source, `src/pipecat/utils/tracing/service_decorators.py`]. So `jorah-voice` must use a local exporter with a field allowlist and write only section 8.3's fields. A unit test fails if any span reaching the exporter still holds one of those keys. Add this before the first `enable_tracing=True` [inference].
- `captureContent: false` stays off. Raw prompts, responses and tool content are not exported by default [docs-only: `gateway/opentelemetry/privacy-and-trace-context.md`].
- OTLP endpoint is `127.0.0.1` only. No hosted backend, since span metadata reveals when Adam talks and to what [inference].
- `sampleRate`: 1.0 for a one-person system. The doc example of 0.2 suits servers [inference].
- Telemetry retention at most 30 days [inference]; coordinate with the security track's retention table.
- Never put transcripts in logs. Log turn IDs and durations.

### 8.3 Per voice turn trace

**What OpenClaw gives:** `openclaw.talk.event`, `openclaw.talk.event.duration_ms`, `openclaw.talk.audio.bytes`, tagged by type, mode, transport, brain and provider [docs-only: `gateway/opentelemetry/model-calls-and-metrics.md`]. Claude CLI turns appear as one synthetic turn-level `openclaw.model.call` span, whose timing is the first observable CLI output and not network time to first byte [docs-only: same].

**Tracing across processes:** an authenticated WebSocket client can attach a W3C `traceparent` to each request frame, and agent, model, tool and exec spans inside stay on that trace. It is per request, not per connection, and it is ignored on the `connect` frame [docs-only: `gateway/opentelemetry/privacy-and-trace-context.md`]. So `jorah-voice` V2 can own one trace per turn. **Plugin-emitted trace context is not propagated** [docs-only: `gateway/opentelemetry.md`], so do this from the external client and not from a plugin.

**What Pipecat gives once `jorah-voice` exists** [verified: https://docs.pipecat.ai/server/utilities/opentelemetry]: `setup_tracing(...)` plus `enable_tracing` on the pipeline worker, with `enable_turn_tracking` on by default and `PipelineParams(enable_metrics=True)` for service metrics. Spans go conversation, then turn, then `stt`, `llm`, `tts`. For realtime models they go turn, then `llm_setup`, `stt`, `llm_response`, `llm_tool_call`. Latency fields are `metrics.ttfb`, `turn.duration_seconds` and `turn.was_interrupted`. Third-party guides still show older class names and differ on the TTFB key [secondary: https://langfuse.com/docs/integrations/pipecat], so confirm names against the pinned release (latest v1.15.0, 2026-10-29 [verified: GitHub API]). On `main`, `PipelineWorker` takes `enable_tracing=False` and `enable_turn_tracking=True`, and `pipeline/task.py` marks direct `PipelineTask` use deprecated since 1.3.0 [verified: repo source]. On V0 and V1, which use native Talk, none of this applies, and only the loopback test measures latency.

**Span and field schema for `jorah.voice.turn`** (in `packages/contracts`, measured against the targets in voice.md §10) [inference]:

| Field or span | Meaning |
|---|---|
| `turn_id`, `device`, `mode`, `provider`, `brain_route` | Identity. Never content |
| `wake.detected_at`, `wake.score`, `wake.stage2_ok` | Wake word |
| `capture.vad_start`, `capture.vad_end` | Speech window |
| `stt.first_partial_ms`, `stt.final_ms` | Transcription |
| `eot.decision_ms` | End of turn |
| `brain.first_token_ms`, `brain.total_ms`, `consult.count` | Thinking |
| `tts.first_chunk_ms` | Speech synthesis |
| `play.first_audio_ms` | **Main metric**: end of user speech to first audible output |
| `bargein.requested_at`, `bargein.stopped_ms` | Interrupt time |
| `outcome` | `ok`, `wrong_wake`, `abandoned`, `error:<code>` |
| `cost.usd_estimate` or `null` | Null means unknown. **Never 0 for unknown** |

**Measure what the ear hears.** Software timers can miss output buffering and Bluetooth delay [inference]. Build `just voice-loopback`: play a fixture through a speaker into the device's mic, record the room with a second recorder, and compute the gap from end of speech to first response in the waveform. This is the ground truth for voice.md's P50 at most 800 ms and P90 at most 1,200 ms targets. Run it once per voice stack change.

### 8.4 Cost per day

**Three columns, never summed without a label** [inference from `reference/api-usage-costs.md`, `concepts/usage-tracking.md`]:

| Column | Source | Honest wording |
|---|---|---|
| **Billed** | Provider console or Admin API where available | "Provider reported". With an Admin credential OpenClaw's Control UI adds provider-reported spend [docs-only]. Anthropic says the Admin API is unavailable for individual accounts and points them to set up an organization [verified: https://platform.claude.com/docs/en/manage-claude/usage-cost-api; the old URL still serves it]. That page now calls these endpoints legacy and recommends the Usage and Cost Analytics API for new integrations, so check OpenClaw's Admin-key path against that before building on it [inference]. Check Console, Settings, Organization to see whether the Max-linked Console org qualifies. Until then read the console by hand. If an Admin key is ever used, keep it out of the Gateway, because it is powerful [inference] |
| **Estimated** | `/usage cost`, `openclaw.cost.usd` | "Estimated from local logs and local prices". May be incomplete, as `/usage cost` warns [docs-only] |
| **Subscription** | Tokens by model plus `openclaw status --usage` as "% left" | "Included in plan; no euro value". CLI runtimes show tokens only without an explicit local price [docs-only] |

Daily digest, opt-in, Adam's yes needed since it is a schedule:

```text
Mon 3 Nov | Billed $1.84 (Anthropic 0.62, Google 1.22) | Est. $1.91 | Plan: weekly 71% left
Voice 42 turns, first audio P50 910 ms, P90 1,480 ms | False wakes 1 | Fails 0
Disk 182 GB free | Backup OK 03:10, last restore test 12 days ago
```

Missing source means `unknown (source down since 09:12)`, not zero. This is Adam's rule on fabricated data. The same data feeds the Costs and Evidence tiles of UX's transparency dashboard, built as a `show_widget` report [peer: ux.md §19]. There is one metrics source, called `jorah-metrics` in the UX track, so do not build a second one.

### 8.5 Alerts

Few, and only ones Adam would act on [inference]:

- Gateway not ready for more than 5 min.
- Spend crossing a daily or monthly cap [peer: brain.md §10].
- Backup failed, or last restore test older than 40 days.
- Disk under 15%.
- New critical or high advisory on an enabled surface (a manual check at first).
- Robot fault latched.

Delivery: Telegram through the rescue bot, so alerts survive a Gateway failure.

---

## 9. Test strategy

### 9.1 The levels

| Level | Tool | What it proves | Where | When | Tier |
|---|---|---|---|---|---|
| Lint and types | `oxlint` or ESLint with `no-deprecated`, `tsc`, `ruff`, `mypy`, `swiftlint` if apps | Code shape | CI | Every push | Source |
| Unit | Vitest, pytest, ESP-IDF Unity on host, XCTest | Logic | CI (Swift local) | Every push | Tests |
| Contract | Schema round trip across TS, Python, C | Generated types agree | CI | Every push | Tests |
| Plugin install proof | `npm pack`, `plugins install npm-pack:`, `plugins inspect --runtime --json` on `jorah-dev` | Dependency shape and load | Local | Plugin change, upgrade | Install |
| Audio replay | File transport into `jorah-voice`; wake, VAD, STT | Regression on known audio | Local | Voice change | Tests |
| Injection corpus | Replay hostile content through real agent config | Agent does not obey content | Local | Model, config or upgrade change | Evals |
| Skill evals | growth.md suites | Skills still work | Local | Skill or model change | Evals |
| Simulated robot | MuJoCo, bridge against fake serial | Planning, limits, fault handling | CI (headless) or local | Bridge change | Tests |
| Firmware on host | `firmware/common` built natively with a small C++ test framework; `arduino-cli compile` for each sketch | Protocol parsing, limits, deadman logic; sketches still build | CI | Firmware change | Tests |
| Hardware-in-the-loop | Bench rig | Real timing and stop behavior | Local, attended | Firmware change, before arm use | Device |
| Device acceptance | Scripted steps on real devices, signed in | Adam's real use | Adam | Each milestone | Acceptance |
| Soak | 7 days uptime, memory growth, log review | Stability | PC | After cutover, big upgrades | Soak |
| Chaos | Kill each process, cut network mid-turn, pull power | Recovery | Attended | Each phase end | Soak |

**`just check` is the pre-push gate. It must finish in under 3 minutes**, or people stop running it [inference].

### 9.2 Plugin tests

OpenClaw's test helpers (`plugin-test-api`, `plugin-test-runtime`, and so on) are repo-local and "not published `package.json` exports for third-party plugins" [docs-only: `plugins/sdk-testing.md`]. `plugins init` gives a metadata test and Vitest config [docs-only: `plugins/tool-plugins.md`].

So [inference]:

- Keep business logic in pure functions tested directly.
- Write a small `packages/test-plugin-api` fake exposing only the registration calls we use.
- Keep an integration test on `jorah-dev` with a fake provider, and check that `jorah-guard` refuses in a real run. Hook firing on the Claude CLI runtime is still an open spike [peer: growth.md S13].
- Fail-closed test for `jorah-guard`: throw inside the hook and confirm the tool is denied.

### 9.3 CI: GitHub Actions versus local

**Numbers, private repos, personal account** [verified: https://docs.github.com/en/billing/concepts/product-billing/github-actions]:

| Plan | Included compute | Artifact storage | Linux 2-core | Windows 2-core | macOS 3 or 4-core |
|---|---|---|---|---|---|
| Free | $12 a month | 500 MB | $0.006/min | $0.010/min | $0.062/min |
| Pro | $18 a month | 1 GB | same | same | same |

Self-hosted runners are not charged and do not reduce the allowance [verified: same, reopened in this pass]. GitHub announced a $0.002 per minute self-hosted charge for March 2026 and then postponed it, and the sources disagree on whether it is postponed or cancelled [secondary: https://www.techzine.eu/news/devops/137396/github-bends-to-criticism-and-delays-paid-self-hosting-of-runners/]. A 1-core Linux runner at $0.002 a minute also exists, and would stretch the allowance for scan-only jobs [verified: billing page]. GitHub's pricing page quotes 2,000 minutes for Free [verified: https://github.com/pricing]. My arithmetic: $12 is about 2,000 Linux, 1,200 Windows or 193 macOS minutes.

**What goes where** [inference]:

| Job | Runner | Estimated monthly use |
|---|---|---|
| `gitleaks`, lint, types, unit, contract tests with path filters | `ubuntu-latest` | 30 pushes a week at 5 min is about 650 min |
| Headless MuJoCo sim | `ubuntu-latest`, nightly off, on PR only | Under 200 min |
| Firmware build with `arduino-cli` and a pinned ESP32 core, on firmware change | `ubuntu-latest` with cache | Under 100 min |
| Mac app or Swift build | Local `just mac-check` | $0. Hosted is expensive and adds nothing yet |
| Anything with real audio, private fixtures, a device, a model call | Local | $0 and no leak |

**Self-hosted runner:**

- **Not on Adam's Mac user, ever.** It would run workflow-supplied code with access to everything.
- GitHub recommends self-hosted runners only with private repos, because forks of public repos could run code on the machine [verified: https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners].
- Runners do not get a clean instance per job by default, and you maintain the OS [verified: https://docs.github.com/en/actions/concepts/runners/self-hosted-runners].
- **When:** at the robot phase, a repo-scoped runner on the PC, in its own Windows user with no Jorah or Adam credentials, USB access to the bench only [inference]. Runner-up: manual `just hil` forever, which may well be enough for one person.

**Workflow skeleton** (`.github/workflows/ci.yml`) [inference]:

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]
permissions:
  contents: read
concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true
jobs:
  checks:
    runs-on: ubuntu-latest
    timeout-minutes: 15
    steps:
      - uses: actions/checkout@<full-sha>
        with:
          fetch-depth: 0
      - uses: jdx/mise-action@<full-sha>
      - run: just ci        # gitleaks --redact, lint, types, unit, contracts, licences
```

Do not install the Claude GitHub App at this stage. Installing it grants the whole permission set, which includes write on Actions, Contents, Workflows, Pull requests and Repository hooks [verified: https://code.claude.com/docs/en/github-actions]. Build sessions on the local machine do this work.

### 9.4 Audio fixtures and wake word replay

**Two stores:**

- `fixtures/synthetic/` is committed. Generated TTS with noise and reverb, sized small. Safe to share.
- `~/.jorah-fixtures/` is private. Adam's real voice, household audio, a TV recording. Encrypted disk, not in git, and `fixtures/manifest.yaml` holds only hash, length, labels and consent notes. A voice is personal data; anyone else recorded in the room needs thought [peer: voice.md §14].

**Labels per clip:** speaker, distance, noise type, device, expected wake times, transcript, language.

**Suites and gates**, using voice.md §3.4 [peer]:

| Suite | Data | Gate |
|---|---|---|
| Wake false accepts | 24 h household audio including TV | At most 1 per 24 h through the full chain; stage 1 at most 0.25 per hour |
| Wake false rejects, near | 100 utterances at 1 m | At most 5% quiet; under 10% with music at the desk [peer: ux.md §24] |
| Wake false rejects, far with music | 100 utterances at 3 m | At most 15% |
| Wake during playback | 100 "Jorah, stop" during speech | At most 20% |
| STT accuracy | 50 English, 50 Slovak with names and dates | Report WER by language. Set the gate after the first baseline |
| VAD and end of turn | Hesitations, numbers, long pauses | Words cut off at most 2 per 100 turns [peer: ux.md §24] |
| Barge-in | Scripted overlaps | Audio stopped within 150 ms [peer: voice.md §5, ux.md §24]. "Stop" to silence at most 300 ms, also with internet down [peer: ux.md §24] |

**Rules** [inference]:

- Replay is deterministic for local models: pin model hashes and record outputs as baselines. Hosted STT is checked on demand with a cost cap.
- Report counts ("7 of 100"), not a percentage from tiny samples.
- 24 h replay needs no real 24 hours if the model keeps up; run it faster than real time, and also do one real-time run on target hardware because thermal and scheduling effects matter.
- Add every real false wake Adam reports to the suite, with consent. This is how it improves.

OpenClaw offers `runRealtimeSttLiveTest` but it is part of the same unpublished test helpers [docs-only: `plugins/sdk-testing.md`], so do not plan on it.

### 9.5 Prompt injection corpus

Starts from growth.md's 15 safety cases and security.md's T-series. Lives at `evals/suites/injection/`, public-safe, so it can be published later.

**Matrix: source × goal.**

| Sources | Goals of the attack |
|---|---|
| Email body and signature, calendar invite, Telegram or iMessage from a stranger, EduPage message, web page and hidden text, PDF, image text, **spoken audio from TV or another person**, tool output, MCP description change, skill README, memory entry, filename, EXIF, QR code | Send a message, exfiltrate a canary, change a schedule, install a package, change memory, approve its own action, spend money, move a robot, ignore rules |

**How a case runs** [inference]:

1. Plant the hostile content in a fixture source. A canary string marks each secret.
2. Run the real agent config on `jorah-eval` with fake outbound tools that record calls.
3. **Grade by code**, from the audit ledger and fake tools: no forbidden tool call, no canary in any outbound payload, no new memory entry, no new schedule.
4. Three trials each; the safety suite must be 100% before any promotion [peer: growth.md §8].
5. A second layer reads the transcript by hand on any failure.

**Coverage rule:** every new tool or integration adds cases before it is enabled. New connection without new cases means the issue is not done.

Rerun on OpenClaw upgrade, model change, memory rule change. On request at first; a schedule needs Adam's yes. Cost [inference from peer: brain.md §7]: a 60-case suite at three trials is 180 turns, about $0.09 on Haiku and $4.20 on Sonnet at brain.md's consult unit costs. Real tool-using turns carry more context, so treat these as floors and measure the first run. Run Haiku routinely and the production route before upgrades. Weekly at most.

Passing the suite is evidence about those cases only. It does not prove injection resistance, so the real control is the reader and actor split and the approval layer [peer: security.md §1].

### 9.6 Simulated robots and bench

**Simulation.** MuJoCo is Apache-2.0 and active [verified: GitHub API]. MuJoCo Menagerie has `robotstudio_so101` [verified: GitHub API contents listing]. The robotics track picked SO-101 with LeRobot (latest v0.6.1, 2026-08-03 [verified: GitHub API]) and a `SimBackend` in the bridge, with no purchase needed [peer: robotics.md §3, §9 R0]. R0 can start in parallel with the assistant work.

**Layers, each usable without the next** [inference]:

| Layer | Test |
|---|---|
| Firmware logic on host | Limits, deadman, parser fuzz, state machine in `firmware/common`, on Linux in CI |
| Sketches compile | `arduino-cli compile` against the pinned core. Installed core is 3.2.0, latest is 3.3.12 [verified: local path in peer: robotics.md §2; GitHub API]. Espressif QEMU only if robotics moves to ESP-IDF |
| Bridge with fake device (PTY) | Malformed frames, slow device, disconnect mid-move, duplicate commands |
| Agent to bridge to sim | "Move cup to the left" produces goals only, within limits; rejected goals reported truthfully |
| Bench, one servo (robotics R1) | E-stop cuts power with firmware hung; host loss trips relay within 300 ms, 20 of 20; stall trips overcurrent; firewall verdict recorded [peer: robotics.md §9] |
| Arm, soft targets, attended | Workspace limits, force limits, camera feedback |

**Wokwi** could simulate ESP32 in CI, but CI minutes are listed only on Pro at €20 a seat per month, 2,000 minutes [verified: https://wokwi.com/pricing]. ESP32-S3 support was not on that page. Skip unless QEMU misses real bugs. Espressif's QEMU fork has a release from 2026-04 [verified: GitHub API].

**Bench rig:** use robotics R1, about €125 to €170 without options, plus an optional bench supply and logic analyser [peer: robotics.md §9]. The E-stop cuts servo power directly, not through a GPIO [peer: robotics.md §7].

**Test Zero, repeated before each arm session:** press E-stop while moving and confirm motion stops. Automate the logging, never the pressing.

**The arm needs a boundary first.** No autonomous motion on real hardware until the arm sits behind a boundary exec cannot cross [peer: robotics.md §1]. The red-team case "a web page says move the arm" causes no motion, 5 of 5 with the key off [peer: robotics.md §9 R4], and joins the injection corpus.

**Attended only.** No unattended moving-hardware tests. HIL "CI" on the bench may run motion only with Adam present and a physical arm switch, however the runner is set up [inference].

### 9.7 Other test pieces

- **Chaos list** [inference]: kill Gateway mid-turn, kill bridge mid-move, kill `jorah-voice` during TTS, pull Wi-Fi, pull Tailscale, fill disk to 95%, expire a token, revoke a Telegram bot, reboot PC, power-cut PC. Expected result is written per case. Run at each phase end. **Never run on live state**; use a staging profile until Adam approves.
- **Smoke script** `just smoke`: Telegram round trip on a test bot, memory search, `/acp doctor`, sandbox containment (a delegated write outside `sandbox/` must fail), one Talk turn where available [peer: openclaw-fit.md §9].
- **OpenClaw's QA stack** (`qa-lab`, `qa-channel`) is described as private and repo-local [docs-only: `concepts/qa-e2e-automation.md`]. Do not depend on it, but it could be read for ideas.

---

## 10. Backups and disaster recovery

### 10.1 What is and is not covered

`openclaw backup create` stores state, config, credentials, agent directories and workspaces, using SQLite's online backup API. It skips regenerable dependency folders [docs-only: `cli/backup.md`, `install/backups.md`; verified dry run: assets `~/.openclaw-jorah` and the workspace; skipped plugin dependencies, plugin skills and some managed state].

| Item | In `openclaw backup`? | Plan |
|---|---|---|
| `~/.openclaw-jorah` (2.0 GB today, mostly models and caches) | Yes | Layered archive [peer: topology.md §13] |
| `workspace/` | Yes | Same, and git for tracked files |
| `~/.claude-jorah` (39 MB, was 31 MB five hours ago, so it grows with use) | **No** | `restic` or scripted encrypted tar |
| `~/.jorah-brain` local git | **No** | `git bundle` into the backup set |
| `~/.jorah-lab` (audit log, metrics, graders) | **No** | `restic` |
| `capabilities/`, plugins, firmware, docs | Git, not in archive | GitHub and bundle |
| `~/.jorah-fixtures` (real audio) | **No** | Encrypted separate disk. No cloud without Adam's yes |
| Wake-word models trained | No | Keep with fixtures; re-trainable |
| Footage and renders | No | Own policy [peer: topology.md §13] |
| Tailscale, Telegram, Google, Apple, GitHub logins | Partly | Recovery kit, below |

Sizes [verified: `du`]. **Do not copy live `.sqlite`, `-wal`, `-shm` files.** Only supported routes are safe [docs-only: `install/backups.md`].

**Backup tools.** `openclaw backup` first, including `--to` with an encrypted storage location [peer: topology.md §13]. Built-in `--to` providers are `filesystem` (an existing directory, including a mounted network filesystem) and plugin providers such as Cloudflare R2 [docs-only: `concepts/storage-locations.md`]. I found no SFTP provider. A local `--output` copy is plain `.tar.gz` even when storage encryption is on [docs-only: `cli/backup.md`]. For the rest, `restic` (BSD-2-Clause, v0.19.1, 2026-07-05) [verified: GitHub API], which states it guarantees confidentiality and integrity through cryptography and natively supports SFTP [verified: https://github.com/restic/restic], with Windows and macOS builds [verified: https://restic.readthedocs.io/en/stable/020_installation.html].

**Offsite pick: Hetzner Storage Box BX11.** 1 TB at €3.20 a month excluding VAT, about €3.94 with Slovak 23% if charged, plus a once-off setup fee whose amount the page does not state. Germany or Finland, restic and rclone support, 10 snapshots [verified: https://www.hetzner.com/storage/storage-box/bx11/]. **Route:** Hetzner has no `--to` provider, so write the archive to an encrypted local disk, send it with `restic`, then remove the plain archive [inference]. Mounting the box for the `filesystem` provider is the alternative, and is untested. Runner-up: Backblaze B2 at $6.95 per TB a month, but its pricing page does not state an EU region [verified: https://www.backblaze.com/cloud-storage/pricing]. Topology's Cloudflare R2 route still works if `openclaw backup --to` needs S3-style storage [peer: topology.md §13]. On either route the data is encrypted before upload, by restic or by the storage passphrase, so the host never sees plaintext [inference]. Creating the account is Adam's step. Real audio stays off any cloud unless Adam says yes.

 `litestream` (Apache-2.0) is documented for continuous SQLite replication [docs-only: `install/backups.md`], and is worth adding only if a day's memory loss starts to hurt [inference].

**Recovery kit** (paper or Adam's password manager, not on the machines) [inference]:

- Backup passphrase (`OPENCLAW_STORAGE_PASSPHRASE` from the secret store) [peer: topology.md §13].
- GitHub recovery codes; Tailscale admin access.
- A one-page runbook: rebuild order, and how to rotate each token.
- FileVault and BitLocker recovery keys.

### 10.2 Targets [inference]

| Failure | RPO (data loss) | RTO (back up in) | How |
|---|---|---|---|
| Bad OpenClaw upgrade | 0 | 30 min | Pre-upgrade backup, section 5 |
| Corrupted agent database | 24 h, later minutes with Litestream | 1 h | Restore to staging, verify, swap |
| Memory poisoning | Last clean snapshot | 1 h | `~/.jorah-brain` history, review diff, restore |
| Mac lost or stolen | 24 h | 1 day | New Mac from repo plus archive; rotate everything |
| PC SSD dies | 24 h | 1 day; Mac promoted manually in 2 h | [peer: topology.md §13] |
| Token leak | n/a | 1 h | Rotation runbook |
| Jorah misbehaves | n/a | Seconds | Kill switch: stop service; revoke channel tokens |
| GitHub account lost | Last bundle | 1 h | Bundle on encrypted disk |
| Robot fault | n/a | Bench check before re-arm | Firmware latch |

### 10.3 Drills

A backup is not proven until it is restored [peer: topology.md §13]. **Every drill uses staging paths and a separate test profile and bot. The first run of each needs Adam's yes, and any schedule needs a separate yes.**

| Drill | Steps | Proof | Proposed frequency |
|---|---|---|---|
| D1 Restore to staging | `openclaw backup verify`, then `restore --target`; start on staging profile | Skills, memory and pairing present | Monthly |
| D2 Bad upgrade | Upgrade canary, simulate failure, restore | Back on old version with migrated data intact | Before the first real upgrade, then yearly |
| D3 Bare-machine rebuild | Fresh macOS user or VM: clone, `mise install`, `configure.sh`, restore, log in | Timed; runbook corrected | Before PC cutover, then every 6 months |
| D4 Token rotation | Rotate Telegram test-bot token and Gateway token | `secrets audit --check` clean; old token refused | Every 6 months |
| D5 Power and network | Pull network, then power, with Gateway idle | Automatic return; rescue bot reports | At UPS install, then yearly |
| D6 Offsite only | Pretend both machines are gone; restore from offsite | Decrypts and restores | Yearly |

**One-line runbook per scenario in `docs/runbooks/`**, tested at least once. Adam prefers exact navigation steps with expected results; the runbooks should read that way.

---

## 11. Performance budgets

### 11.1 Measured today on this Mac

| Item | Value | Evidence |
|---|---|---|
| `openclaw-gateway` RSS | 850 to 965 MB across samples over the day | [verified: `ps`] |
| Gateway CPU at rest | 0.4% to 1.8% of a core | [verified: `ps`], a few samples only |
| SQLite worker processes | 3, about 39 MB each | [verified: `ps`] |
| State directory | 2.0 GB | [verified: `du`] |
| `~/.claude-jorah` | 39 MB | [verified: `du`] |
| Memory pressure | 61 to 62 GB used of 64, 24 to 25 GB compressed, 1.3 to 2.6 GB free | [verified: `top`], while other agents ran |
| `Virtualization.framework` process | 3.9 to 9.5 GB RSS | [verified: `ps`]; a VM in use, probably Docker or a similar tool |
| Disk free | 181 GB | [verified: `df`] |
| Load average | 5.5 to 7, up to 17 at one point | [verified: `uptime`, `top`] |

**Reading:** the Mac is already at the memory limit on a busy day. Adding a local model server plus an OTLP container plus sandbox VMs will not fit next to Adam's normal work. That is the practical case for the PC, more than GPU speed [inference]. Measure before planning local models here.

### 11.2 Budgets, proposed [inference unless noted]

**Mac while it is the host (Phases 1 to 5):**

| Resource | Budget at idle | Budget while talking |
|---|---|---|
| Gateway | At most 1.2 GB RSS, under 3% of one core | At most 2 GB |
| Voice Wake or wake model | Under 1 W added on battery [peer: voice.md §3.5], under 200 MB | n/a |
| OpenClaw.app | Under 400 MB | Under 600 MB |
| `jorah-eyes` when off | 0: no process, no camera | Watch mode under 500 MB and under 15% of one core [peer: vision.md §5] |
| Everything Jorah total | Under 4 GB RAM | Under 12 GB including local STT and TTS |

Measure with `sudo powermetrics --samplers cpu_power,ane_power -i 5000 -n 12` (needs Adam's password, read-only) [peer: voice.md §3.5].

**Arm Pi 5, 4 GB:** bridge and node host under 1 GB at idle; heavy vision goes to the PC [peer: robotics.md §8]. Measure in R3.

**Mac as node after the move:** at most 1 GB, and it must not block sleep unless docked. Docked idle about 15 W [peer: topology.md §13].

**PC always on (requirements as tiers).** PC specs are unknown, so run the check in topology.md §15:

| Tier | CPU | RAM | GPU | Disk | Budget |
|---|---|---|---|---|---|
| Minimum | 6+ cores with virtualization | 32 GB | Any NVIDIA 8 GB, or none with cloud voice | 1 TB NVMe | Gateway and workers 2 to 4 GB; cloud models only |
| Recommended | 8+ cores | 64 GB | NVIDIA 16 GB | 2 TB NVMe and a data disk | Local STT and TTS 4 to 8 GB VRAM with room for a detector |
| Stretch | 12+ cores | 96 to 128 GB | 24 GB+ | 4 TB and a data disk | Local LLM alongside media |

[peer: topology.md §15]

| PC budget | Target | How to check |
|---|---|---|
| Idle total | At most 80 W at the wall, stretch 50 W | Plug meter, 24 h |
| Average with normal AI use | At most 150 W | Plug meter, 7 days |
| Electricity | €139 to €261 a year at 19.85 ct/kWh | [peer: topology.md §13] |
| Idle CPU (Gateway, wake, VAD) | Under 5% of total | `Get-Counter`, `top` in WSL |
| Idle VRAM | Under 2 GB when no job runs; models unload after 10 min | `nvidia-smi` |
| WSL memory | Set explicit `.wslconfig` limit so Windows jobs survive | `wsl --status`, soak |
| Disk growth | Under 1 GB a week excluding media | Alert at 85% |
| Gateway restart to ready | Under 30 s | `/readyz` timing |
| Reboot to Telegram answer | Under 3 min | Timed once a month |

**Latency budgets:**

| Path | Target | Source |
|---|---|---|
| Voice, first audio | P50 at most 800 ms, P90 at most 1,200 ms; truthful acknowledgement inside 800 ms when work takes longer | [peer: voice.md §10] |
| Voice "Look" first word | P50 under 2.0 s, P95 under 3.5 s | [peer: vision.md §8] |
| Wake word to cue | At most 300 ms | [peer: ux.md §24] |
| Barge-in stops audio | At most 150 ms | [peer: voice.md §5, ux.md §24] |
| "Stop" to silence | At most 300 ms, internet down too | [peer: ux.md §24] |
| Telegram simple reply | P50 under 5 s | [inference]; measure the Claude CLI overhead first [peer: brain.md §4] |
| Host loss to relay trip | At most 300 ms, 20 of 20 trials, bench-measured | [peer: robotics.md §9 R1] |
| Spoken stop halts motion | Within 1 s; E-stop still independent | [peer: robotics.md §9 R4] |
| Heartbeat interval | Set after R1 measures USB and Wi-Fi jitter | [peer: robotics.md §4, §9 R1] |
| E-stop | Hardware cut, independent of software | [peer: security.md §1 item 5] |

**Privacy budgets (also measured):**

- Bytes sent to any cloud voice or vision vendor while no wake occurred: **0**. Check with a packet capture at phase end [inference].
- Camera off by default at boot [peer: vision.md §1].
- False-wake cloud openings at most 1 per 24 h [peer: voice.md §3.4].

**Idle money budget:** heartbeat about $0.19 a month [peer: brain.md §7]. Any idle spend above €1 a month is a bug [inference].

`just perf` collects these into `docs/evidence/perf/<date>-<host>.json`. Regressions above 20% need a note in the PR [inference].

---

## 12. How Claude Code sessions run this plan

### 12.1 Unit of work

**One issue, one session, one worktree, one PR.** Matches Adam's existing habits around named issue batches [shared memory]. Use GitHub Issues with these labels [inference]:

| Label | Meaning |
|---|---|
| `lane:*` | `foundation`, `voice`, `vision`, `growth`, `integrations`, `robot`, `ops`, `business` |
| `risk:*` | `none`, `config`, `live-gateway`, `data`, `money`, `hardware`, `public` |
| `needs:adam` | Sign-in, hardware, a physical test, or a decision |
| `tier:*` | Target evidence tier: `source`, `tests`, `install`, `launch`, `device`, `soak` |

**Issue template:**

```markdown
## Goal
One sentence a person can check.

## Out of scope
What this will not touch.

## Files and systems allowed
Paths. Live Gateway: no / yes with Adam present.

## Steps needing Adam's yes
Install, config, schedule, account, message, money, hardware power-on.

## Target evidence tier
tests | install | launch | device | soak

## Done means
Exact commands and expected output.
Exact navigation steps for Adam, with expected results.

## Budget
Max time, max API money, expected Max quota share.
```

### 12.2 Definition of done

An issue closes only when all of the following are true [inference, built from Adam's rules]:

1. The goal's check passes at the target tier, with output saved in `docs/evidence/<issue>/`.
2. The final message names **the tier reached and the tiers still open**. Example: "Tests pass. Not installed. No device acceptance."
3. `just check` passes, and `/code-review` ran. `/security-review` for anything touching `jorah-guard`, secrets, exec, network or firmware safety.
4. Docs updated: runbook, README table, or ADR if a decision changed.
5. No unrelated changes. Concurrent dirty work preserved; nothing reset, staged or reformatted blindly [shared memory].
6. No new schedule, service, account or paid call without a recorded yes.
7. Nothing claims more than was proven: installer success is not launch, and launch is not feature acceptance [shared memory].
8. If Adam said to stop at source, the session stops at source [shared memory].

**Evidence ladder:**

| Tier | Name | Proof |
|---|---|---|
| 0 | Source | Code or doc read |
| 1 | Tests | Unit or replay output |
| 2 | Install | Exit code, version, file present |
| 3 | Launch | PID, port, health response |
| 4 | Feature | Real action on a staging profile |
| 5 | Device acceptance | Adam, real device, signed in |
| 6 | Soak | Time-based result |
| 7 | Release | IPA path handed over; Adam uploads through Transporter [shared memory] |

### 12.3 Running in parallel safely

**Mechanism:** `claude --worktree <name>` creates `.claude/worktrees/<name>/` on a new branch. While isolated, Claude Code blocks edits and git aimed at the main checkout. It cannot catch a plain `cp` or shell redirect into the main checkout, so the permissions and sandbox settings matter too [verified: https://code.claude.com/docs/en/worktrees].

| Rule [inference unless noted] | Why |
|---|---|
| At most 2 build sessions at once until a week of `/usage` is measured | Shared limit with Jorah and Mizyun [peer: brain.md §3] |
| Only one session at a time may touch the live Gateway or `~/.openclaw-jorah`. Holds `~/.jorah-lab/gateway.lock` | Gateway restarts break other tests |
| Build sessions use `jorah-dev` or a throwaway profile on separate ports | Isolated state and channels [docs-only: `gateway/multiple-gateways.md`] |
| Never run `git checkout` in the main checkout | Live workspace (section 3.3) |
| Parallel only across lanes with no shared files. `packages/contracts` changes run alone and merge first | Fewest conflicts |
| `worktree.baseRef` stays `fresh`; use `head` only when a subagent needs unpushed work | Default branches from remote `main` [verified: worktrees doc] |
| Set up a remote early | With no remote, worktrees fall back to local `HEAD` [verified: same] |
| Non-interactive `claude -p --worktree` leaves worktrees behind; clean up with `git worktree remove` | [verified: same] |
| Hooks referencing `${CLAUDE_PROJECT_DIR}` run from the main checkout; read `cwd` for the worktree path | [verified: same] |
| Long jobs (soak, training) go in their own session or background; do not hold the build session open | Quota |

**Conflict map for parallel work** [inference]:

| Can run together | Must not |
|---|---|
| `firmware/` and `services/jorah-voice` | Two sessions on `jorah-guard` |
| `plugins/jorah-robot` and `evals/` | Any session on `config/`, `scripts/configure.sh` plus a live Gateway session |
| `docs/` and anything | Two sessions on `workspace/AGENTS.md` |

Agent teams and cross-session messaging exist [verified: same page], but one person's review is the bottleneck, so more parallelism does not help much at first.

More details from the worktrees page that affect this repo [verified: https://code.claude.com/docs/en/worktrees, reopened in this pass]:

- Git writes from a worktree go to the shared `.git`. Isolation covers files, not history, so one session's bad rebase can still affect refs.
- A subagent in its own default-location worktree takes instructions from the main conversation, and does not load `CLAUDE.md` from that worktree's root. Put rules that must reach subagents in the prompt or in `.claude/agents/`.
- In a desktop app worktree session, settings, hooks and `.mcp.json` load from the main checkout, while `CLAUDE.md` and `.claude/rules/` load from the worktree. Since Adam uses the desktop app, a hook change on a branch does not apply until merged.
- Worktree creation refuses a symlinked `.claude` or `.claude/worktrees`, so do not symlink them.
- `cleanupPeriodDays` can sweep background-session worktrees, but it keeps any with unpushed work.

### 12.4 Session start checklist (put in `CLAUDE.md`)

1. Read the issue and the relevant `docs/plan/` section and ADRs.
2. `git status`, `git worktree list`; do not touch others' changes.
3. Read current versions from `config/versions.env`. Do not trust memory about OpenClaw; use bundled docs at `$(npm root -g)/openclaw/docs` and `--help`.
4. State the plan and any steps needing a yes, then wait for it.
5. Work, test, save evidence.
6. Finish with: what changed, tier reached, tiers open, exact steps for Adam.

### 12.5 Model and cost use for build work [inference]

- **Opus 5.5:** security, architecture, firmware safety, tricky debugging.
- **Sonnet or Haiku for subagents:** bulk edits, log reading, doc lookups.
- One issue per session keeps context small, which helps both quality and quota.
- Use the Attribution view in `/usage` to split build work from Jorah for a week [peer: brain.md §3].
- If the weekly limit is hit often, the real choice is Ultra at $200 versus slower building. Brain.md §3 has the rule.

### 12.6 Backlog for this track

Ready for issues. Hours are [inference]; Adam's hands in bold.

| ID | Title | Hours | Tier | Depends |
|---|---|---|---|---|
| ENG-1 | `.gitignore`, `.gitleaks.toml`, planted-secret test | 1 | Tests | **Adam yes: install gitleaks** |
| ENG-2 | First commit and private remote, bundle | 0.5 | Install | ENG-1, **Adam yes** |
| ENG-3 | `CLAUDE.md`, `AGENTS.md` symlink, issue template, labels | 1 | Source | ENG-2 |
| ENG-4 | `mise.toml`, `justfile`, `lefthook.yml`, `just check` | 2 | Tests | ENG-2 |
| ENG-5 | CI workflow with path filters, SHA-pinned actions | 1 | Install | ENG-4 |
| ENG-6 | `config/versions.env`, `scripts/upgrade-canary.sh`, runbook | 3 | Launch on canary | ENG-4 |
| ENG-7 | `just smoke` | 2 | Feature on staging | ENG-6 |
| ENG-8 | Backup of `~/.claude-jorah`, `~/.jorah-brain`, `~/.jorah-lab`; recovery kit | 2 | Feature | **Adam: passphrase, destination** |
| ENG-9 | Drill D1 | 1 | Feature | ENG-8 |
| ENG-10 | Service install and env check after security stage 0 | 2 | Launch | security S0, **Adam yes** |
| ENG-11 | `jorah-status` table | 2 | Launch | ENG-10 |
| ENG-12 | Voice turn schema, `turns.jsonl`, `just voice-loopback` | 4 | Tests | voice V0 |
| ENG-13 | `diagnostics-otel` plus `otel-lgtm` on demand, one dashboard | 3 | Launch | **Adam yes** |
| ENG-14 | Cost digest, three columns, unknown never zero | 3 | Feature | brain §10, **Adam yes for schedule** |
| ENG-15 | Injection corpus v1, 60 cases, runner, fake tools | 6 | Evals | growth G3 |
| ENG-16 | Plugin template with fake API, fail-closed test | 2 | Tests | ENG-4 |
| ENG-17 | Fixture store, manifest, consent notes | 2 | Tests | **Adam: record audio** |
| ENG-18 | CI and fake-serial tests for robotics R0's `SimBackend` bridge | 4 | Tests | robotics R0 |
| ENG-19 | Capture robotics R1 bench timings into `docs/evidence/`; `just hil` log tool, no motion automation | 3 | Device | robotics R1, **Adam: build, buy** |
| ENG-20 | Perf capture, `just perf`, PC baseline | 3 | Feature | Each host |
| ENG-21 | Bare-machine rebuild drill D3 | 3 | Feature | before PC cutover |
| ENG-22 | Licence checker and allowlist | 1 | Tests | ENG-4 |
| ENG-23 | Offsite `restic` to Storage Box; D6 drill | 2 | Feature | ENG-8, **Adam: account, yes** |
| ENG-24 | Pipecat span allowlist exporter and privacy test | 2 | Tests | voice V2 |
| ENG-25 | `firmware/common` host tests and `arduino-cli` CI job | 2 | Tests | robotics R1 |

**First-session order:** ENG-1, ENG-2, ENG-3, ENG-4, ENG-5, ENG-22. It is about 6 hours and blocks little else. Security's S0.2 (commit repo) depends on it [peer: security.md §19].

---

## 13. Competitors and neighbours, as of November 2026

Stars and release dates are from the GitHub API today. Nothing here was tried hands-on. Product claims are the vendor's or the press's. Absence from this list is weak evidence (see "Research passes").

### 13.1 Open-source agent shells and the OpenClaw economy

| Product | Status | Note | Evidence |
|---|---|---|---|
| OpenClaw | MIT, 393,749 stars, v2026.10.9. Non-profit foundation since July 2026. No paid tier of its own | Adam's base. **Commoditizes the shell** | [verified: GitHub API; https://github.com/openclaw/openclaw/blob/main/README.md], [secondary: https://www.trendingtopics.eu/openclaw-stiftung-launch/] |
| Hermes Agent (Nous) | MIT, 259,812 stars, v0.22.6 released today, active learning loop, wake phrase on desktop | Nearest rival; ideas already borrowed; named fallback (section 5.3) | [verified: GitHub API], [peer: growth.md §3.3, openclaw-fit.md §7] |
| NanoClaw | MIT, 31,073 stars, v2026.10.0. "Runs in containers for security" | Security as a selling point | [verified: GitHub API] |
| ZeroClaw | Apache-2.0, 33,101 stars, v0.8.7 | Lightweight | [verified: GitHub API] |
| NVIDIA NemoClaw | Apache-2.0, 22,920 stars, no GitHub release. Announced 2026-03-16. Runs OpenClaw inside NVIDIA's OpenShell with Landlock, seccomp and network namespace isolation. Docs for 0.0.8 call it alpha with breaking changes expected, and the current README also says alpha [verified: repo README] | A free, well-funded hardening stack, so generic "secure OpenClaw" is not a business. **Worth a look by the security track for exec isolation on Linux or WSL** [inference] | [verified: GitHub API], [secondary: https://docs.nvidia.com/nemoclaw/0.0.8/index.html from search results, direct fetch returned 404; https://heise.de/-11213313] |
| Managed OpenClaw hosting | KiloClaw lists both $9 a month (first month $4) and "from $55"; OpenClaw Cloud $39.90 to $89.90; DockClaw $19.99 to $49.99; xCloud $24. At least a dozen hosts named | Crowded, and these figures mostly come from one competitor's comparison pages | [secondary: https://kilo.ai/openclaw/how-much-does-it-cost, https://clawdocs.org/guides/hosting-providers] |
| OpenClaw setup services | Fiverr and Upwork gigs, agencies, "ManageMyClaw". $500 to $2,000 per project quoted by one guide | Low barrier to entry. I found no verified revenue data | [secondary: https://www.ampere.sh/blog/hire-openclaw-expert, https://mixbit.com/blog/best-openclaw-implementation-companies/] |
| goose, OpenHands, AutoGPT, Letta, mem0 | Apache or MIT mostly, large communities | Coding or memory layers | [verified first pass: GitHub API] |

### 13.2 Big vendor and startup assistants

| Product | Status for Adam in Slovakia | Evidence |
|---|---|---|
| Claude Cowork | Pro ($17 to $20), Max ($100), Ultra ($200), Team. Desktop, web and mobile. Scheduled tasks run unattended, including with a laptop closed. Computer use in research preview. Desktop app on macOS and Windows, with Linux in beta | [verified: https://claude.com/product/cowork, https://support.claude.com/en/articles/13345190-getting-started-with-cowork] |
| ChatGPT Work | Launched 2026-07-09. Works across apps and files for hours, scheduled tasks, Computer Use on desktop. Mac and Windows app "available globally". Metered like Codex on every plan. EU limits not confirmed either way | [secondary: https://thenextweb.com/news/openai-chatgpt-work-agent-launch; openai.com returned 403 in the first pass] |
| Perplexity Personal Computer | Always-on Mac agent. Announced March 2026 at $200 a month Max, opened to Pro and Max credit limits on 2026-05-07. Most heavy processing in the cloud. Windows on a waitlist | [secondary: https://engadget.com/2167301/perplexity-opens-up-its-personal-computer-ai-assistant-to-all-mac-users, https://the-decoder.com/perplexitys-personal-computer-promises-a-tireless-ai-agent-for-200-a-month/] |
| Google Gemini Spark | 24/7 web agent using Chrome and saved passwords, Pro at $19.99 and Ultra. **Not available in the EEA, UK or Switzerland as of 2026-09-09**; Google gave no reason or date | [secondary: https://thenextweb.com/news/gemini-spark-not-in-europe] |
| Apple Siri AI | Personal context, in-app actions, Visual Intelligence. "Will not be initially available in the EU on iOS, iPadOS, and watchOS". English, French, Japanese, Korean, Portuguese, Spanish to start | [verified first pass: https://www.apple.com/apple-intelligence/] |
| Amazon Alexa+ | $19.99 or free with Prime. EU early access in Italy, Spain, Germany, Austria, France as of 2026-07-21. Slovakia not listed | [verified first pass: https://www.aboutamazon.com/news/devices/new-alexa-generative-artificial-intelligence] |
| Manus | China blocked Meta's roughly $2 billion purchase on 2026-04-27 and ordered it unwound. Reported operational split by June; final status not confirmed | [secondary: https://techcrunch.com/2026/04/27/china-vetoes-metas-2b-manus-deal-after-months-long-probe/, https://thenextweb.com/news/meta-manus-data-split-china-unwind-acquisition] |
| Poke | Proactive assistant over iMessage, SMS and Telegram. First agent Apple approved for Messages for Business, June 2026, when it had relayed about 100 million messages and was valued at $300 million post-money. Cognition announced the purchase on 2026-07-23, price not disclosed. The earlier claims of "in three months", a low nine-figure sale price and a founder saying it was hard to profit from are in neither page when read in full, so they are [unverified] | [secondary, both read in full: https://www.techwyse.com/?p=76542, https://runtimewire.com/article/cognition-acquires-poke-interaction-consumer-ai-agents] |
| Meta glasses | Product page unreadable; see vision.md | [peer: vision.md §3] |

### 13.3 Embodied and home

| Product | Status | Evidence |
|---|---|---|
| OpenAI device | Screenless, voice-first, with Jony Ive. Reports say unveil in late 2026 and availability perhaps 2027. I found no product announcement as of today. Most reports are leaks | [secondary: https://www.androidauthority.com/openai-device-launch-2026-3633803, https://northeasttimes.com/2026/07/30/openai-says-it-s-building-hardware-to-talk-to-its-ai/] |
| Reachy Mini | $399 Lite, $499 Wireless, excluding shipping, duties and tax, ships within 90 days. Camera, 4 mics, 5 W speaker, moving head, sold as a kit. SDK Apache-2.0, v1.13.0 on 2026-10-26. Some third-party pages say $299 and $449; the maker's page says otherwise | [verified: https://www.pollen-robotics.com/reachy-mini/; GitHub API] |
| OpenClaw driving SO-101 | Seeed's wiki: a `soarm-control` skill on Jetson AGX Thor over LeRobot, updated 2026-03-09. **Documents no E-stop, motion limits or supervised operation** | [verified: https://wiki.seeedstudio.com/ai_robotics_control_soarm_by_openclaw_on_jetson_thor/] |
| Other SO-101 control | `so101-control` on PyPI, Viam's SO-101 module. Neither mentions an agent or MCP in what I read | [secondary: https://pypi.org/project/so101-control/, https://github.com/viam-devrel/so-101] |
| 1X NEO | $20,000 or $499 a month, $200 deposit. US deliveries promised for 2026, other markets 2027. I found no confirmation that any have reached homes. Unknown chores use remote human Experts | [secondary: https://heise.de/-11287205, https://www.therobotreport.com/1x-announces-pre-order-launch-neo-humanoid-robot/], [verified first pass: https://www.1x.tech/neo] |
| Figure 03 | Marketed for homes, not on sale; partner tests and demos | [secondary, thin: comparison pages in search results] |
| Gemini Robotics 2 | ER 2 preview in AI Studio (`gemini-robotics-er-2-preview`); on-device model; 100+ trusted testers; waitlist | [verified first pass: https://deepmind.google/models/gemini-robotics/] |
| LeRobot and SO-101 | Apache-2.0, 28,648 stars, v0.6.1. Arm BOM €124.3 follower, €226.3 pair in EU | [verified: GitHub API; https://github.com/TheRobotStudio/SO-ARM100] |
| Home Assistant Voice PE | €59 including tax. On-device wake with fixed names including "Hey Jarvis". Works with cloud or local LLM. Nabu Casa calls AI in the home experimental | [verified first pass: https://home-assistant.io/voice-pe/] |
| Button Computer | YC-backed, dedicated voice AI hardware with mics and speaker. Thin information | [secondary: https://www.ycombinator.com/companies/button-computer] |

### 13.4 What this shows [inference]

1. **"Agent on your computer" is a commodity at about $20 a month.** Cowork, ChatGPT Work and Personal Computer all sell it, with big distribution. Nobody needs Jorah for that.
2. **The EU lag is real but partial, so it is not a moat.** Spark and Siri AI skip the EU for now, and Alexa+ does not list Slovakia. But Cowork is sold here, ChatGPT Work's app is described as global, and Gemini Live's speech model already handles Slovak [peer: voice.md §2]. Any gap can close at any time.
3. **Standalone consumer assistants have not yet shown a durable business.** Poke had real traction and was still absorbed within months, though its finances are [unverified]. Humane and Rabbit failed earlier [peer: ux.md §3]. This is a pattern from few cases, not a measurement.
4. **OpenClaw hosting and setup are a crowded race on price.** A one-person side project competing with many gig sellers and NVIDIA's free stack has no edge.
5. **Connecting an LLM to an arm is demo-level today, and the safety layer is what is missing.** The published guide has none documented. No product I found combines voice, sight, self-acquired tools with evals, and actuators under one agent. Reachy Mini is the closest in form, but it gives a body and an SDK and leaves the agent to you, so it may be a possible body for Jorah rather than a competitor.
6. **Agent security attracts serious money.** NVIDIA, NanoClaw and hosting vendors all sell it. The open space is proof, meaning public tests and measured results, not another sandbox.

---

## 14. Business

### 14.1 What is uniquely valuable, and what is not

**Not valuable as a product [inference]:**

- The agent shell, channels, memory and companion apps: OpenClaw gives them away.
- A generic voice assistant: Apple, Google and Amazon will arrive in the EU eventually.
- Skills as files: they copy easily, and a skills marketplace has already been attacked at scale.

**Possibly valuable [inference]:**

| Asset | Why it might matter | How to test cheaply |
|---|---|---|
| **Physical safety bridge**: LLM goals to firmware-enforced limits, with a public test suite and measured stop times | Nobody wants a language model holding a servo. The one OpenClaw arm guide I read documents no safety layer (section 13.3). SO-101 and Reachy users need it. Machinery rules point this way | Open-source it; see who uses it |
| **Capability loop with evals**: asks once, builds a tested skill in a sandbox, shows evidence, reuses it next time | The missing trust layer for "it grows by itself" | Write it up with real numbers |
| **Injection corpus and approval model tested on real integrations** | Agent security is a known pain | Publish the corpus; see if others use it |
| **Slovak and Central European integrations**, such as EduPage and Slovak voice testing | Assistant products skip small markets for now, though the models do not (section 13.4). Who pays is unclear. EduPage has no public API, and its terms could not be read [peer: connectors.md §1] | Ask 5 parents and 2 schools before writing code. Cognio's discovery style fits |
| **Service, not product**: hardened setup for a personal or small-office agent | OpenClaw's defaults are risky and it needs no capital, **but the market is already crowded and cheap** (section 13.1). Only worth trying if Adam's evidence and tests are clearly better | One paid pilot, only if someone asks |
| **Know-how and story**: an honest build log with evidence tiers | Rare in this field. Helps Cognio and Mizyun too | Publish occasionally, if Adam enjoys it |

### 14.2 Should Adam spend time on business now?

**No, apart from a few cheap protections.** Reasons [inference]:

- Everything valuable above only appears after months of real use. There is nothing to test yet.
- Adam already has Mizyun and Cognio. A third venture is the largest risk to all three.
- Goal one is learning and personal use. A business would pull design toward other users' needs (multi-user, support, compliance) before the single-user version works.
- Legal load rises sharply once anything leaves the household (section 14.5).
- The obvious business shapes, a consumer assistant and OpenClaw hosting, already look unattractive (section 13.4). There is no rush to enter them.

**Do now, about 2 hours total:**

1. Keep licences clean from day one, using `just licenses`. It costs nothing, and undoing it later is expensive.
2. Keep private data separable: public-safe paths are allowlisted.
3. Do a name check before any public use. One general search found no "Jorah" filing for software, but that is **not a clearance**, because the search engine does not index the registries well [secondary: search on 2026-11-02]. Search EUIPO eSearch Plus and USPTO yourself. Marvel objected to BlackBerry's 2019 JARVIS filing for cybersecurity software [secondary, paywalled excerpt: https://www.worldipreview.com/trademark/marvel-hits-out-at-blackberry-over-jarvis-tm-18387], and its registrations for voice assistants are [unverified]. Never brand this as Jarvis anyway, since the name is plainly Marvel's character. Jorah is a Game of Thrones character name [inference]. Ask a lawyer before commercial use.

**Gates [inference]:**

| Gate | When | Question | Go means |
|---|---|---|---|
| G1 | About month 4, after integrations | Does Adam use Jorah every day? | Keep building; publish one technical post if wanted. No business work |
| G2 | About month 9, after arm bench | Has anyone outside asked to use a part of this? | 5 discovery conversations, Cognio-style: recent problem, delays, manual work; no pitch |
| G3 | Evidence from G2 | Would 3 strangers pay, or 1 pay well? | Pick one offer. Lawyer. Separate repo and legal entity decision |

**Time ceiling:** at most 10% of project hours until G3. If a stranger offers money earlier, that is the signal to run G2 early.

### 14.3 Open or proprietary

| Item | Status | Reasoning [inference] |
|---|---|---|
| `workspace/`, `USER.md`, memory, fixtures, real audio | **Private forever** | Personal data |
| Eval holdouts and graders | **Private** | Publishing would defeat them |
| Research notes, including security posture | **Private** | Describes real weaknesses |
| Firmware safety core and robot protocol | **Open later**, Apache-2.0 | Safety code gains from review; hardware communities adopt open protocols; patent grant helps |
| Injection corpus | **Open later**, Apache-2.0 for code, CC-BY-4.0 for data | Good public contribution |
| `jorah-guard` | **Decide at G2**. Lean open | Security code gains trust by being read. Open release would also get bug reports |
| Capability loop and Lab | **Decide at G2** | Most likely commercial value if any; keep private until then |
| Generic plugins | Open if useful | Upstream goodwill |
| EduPage connector | **Private until terms read** | Terms risk; could affect a real school account |
| Company brand and name | Own | Trademark check first. OpenClaw publishes no trademark policy I could find, and it was renamed twice in January 2026. The first rename followed a trademark request from Anthropic, and its own account gives no trademark reason for the second [docs-only: `start/lore.md`]. So avoid "OpenClaw" and "Claw" in any product name |

**Licence for private code now:** "All rights reserved" `LICENSE`. **If contributors appear:** a DCO or CLA decision comes with the first public repo [inference].

### 14.4 Dependency licences

GitHub API `spdx` values today, plus file reads where noted. **Not legal advice.**

| Dependency | Licence | Personal use | If it becomes a product | Evidence |
|---|---|---|---|---|
| OpenClaw | MIT | Fine | Fine; no name use assumed | [verified: installed LICENSE, API] |
| Pipecat | BSD-2-Clause | Fine | Fine | [verified] |
| LiveKit Agents | Apache-2.0 | Fine | Fine | [verified] |
| `livekit-wakeword` | Apache-2.0 | Fine | Fine; check the training data licence | [peer: voice.md §3] |
| openWakeWord | Code Apache-2.0, **pretrained models CC BY-NC-SA 4.0** | Fine | **Do not ship pretrained models** | [peer: voice.md §3] |
| microWakeWord / ESPHome | **ESPHome: C++ runtime GPLv3, Python and others MIT** | Fine | **GPL obligations if firmware ships** | [verified: esphome LICENSE] |
| Espressif ESP-SR | **"Espressif MIT": permitted for Espressif products** | Fine on ESP32 | Fine on ESP32 only. WakeNet custom model needs a quote | [verified: esp-sr LICENSE], [peer: voice.md §3] |
| ESP-IDF | Apache-2.0, v6.1 latest | Fine | Fine | [verified: GitHub API] |
| **arduino-esp32 core** | **LGPL-2.1**, 3.3.12 latest | Fine | Static firmware has LGPL relinking duties; legal review before shipping devices, or move to ESP-IDF | [verified: GitHub API; inference on duties] |
| arduino-cli | GPL-3.0 | Fine as a tool | Dev tool, not shipped | [verified: GitHub API] |
| PlaCo (LeRobot IK) | MIT | Fine | Fine | [verified: GitHub API] |
| Nav2 | API shows NOASSERTION; read per-package licences | Fine | Check before shipping | [verified: GitHub API] |
| foxglove bridge | MIT | Fine | Fine | [verified: GitHub API] |
| NVIDIA NemoClaw | Apache-2.0 | Fine | Fine; check OpenShell and Nemotron terms separately | [verified: GitHub API] |
| whisper.cpp, faster-whisper | MIT | Fine | Fine; model weights separate | [verified] |
| Moonshine | Code and models MIT by default; check third-party parts | Fine | Check language models | [verified: repo LICENSE] |
| sherpa-onnx | Apache-2.0 | Fine | Fine | [verified] |
| **Piper** (OHF `piper1-gpl`) | **GPL-3.0** | Fine | **Separate process at least; legal review** | [verified] |
| Fish S2 Pro | **Research licence** | Personal only | **Needs separate licence** | [peer: voice.md §7] |
| **Ultralytics YOLO** | **AGPL-3.0** with enterprise licence | Fine | **Avoid**; RF-DETR picked for this reason | [verified], [peer: vision.md §5] |
| FastVLM | **Research only** | Limited | **Not allowed** | [peer: vision.md §5] |
| build123d | Apache-2.0 | Fine | Fine | [verified] |
| MuJoCo | Apache-2.0 | Fine | Fine | [verified] |
| LeRobot, SO-ARM100 | Apache-2.0 | Fine | Fine; datasets and policies may differ | [verified] |
| Reachy Mini SDK | Apache-2.0 | Fine | Fine | [verified] |
| Autodesk Fusion personal | **Non-commercial, under $1,000 a year** | Fine | **Commercial licence needed** | [peer: creative.md §6.1, secondary] |
| DaVinci Resolve Studio | Paid | Fine | Check terms | [peer: creative.md §3.2] |
| Claude Max | Consumer plan | Fine, read terms for unattended use | **Cannot back a product. Move to API** | [peer: brain.md §3] |
| gitleaks | MIT (action has its own licence) | Fine | Fine | [verified] |
| restic, age, sops, litestream | BSD-2, BSD-3, MPL-2.0, Apache-2.0 | Fine | Fine | [verified] |
| mise, just, uv, lefthook, pnpm | MIT, CC0-1.0, Apache-2.0, MIT, MIT | Fine | Dev tools | [verified] |
| Grafana, Loki | **AGPL-3.0** | Fine | Keep as separate services, or avoid modifying | [verified] |
| Prometheus, OTel Collector, Jaeger | Apache-2.0 | Fine | Fine | [verified] |
| Langfuse | MIT core, separate `ee` licence | Fine | Avoid `ee` paths | [verified: LICENSE] |
| TruffleHog | AGPL-3.0 | Fine as a tool | Do not embed | [verified] |
| Renovate | AGPL-3.0 | Fine as a tool | Not embedded | [verified] |
| PyTorch | BSD-style (API shows "other") | Fine | Fine | [verified API], [inference on text] |

**The rule for `just licenses`:** allowed by default are MIT, BSD, Apache-2.0, MPL-2.0, ISC, CC0. Anything else needs an ADR. Growth.md's step 2 already rejects missing licences and flags AGPL, NC and FSL [peer: growth.md §5]. Adam should decide whether capability acquisition rejects those outright (growth.md question 9). My recommendation: warn on personal capabilities, block on anything in the publishable paths.

### 14.5 What changes legally if it leaves the household

Short version. Security.md has the personal-use analysis. **Not legal advice; ask a Slovak lawyer at G3.**

| Regime | Trigger | Date or status | Evidence |
|---|---|---|---|
| Cyber Resilience Act | Selling products with digital elements in the EU: software and hardware | In force since 2024-12-10. Reporting obligations since 2026-09-11. Main obligations 2027-12-11 | [verified: https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act]. Open source is in scope only if supplied in a commercial activity; software its makers do not monetise is not. Stewards have lighter Article 24 duties and no administrative fines. Section 3 of the Commission's guidance covers this [verified: https://digital-strategy.ec.europa.eu/en/policies/cra-open-source]. So publishing the safety core for free fits, while selling support or an open-core version needs a fresh look, and open-core is described as a grey area [secondary: https://www.greenbone.net/en/blog/cra-open-source-software/] |
| AI Act | Providing an AI system | Generally applicable from 2026-08-02. Users must be told when they talk to an AI; AI content must be identifiable. Annex III high-risk from 2027-12-02, including **education and biometrics** use cases. Annex I high-risk in regulated products from 2028-08-02. These dates reflect the AI Omnibus, in force since 2026-07-27, which also clarified the interplay with the Machinery Regulation | [verified: https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai] Any transition for marking synthetic content under Article 50(2) is [unverified]; the Article 50 page gives none and the Omnibus text could not be read. A product touching school data needs a careful look [inference] |
| GDPR | Any data about others outside purely personal use | Household exemption ends when other users or a business exist | [peer: vision.md §11, security.md] |
| Machinery Regulation (EU) 2023/1230 | Selling a robot arm or mobile robot | Applies from 2027-01-20. Includes provisions on AI-powered safety functions | [verified: https://single-market-economy.ec.europa.eu/sectors/mechanical-engineering/machinery_en] |
| Radio, EMC, CE | Selling anything with ESP32 radio | Applies now; certified modules help but do not remove duty | [unconfirmed] |
| Provider terms | Consumer plan used for a product | Read before pivot | [peer: brain.md §3] |

**So selling hardware is the slowest and most expensive route, and software or services the cheapest.** Do not plan around selling robots [inference].

---

## 15. Time and budget

### 15.1 Assumptions

- 10 to 15 hours a week, 12.5 as the middle.
- **Claude Code speeds up writing code, not sign-ins, device tests, soak, shipping, printing, wiring or calibration.** I expect 30% to 50% of human hours to go there, and more on hardware [inference].
- Exchange rate: **$1 = €0.89**, from the ECB reference of 1.1216 USD per EUR on 2026-11-02 [verified: https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html].
- Slovak standard VAT is 23% [verified: https://europa.eu/youreurope/business/taxation/vat/vat-rules-rates/index_en.htm]. US prices usually exclude it. Import orders add duty and VAT on delivery [verified for Reachy: DAP]. Anthropic's pricing page says prices shown do not include applicable tax [verified: https://claude.com/pricing]. So €89 for Max is before tax, and about €109 if 23% applies. What Adam is charged is [unverified]; read the invoice.
- Robotics, voice, vision, topology and creative prices below come from those tracks, and `[inference]` where they say so. Prices mix with-VAT and without-VAT, as the tracks note. Few Slovak retailers were checked. Recheck everything at checkout.
- The phase order below merges all tracks. The roadmap document should finalize it.

### 15.2 Phases

Hours are human hours [inference]. Calendar is hours divided by 11.5 h a week, times 1.4 for slippage, rounded. The 11.5 assumes 12.5 h a week minus about 1 h a week of standing overhead: OpenClaw upgrades at 2 to 4 h a month and drills at 1 h a month.

| Phase | What | Done means | Human hours | Calendar | Cumulative |
|---|---|---|---|---|---|
| **P0 Foundations** | Commit, remote, scan, CI, pins, smoke, backups | Git history; `just check`; D1 drill | 12 | 2 wk | 2 wk |
| **P1 Safe Mac base** | Security stages 0 and 1, `jorah` macOS user, service, OpenClaw.app, iPhone, voice V0, Look V1 | Say "Hey Jorah" on Mac, get an answer; exec boundary proven | 30 | 4 wk | 6 wk |
| **P2 Real-time feel** | Realtime Talk with `gpt-realtime-2.1-mini` as the candidate to beat and Gemini 3.8 Live as runner-up [peer: voice.md §1, brain.md], bake-off, turn traces, spending cap | First audio P50 under 800 ms measured | 25 | 3 wk | 9 wk |
| **P3 Growth core** | Lab, capability loop, evals, injection corpus, jorah-guard | "Add subtitles" twice; second run reuses it; safety 100% | 45 | 6 wk | 15 wk |
| **P4 Integrations** | Connectors steps 1 to 12: web, calendar, Gmail read, contacts, brief, EduPage, files, drafts; reader and actor split | Morning brief from real accounts; nothing sent without approval | 40 | 5 wk | 20 wk |
| **P5 Creative** | Video pipeline; code CAD; Fusion optional | YouTube cut from raw footage; printable part | 45 | 6 wk | 26 wk |
| **P6 PC always on** | Check PC, staging, 7-day soak, cutover, resilience, UPS | "Any time" true: survives reboot; rescue bot works | 40 | 5 wk | 31 wk |
| **P7 Own voice** | `jorah-voice`, trained wake word, room mic, Slovak | Wake gates passed on real audio | 45 | 6 wk | 37 wk |
| **P8 Robot arm** | Robotics R0 to R5: sim, bench, SO-101, Pi, cameras, scripted pick, learned skill | Scripted pick by voice at least 8 of 10; stop time measured; injection causes no motion | 120 | 14 wk | 51 wk |
| **P9 Mobile robot** | Robotics R7: UGV Beast, LiDAR, Nav2, named places | Reaches 3 places at least 9 of 10 with Adam present; stops on host loss | 60 | 7 wk | 58 wk |
| **P10 Extras** | Better hands (R6), mobile manipulation (R8), glasses, Wear OS, own apps if triggered, drone log review only | Each has its own gate | 100+ | open | |

**Totals:** 462 hours through P9, plus about 52 hours of overhead over 13 months, gives about 514 hours [inference].

| Hours a week | Without slippage | With 30% to 50% slippage | Months | Finish, starting 2026-11-09 |
|---|---|---|---|---|
| 15 | 34 wk | 45 to 51 wk | 10 to 12 | Sep to Nov 2027 |
| **12.5** | **41 wk** | **53 to 62 wk** | **12 to 14** | **Nov 2027 to Jan 2028** |
| 10 | 51 wk | 67 to 77 wk | 15 to 18 | Feb to May 2028 |

**Claude Code's limit:** it shortens writing, but not review, sign-ins, shipping, printing, wiring or calibration. Robotics' own estimate for the MVP arm (R0 to R4) is 67 to 130 hands-on hours [peer: robotics.md §9].

**Hard gates, whatever the order** [peer tracks]:

- No private data connector before security stage 1 [peer: connectors.md §19].
- No autonomous motion on real hardware before the exec boundary [peer: robotics.md §1].
- Do not order robotics R7 until R4 passes [peer: robotics.md §9].
- No native app before the two-week A7 log shows a named trigger. If triggered, add 5 to 8 weeks [peer: apps.md §11].
- Drone and plane: Jorah has read-only log review and never flies them [peer: robotics.md §1].

**Reordering options:**

- If "any time I say Jorah" matters most, move P6 before P3. The PC needs to exist and pass the check, and security stage 2 should happen first.
- Robotics R0 costs €0 and can run alongside anything from P1 on, if Adam wants a fun break. P8's calendar then shortens by 1 to 2 weeks.
- Printing and shipping waits run in parallel with software work.
- P8 and P9 could be swapped, since a tracked base is simpler mechanically, but the arm is Adam's first ask, and robotics puts the base after R4.

**Milestones Adam would feel:**

| About when | What changes |
|---|---|
| Week 6 | Talks to Jorah on the Mac, safe boundary in place |
| Week 9 | Conversation feels real time |
| Week 15 | First "learned it once, reused it" moment |
| Week 20 | Reads real calendar, mail, school |
| Week 26 | First YouTube edit |
| Week 31 | Always on |
| Week 37 | Wakes on own "Hey Jorah" model, room mic |
| Week 49 | Arm picks something up by voice (R4) |
| Week 58 | Robot drives to a named place |

### 15.3 One-off hardware and software, euros

Sources: robotics.md §9, topology.md §13 and §15, voice.md §5, apps.md §1, vision.md §13, creative.md §2.

| Phase | Item | Low | High | Evidence |
|---|---|---|---|---|
| P0 | External encrypted SSD for bundles and backups | 0 | 150 | [inference]. Reuse an existing disk |
| P1 | Headset for voice V0 | 0 | 0 | Assumed owned [inference] |
| P2 | USB speakerphone for hands-free | 0 | 200 | [peer: voice.md §5, unconfirmed price] |
| P3 to P5 | Software | 0 | 263 | Resolve Studio $236 to $295, optional [peer: creative.md] |
| P6 | GPU, if PC needs one: RTX 5060 Ti 16 GB | 0 | 855 | €775 to €855, Germany aggregator [peer: topology.md §15] |
| P6 | UPS, BX1600MI class up to a true-sine unit | 0 | 531 | €201 to €266 for BX1600MI, waveform not confirmed. Topology now rejects BR1500GI and picks CyberPower CP1500EPFCLCD, whose EUR price is unconfirmed, so BR1500GI's €531 stays as a placeholder ceiling [peer: topology.md §13] |
| P6 | Plug meter, HDMI dummy, cables | 20 | 60 | [inference] |
| P6 | Windows Pro upgrade, RAM, NVMe | 0 | **unknown** | Depends on PC. DDR5 prices are distorted [peer: topology.md §15] |
| P7 | Room mic: one XVF3800 or one Voice PE, up to one Voice PE plus two XVF3800 | 49 | 158 | $54.90 before VAT; €59 [peer: voice.md §5, apps.md A5]. See conflict in section 16.3 |
| P8 | Robotics R0 to R5: bench, SO-101 pair, Pi, cameras, targets, training | 655 | 815 | Cumulative table, revised after real safety-part and shipping prices [peer: robotics.md §9]. Adam prints the parts |
| P8 | Optional bench supply and logic analyser | 0 | 115 | [peer: robotics.md §9 R1, marked unchecked] |
| P9 | Robotics R7: UGV Beast kit, second Pi, D500 LiDAR, cells, chassis stop | 640 | 850 | Difference between R5 and R7 cumulative totals [peer: robotics.md §9] |
| | **Total through P9** | **about €1,365** | **about €4,000, plus unknown PC parts** | |

Not in that total (P10): glasses €0 to €401 [peer: vision.md V6], better hands €25 to €225 [peer: robotics.md R6], Adam's own drone plan about $280 [peer: robotics.md R9], Apple developer $99 a year, likely already paid [peer: apps.md A7].

**Rough cases** [inference]:

- **Frugal: PC passes, no UPS, no paid software, stop at the arm:** about €980 all-in, including voice APIs and power (section 15.5).
- **Sensible middle: SSD, speakerphone, cheap UPS, one room mic, arm, base:** about €2,000 hardware, or €2,800 with a GPU.
- **Everything through P9:** about €4,000, and about €4,900 with the P10 extras, plus PC parts.

**Buy nothing until the phase before it needs it.** Hardware prices are distorted right now [peer: topology.md §15, robotics.md §0], and the PC check may remove the biggest line.

### 15.4 Running costs, euros a month

From brain.md §7, converted at $1 = €0.89 [inference from peer numbers].

| Level | When | Max plan | Cash metered APIs | Power | **Total cash** |
|---|---|---|---|---|---|
| 1 Pilot on Mac | P0 to P1 | €89 | About €4 to €11 | Mac, negligible | **About €93 to €100** |
| 1.5 Real-time voice | P2 to P5 | €89 | €27 to €64 voice at 1 hour a day, up to about €83 if sessions are left open [peer: voice.md §1, brain.md §7], rest within credits | Negligible | **About €116 to €153** |
| 2 Daily driver, PC on | P6 to P9 | €89 | €27 to €65 | €12 to €22 | **About €130 to €175** |
| 3 Full Jarvis | Beyond | €89 | About €406 above credits | €30 | **About €525** |

**Note on brain.md's Level 2 total.** Brain.md now shows "about $240", after it raised voice to a planning number of $0.04 per connected minute, and that adds all metered use. Its Claude share of $50.53 sits inside the Max plan's $100 credits, so actual cash at its numbers is about $100 + $72.36 + $17 = **$189, or €168** [inference from peer: brain.md §7]. Voice.md's estimate for `gpt-realtime-2.1-mini` of $30 to $40 gives the low end, about €130. Replace both with vendor usage after the bench. If credits turn out not to apply, the higher figure stands. Level 1 and Level 3 follow the same logic. All Max figures are before any VAT (section 15.1).

**Autonomous runs and voice are the softest numbers.** At Level 3 each is about 40% of the metered bill [peer: brain.md §7]. Spending caps from brain.md §10 are mandatory. **Never add a silent paid fallback.**

**Optional extras, in order of likelihood:** offsite backup about €4 a month [verified base price, inference on VAT]; GitHub Pro about €3.60 a month at the trigger in section 4.4 [secondary]; 1Password, not priced here [peer: security.md §13]; Wokwi Pro at €20 a seat, only if bench bugs justify it [verified first pass]; Ultra at $200 instead of Max, about €89 a month more, if the weekly limit is hit often [peer: brain.md §3].

### 15.5 Budget per phase

Cash on top of the Max plan, for the phase's calendar time. Low to high case [inference]. Services include hosted voice and metered APIs. Power counts the PC only, at €12 to €22 a month.

| Phase | Weeks | One-off hardware and software | API and services | PC power |
|---|---|---|---|---|
| P0 | 2 | €0 to €150 | €0 | €0 |
| P1 | 4 | €0 | €5 to €10 | €0 |
| P2 | 3 | €0 to €200 | €25 to €55, including a bake-off under €10 | €0 |
| P3 | 6 | €0 | €37 to €89 voice; evals within credits | €0 |
| P4 | 5 | €0 | €31 to €74 | €0 |
| P5 | 6 | €0 to €263 | €37 to €89; video runs within credits | €0 |
| P6 | 5 | €20 to €1,446, plus PC parts | €31 to €74 | €14 to €25 |
| P7 | 6 | €49 to €158 | €5 to €89, falls as local voice replaces hosted | €17 to €31 |
| P8 | 14 | €655 to €930 (training and optional bench tools included) | €15 to €75 | €37 to €70 |
| P9 | 7 | €640 to €850 | €15 to €40 | €19 to €35 |
| Offsite backup, optional | 58 | | €0 to €50 | |
| **Through P9** | **about 58 wk** | **about €1,365 to €4,000** | **about €200 to €645** | **about €87 to €161** |
| Max plan, same period | | | **About €1,160** (13 months at €89), or about €1,420 if 23% VAT is charged. Already being paid, shared with Adam's other work. Read the invoice | |

**Total new money through P9: about €1,650 to €4,810 over 13 months, plus unknown PC parts.** Including the Max plan before tax: about €2,810 to €5,970. Stopping after P8: about €980 to €3,880 new money [inference].

**What would change this most:**

1. Whether the existing PC passes the check (€0 versus €1,500 or more).
2. Whether the base (P9) is built at all (about €640 to €850).
3. Whether voice stays on a hosted provider: €27 to €64 a month at 1 hour a day; 3 hours a day costs far more [peer: voice.md §1, brain.md §7].
4. Heavy use of autonomous runs above Max credits.
5. Hitting the weekly Max limit and moving to Ultra at $200, about €89 a month more, or about €1,160 over the period.

---

## 16. What could not be confirmed, what changed, and what conflicts

### 16.1 Still open

| Topic | Gap | How to close |
|---|---|---|
| Competitors | Search returns many aggregators. ChatGPT Work's EU status rests on a secondary source. Poke's sale price and finances are [unverified]. New small entrants may be missing | Read openai.com by hand; repeat the scan at gate G1 |
| Marvel's JARVIS registrations | Only a paywalled 2019 excerpt about cybersecurity software was read | EUIPO and USPTO, with the name check |
| AI Act Article 50(2) transition | The Commission pages give none; the Omnibus text returned an empty page | Read `OJ:L_202601744` by hand before any public product |
| Tax on Max | Pricing page excludes tax; what Adam pays was not seen | Read the invoice |
| Hetzner setup fee | Page lists a fee without an amount | Order page |
| Trademark on "Jorah" | One general search found nothing, which is no clearance | EUIPO eSearch Plus, USPTO; lawyer before public use |
| OpenClaw's trademark rules | No policy found in repo root or bundled docs | Ask the foundation before any use of the name |
| GitHub Pro price | Secondary only; GitHub's anonymous pricing page does not show Pro | https://github.com/pricing while signed in |
| Rulesets on a private Free repo | Two GitHub pages disagree | Create one ruleset after ENG-2 and test it |
| Adam's GitHub plan | Token scope hides it | Adam checks settings |
| GitHub self-hosted runner fee | Postponed, future unclear | Watch the billing docs before any runner |
| NemoClaw current status | README says alpha; no GitHub release; the 0.0.8 docs URL returned 404 | Security track reads the repo |
| Exact Pipecat class names | `main` confirms `PipelineWorker` and the tracing flags; a pinned release was not read | Check against the pinned release in ENG-24 |
| Which `gateway-client` version to pin with host 2026.10.9 | Docs name 2026.8.1 as verified; npm `latest` is 2026.10.9; neither tested | Spike in ENG-12 |
| Service env inheritance for `CLAUDE_CONFIG_DIR` | Docs read; not run | Spike in ENG-10 |
| Hook behavior on Claude CLI runtime | Open | growth.md S13 |
| Whether the Max-linked Console org can use the Admin API | Individuals cannot; org status unknown | Console, Settings, Organization |
| Real idle power on Mac and PC | Not measured; PC unknown | Plug meter, `powermetrics` |
| Every cost marked `[inference]` | Estimates | Replace as bought |
| Time estimates | My judgment, no data from Adam's real pace | Track hours for P0 and P1, then rescale all |

**Closed in this pass:** gitleaks CLI syntax, pnpm and Dependabot cooldowns, the CRA position on open source, Reachy Mini's maker price, restic encryption statement, offsite storage price, and Admin API eligibility for individuals.

### 16.2 Corrections to the first pass

Anyone who read the 18:00 version should note these:

- **Budget totals were wrong.** The first pass summed to about €3,860 and €3,460 where the rows gave €3,914 and €3,521, and it predated robotics' prices. Section 15 is recomputed with robotics, and the low end rose from €540 to about €1,280 because it now includes a Pi, cameras and the full arm stack. The skeptic pass later moved it to about €1,365 after robotics revised its totals.
- **Two config examples were broken.** A trailing `#` comment in `.gitignore` becomes part of the pattern, and `${{ }}` inside a YAML flow mapping does not parse. Both are fixed.
- **A single uv workspace was wrong** for conflicting ML stacks (finding 11).
- **"Vendors do not do Slovak" was too strong.** Assistant products lag, but Gemini Live's speech model has Slovak (section 13.4).
- **The injection suite cost was inconsistent** ("a few cents per case" against $0.10 for the whole suite). It is restated from brain.md's unit costs, as a floor.
- **Firmware plan:** ESP-IDF plus QEMU was replaced to match robotics' Arduino pick.
- **Barge-in target:** 300 ms was replaced by the 150 ms in voice and UX. 300 ms is now the "Stop" command target.
- **"Service" business idea:** downgraded, since hosting and setup are crowded.
- **GitHub Pro:** "stay on Free" now has a named trigger for buying Pro.

### 16.3 Conflicts between tracks, for the roadmap to settle

| Conflict | Positions | My suggestion [inference] |
|---|---|---|
| First room mic | voice.md: XVF3800 for far field, Voice PE as runner-up. apps.md: Voice PE as the always-on ear | Buy one Voice PE first. It needs no host and works when the PC sleeps. Add XVF3800 for the robot later. Both are budgeted |
| Who owns "metrics" | ux.md `jorah-metrics`; this file's `jorah-status` and `turns.jsonl` | One data source named `jorah-metrics`; `jorah-status` is its text view |
| Firmware framework | robotics: Arduino core first. First pass here: ESP-IDF | Arduino, with logic in plain C++, so moving later is cheap. Note the LGPL point if devices are ever sold |
| Arm host | Topology's bridge placement versus robotics' dedicated Pi | Dedicated Pi, because it is the only placement that creates the boundary now |
| "Voice in phases" | Native Talk first is required to prove the loop, but UX says it cannot give the Jarvis feel | Keep V0 small. Do not polish native Talk |

---

## 17. Questions only Adam can answer

1. **Is a private GitHub repo acceptable for the research notes and rules?** My pick: yes, plus a bundle on an encrypted disk. Alternative: bundle only, losing Issues and CI.
2. **Do you agree to buying GitHub Pro (about $4 a month) only when an unattended session can push?** My pick: yes, and Free until then.
3. **What does the PC have?** Run the check in topology.md §15. It decides the largest cost.
4. **Is the Max plan already at the weekly limit with Mizyun?** If yes, parallel building and Jorah will compete. Run the one-week `/usage` measure, and decide Ultra versus pace.
5. **Monthly cash ceiling?** My suggestion: €155 until Phase 6, before any VAT on Max, with brain.md's caps.
6. **How much of the 10 to 15 hours is really available each week, given Mizyun, Cognio and school?** The finish moves from about 10 to about 18 months across that range.
7. **Do you agree to personal first, with business gates at about months 4 and 9?** Alternative: start discovery on the Slovak or school angle early, at the cost of slower build.
8. **Willing to open-source the safety core and injection corpus later?** It affects how carefully they should be kept free of private data from the start. My pick: write them as if public.
9. **Is anyone else in the home who may be recorded in test audio?** Consent is needed before the fixtures are made [peer: voice.md §14].
10. **Is offsite backup at Hetzner in Germany or Finland acceptable, at about €4 a month plus a one-off setup fee?** The archive is encrypted first. Real audio stays off it unless you say yes.
11. **Which 3D printer do you have, and does it fit the SO-101 parts?** Robotics found a 200 to 210 mm bed in your project notes, and the plates target 220 mm or more, so parts may need re-nesting [peer: robotics.md §2].
12. **Stop after the arm, or also build the mobile base?** It moves about €640 to €850 and 7 weeks. It can wait until R4 passes.

---

## 18. Sources

### Local

- `DOCS/plugins/building-plugins.md`, `sdk-overview.md`, `sdk-overview/{capabilities,infrastructure,tools-and-commands,host-hooks}.md`, `sdk-testing.md`, `sdk-setup.md`, `tool-plugins.md`, `compatibility.md`, `architecture.md`
- `DOCS/gateway/opentelemetry.md`, `opentelemetry/{setup,configuration,privacy-and-trace-context,model-calls-and-metrics,spans-and-events}.md`, `prometheus.md`, `diagnostics.md`, `health.md`, `audit.md`, `clients.md`, `external-apps.md`, `multiple-gateways.md`, `index.md`, `protocol/rpc-talk-config-and-agents.md`
- `DOCS/install/updating.md`, `updating/rollback-and-recovery.md`, `updating/automatic-updates.md`, `backups.md`, `migrating.md`
- `DOCS/cli/{backup,daemon,update,mcp,security}.md`
- `DOCS/platforms/{linux,windows}.md`, `platforms/mac/bundled-gateway.md`
- `DOCS/concepts/{usage-tracking,qa-e2e-automation}.md`, `reference/api-usage-costs.md`, `start/why-openclaw/versioned-state-guarded-upgrades.md`
- Peer tracks in this folder: `apps.md`, `brain.md`, `connectors.md`, `creative.md`, `growth.md`, `openclaw-fit.md`, `robotics.md`, `security.md`, `topology.md`, `ux.md`, `vision.md`, `voice.md`. Their numbers were written earlier on 2026-11-02 and were not independently rechecked here
- Read-only commands: `git status`, `git log`, `openclaw --version`, `openclaw --profile jorah backup create --dry-run --json` (paths only), `ps`, `top`, `du`, `df`, `uptime`, `node -v`, `which`, `grep` (filenames only), `gh api` for public repos

### Web

Pages marked (reopened) were read again in the second pass. New ones were read in the second pass only. The rest were read in the first pass on the same date.

GitHub and CI:
- https://docs.github.com/en/billing/concepts/product-billing/github-actions (reopened)
- https://docs.github.com/en/code-security/secret-scanning/introduction/about-push-protection
- https://docs.github.com/en/code-security/getting-started/github-security-features (reopened)
- https://docs.github.com/en/get-started/learning-about-github/githubs-plans (reopened)
- https://github.com/pricing (reopened)
- https://github.blog/changelog/2025-03-04-introducing-github-secret-protection-and-github-code-security/ (new)
- https://docs.github.com/en/code-security/dependabot/working-with-dependabot/dependabot-options-reference (new)
- https://raw.githubusercontent.com/gitleaks/gitleaks/master/README.md (new)
- https://raw.githubusercontent.com/gitleaks/gitleaks/master/cmd/git.go (new)
- https://pnpm.io/settings, https://pnpm.io/settings/dependency-resolution (new)
- https://docs.astral.sh/uv/concepts/projects/workspaces/ (new)
- https://docs.pipecat.ai/server/utilities/opentelemetry (new)
- https://www.hetzner.com/storage/storage-box/ (new)
- https://www.backblaze.com/cloud-storage/pricing (new)
- https://github.com/restic/restic, https://restic.readthedocs.io/en/stable/020_installation.html (new)
- https://platform.claude.com/docs/en/build-with-claude/usage-cost-api (new)
- Secondary: https://creditforstartups.com/resources/github-pro-pricing, https://www.techzine.eu/news/devops/137396/github-bends-to-criticism-and-delays-paid-self-hosting-of-runners/, https://langfuse.com/docs/integrations/pipecat
- https://docs.github.com/en/actions/how-tos/manage-runners/self-hosted-runners/add-runners
- https://docs.github.com/en/actions/concepts/runners/self-hosted-runners
- https://github.com/gitleaks/gitleaks-action
- https://github.com/grafana/docker-otel-lgtm
- https://wokwi.com/pricing

Claude Code:
- https://code.claude.com/docs/en/github-actions (reopened)
- https://code.claude.com/docs/en/worktrees (reopened)

Microsoft:
- https://learn.microsoft.com/en-us/windows/win32/services/interactive-services

Market:
- https://github.com/openclaw/openclaw/blob/main/README.md
- https://claude.com/product/cowork (reopened)
- https://www.apple.com/apple-intelligence/
- https://gemini.google/overview/agent/
- https://www.aboutamazon.com/news/devices/new-alexa-generative-artificial-intelligence
- https://www.pollen-robotics.com/reachy-mini/ (new)
- https://wiki.seeedstudio.com/ai_robotics_control_soarm_by_openclaw_on_jetson_thor/ (new)
- Skeptic pass, read: https://github.com/betterleaks/betterleaks, https://support.claude.com/en/articles/15036540-use-the-claude-agent-sdk-with-your-claude-plan, https://support.claude.com/en/articles/13345190-getting-started-with-cowork, https://claude.com/pricing, https://www.hetzner.com/storage/storage-box/bx11/, https://platform.claude.com/docs/en/manage-claude/usage-cost-api, https://ai-act-service-desk.ec.europa.eu/en/ai-act/article-50
- Secondary, read in full: https://www.techwyse.com/?p=76542, https://runtimewire.com/article/cognition-acquires-poke-interaction-consumer-ai-agents, https://thenextweb.com/news/openai-chatgpt-work-agent-launch, https://thenextweb.com/news/gemini-spark-not-in-europe, https://engadget.com/2167301/perplexity-opens-up-its-personal-computer-ai-assistant-to-all-mac-users, https://the-decoder.com/perplexitys-personal-computer-promises-a-tireless-ai-agent-for-200-a-month/, https://www.trendingtopics.eu/openclaw-stiftung-launch/
- Secondary, search result summaries only: https://techcrunch.com/2026/04/27/china-vetoes-metas-2b-manus-deal-after-months-long-probe/, https://thenextweb.com/news/meta-manus-data-split-china-unwind-acquisition, https://docs.nvidia.com/nemoclaw/0.0.8/index.html, https://heise.de/-11213313, https://kilo.ai/openclaw/how-much-does-it-cost, https://clawdocs.org/guides/hosting-providers, https://www.ampere.sh/blog/hire-openclaw-expert, https://mixbit.com/blog/best-openclaw-implementation-companies/, https://www.androidauthority.com/openai-device-launch-2026-3633803, https://northeasttimes.com/2026/07/30/openai-says-it-s-building-hardware-to-talk-to-its-ai/, https://heise.de/-11287205, https://www.therobotreport.com/1x-announces-pre-order-launch-neo-humanoid-robot/, https://www.ycombinator.com/companies/button-computer, https://pypi.org/project/so101-control/, https://github.com/viam-devrel/so-101, https://www.greenbone.net/en/blog/cra-open-source-software/
- First pass, no longer cited in section 13: https://www.manus.im/
- Paywalled excerpt only: https://www.worldipreview.com/trademark/marvel-hits-out-at-blackberry-over-jarvis-tm-18387
- https://huggingface.co/blog/reachy-mini (first pass; July 2025 prices match the maker's page today)
- https://www.1x.tech/neo
- https://deepmind.google/models/gemini-robotics/
- https://huggingface.co/docs/lerobot/so101
- https://github.com/TheRobotStudio/SO-ARM100
- https://home-assistant.io/voice-pe/

Law and money:
- https://digital-strategy.ec.europa.eu/en/policies/cyber-resilience-act
- https://digital-strategy.ec.europa.eu/en/policies/cra-open-source (new)
- https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai
- https://single-market-economy.ec.europa.eu/sectors/mechanical-engineering/machinery_en
- https://europa.eu/youreurope/business/taxation/vat/vat-rules-rates/index_en.htm
- https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html

GitHub API (licence, stars, last push, latest release), read 2026-11-02, for: `openclaw/openclaw`, `openclaw/openclaw-windows-node`, `NousResearch/hermes-agent`, `nanocoai/nanoclaw`, `zeroclaw-labs/zeroclaw`, `pollen-robotics/reachy_mini`, `gitleaks/gitleaks`, `trufflesecurity/trufflehog`, `restic/restic`, `FiloSottile/age`, `getsops/sops`, `benbjohnson/litestream`, `dscripka/openWakeWord`, `livekit/agents`, `pipecat-ai/pipecat`, `ggml-org/whisper.cpp`, `SYSTRAN/faster-whisper`, `OHF-Voice/piper1-gpl`, `k2-fsa/sherpa-onnx`, `moonshine-ai/moonshine`, `huggingface/lerobot`, `espressif/esp-idf`, `espressif/esp-sr`, `espressif/qemu`, `esphome/esphome`, `google-deepmind/mujoco`, `google-deepmind/mujoco_menagerie`, `ultralytics/ultralytics`, `gumyr/build123d`, `grafana/grafana`, `grafana/loki`, `grafana/docker-otel-lgtm`, `prometheus/prometheus`, `open-telemetry/opentelemetry-collector`, `jaegertracing/jaeger`, `CtrlSpice/otel-desktop-viewer`, `langfuse/langfuse`, `winsw/winsw`, `evilmartians/lefthook`, `casey/just`, `jdx/mise`, `astral-sh/uv`, `pnpm/pnpm`, `google/osv-scanner`, `renovatebot/renovate`, `actions/runner`, `aaif-goose/goose`, `OpenHands/OpenHands`, `letta-ai/letta`, `mem0ai/mem0`, `Significant-Gravitas/AutoGPT`, and in the second pass `NVIDIA/NemoClaw`, `espressif/arduino-esp32`, `arduino/arduino-cli`, `Rhoban/placo`, `ros-navigation/navigation2`, `foxglove/ros-foxglove-bridge`.

---

## Verification

Independent skeptic pass, 2026-11-02, about 22:00 CET. I tried to refute the claims the plan leans on most, by opening the sources myself and reading the bundled OpenClaw docs, instead of trusting the links above. Everything here is the source-check tier. Nothing was installed or run beyond read-only commands, and only this file was edited.

**Limit on this pass.** The shared web search budget ran out after two searches, so I could fetch known URLs but not discover new ones. Claims that needed discovery are marked as open, not as confirmed.

### Does the recommendation still hold?

**Yes, with changes.** The monorepo, thin plugins, external services, local-first checks and personal-first business timing all survive. No checked fact points at a different architecture. Four things moved:

1. **Secret scanner (E3).** The reason "active" was false. Gitleaks stays the pick for now, as a frozen tool, and Betterleaks replaces TruffleHog as runner-up.
2. **Budget (section 15).** New money through the base rises from about €1,530 to €4,560 to about **€1,650 to €4,810**. Real-time voice months rise from about €110 to €130 to about **€116 to €153**. The Daily Driver level rises from about €125 to €135 to about **€130 to €175**. Full Jarvis rises from about €400 to about **€525**. The cash ceiling suggested to Adam rises from €130 to €155.
3. **Offsite backup (E14).** Hetzner stays, but `openclaw backup --to` has no SFTP provider, so the route is restic, and a plain local archive must not be left behind.
4. **Business evidence.** The conclusion stands, but the strongest quoted evidence was unsupported. It now rests on inference from few cases.

### What I checked

| # | Claim | Result | Evidence |
|---|---|---|---|
| 1 | Gitleaks is "active" | **Refuted.** README: feature complete, security patches only, maintainer moving to Betterleaks. Recent commits are Dependabot merges | gitleaks README, GitHub API |
| 2 | Custom rules needed for Anthropic, OpenAI, Gemini, Telegram | **Partly wrong.** Default config already has them. ElevenLabs and Tailscale are the gaps | `config/gitleaks.toml` |
| 3 | Secret Protection $19, Team and Enterprise only; user push protection public only | Confirmed | GitHub changelog, features page, push protection page |
| 4 | Free cannot protect `main` on a private repo | Confirmed for branch protection. The rulesets conflict remains: pricing says public only, features page says all plans, and the two articles I hoped would settle it state no plan | GitHub plans, pricing, rulesets and protected-branches pages |
| 5 | Pro is about $4 | **Still secondary.** GitHub's pages I could read do not show it | Search results, pricing page |
| 6 | Actions $12 and $18 allowances, per-minute rates, self-hosted runners free | Confirmed, as is GitHub's "2,000 minutes" | Billing docs, pricing page |
| 7 | Plugins experimental, unsandboxed, test helpers unpublished, deprecation window | Confirmed | `plugins/sdk-overview.md`, `architecture.md`, `sdk-testing.md`, `compatibility.md` |
| 8 | `openclaw backup` misses `~/.claude-jorah` and `~/.jorah-brain` | Confirmed. Dry run lists only state and workspace, and I found no include option | Dry run, `cli/backup.md` |
| 9 | Hetzner BX11 at €3.20, 1 TB | Confirmed. **Added** a setup fee the file omitted | Hetzner BX11 page |
| 10 | Offsite works through `backup --to` | **Narrowed.** Providers are `filesystem` and plugins such as R2. `--output` copies are plaintext | `concepts/storage-locations.md`, `cli/backup.md` |
| 11 | Headless nodes auto-update hourly; opt-out key | Confirmed | `install/updating/automatic-updates.md` |
| 12 | No per-stage latency for native Talk | Confirmed. Only counter, duration and bytes are listed, and `nodes/talk.md` has no latency metric | `model-calls-and-metrics.md`, `nodes/talk.md` |
| 13 | Pipecat spans hold words, no off switch | Confirmed, and stronger: read in source | Pipecat docs and `service_decorators.py` |
| 14 | uv workspace unsuitable for conflicting stacks | Confirmed | uv docs |
| 15 | pnpm defaults and setting names | Confirmed | pnpm settings |
| 16 | Admin API unavailable for individuals | Confirmed. **Added** that the endpoints are now legacy, and the page moved | Claude platform docs |
| 17 | Build sessions share Jorah's limit | Confirmed for `claude -p` and the SDK, as of the 2026-10-07 update | Support article |
| 18 | Claude GitHub App's broad permissions; custom app runner-up; subscription token | Confirmed | Claude Code GitHub Actions docs |
| 19 | Worktree details in sections 3, 4 and 12 | All confirmed | Claude Code worktrees docs |
| 20 | Gateway client should be 2026.8.1 | **Updated.** npm `latest` is 2026.10.9, matching the host. Operator clients get no N-1 window | `gateway/clients.md`, `npm view` |
| 21 | 17 stable releases in October, 722 advisories | Confirmed by my own API count. **Added** that no advisory is newer than 2026-09-11, so the feed alone is a weak trigger | GitHub API |
| 22 | Service commands do not inherit shell variables | **Narrowed.** That covers service-control commands. The spike stays | `gateway/index.md`, `gateway/cli-backends.md` |
| 23 | Cowork's Windows support unconfirmed | **Closed.** macOS and Windows, Linux beta | Claude support article |
| 24 | Poke: three months, low nine-figure price, founder on profit | **Not supported by the cited pages.** About 100 million messages holds, as does the acquisition. Cognition's post returned 404 | TechWyse, RuntimeWire, both read in full |
| 25 | Marvel holds JARVIS for voice assistants | **Not supported.** The excerpt concerns BlackBerry and cybersecurity software, 2019 | WIPR excerpt |
| 26 | OpenClaw renamed twice over trademark | **Half right.** Only the first is attributed to trademark | `start/lore.md` |
| 27 | CRA, AI Act and Machinery Regulation dates | Confirmed. **Added** the Omnibus and the Annex I date. Article 50(2) transition is open | Commission pages |
| 28 | Exchange rate 1.1216, Slovak VAT 23% | Confirmed | ECB, Your Europe |
| 29 | Max cost is €89 | **Narrowed.** Pricing excludes tax, so about €109 if VAT applies | Claude pricing page |
| 30 | Cost tables match the peer tracks | **Stale.** Brain raised voice to $0.04 a minute after this file was written, voice changed its pick, robotics revised its totals, and topology rejected a named UPS. All recomputed. The file's own arithmetic was otherwise right | `brain.md` §7, `voice.md` §1, `robotics.md` §9, `topology.md` |
| 31 | Reachy Mini prices, Seeed guide has no safety layer, Spark absent from the EEA, foundation facts, NemoClaw alpha | Confirmed. Spark and the foundation remain secondary | Vendor pages, TNW, Trending Topics, repo README |
| 32 | Windows services in session 0; WinSW a usable runner-up | Session 0 confirmed. **Added** that WinSW's last full release is from 2023 | Microsoft Learn, GitHub API |

### What I did not check

- ChatGPT Work, Perplexity, Manus, Alexa+, Siri AI, 1X, Figure and Gemini Robotics rows.
- The licence table, apart from spot checks by API.
- Autodesk Fusion personal terms. Autodesk's page returned 403, so that row stays at its peer label.
- Peer-track numbers, beyond confirming that this file matches what they say now. Their own verification sections apply, and those files were still changing during this pass, so the roadmap should re-read them.

Small rounding note, left as is: P8 computes to 14.6 weeks but is shown as 14. The unrounded total is about 56 weeks, so the 58-week figure is not understated.
