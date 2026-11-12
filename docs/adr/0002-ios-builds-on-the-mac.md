# ADR 0002: iOS builds on the Mac, requested from Jorah on the PC

**Status:** accepted by Adam, 2026-11-12, in the build session: "accept all four, for D4 allow all simulator use as well". Route 2, waiver accepted, paid team with a Development certificate, device install allowed on the iPhone, and simulator use allowed. Nothing is installed, paired, configured or applied yet. Issue 7.

**Recommendation:** route 2. A Gateway plugin on the PC, `jorah-ios`, offers three typed tools and calls a small runner on the Mac, under macOS user `jorah-build`, over the tailnet. No node is paired, `gateway.nodes` is not touched, and `system.run` stays denied everywhere. The interface the other issues build to is in [`docs/contracts/jorah-ios-v1.md`](../contracts/jorah-ios-v1.md).

## Adam's decisions

Decided 2026-11-12. Issues 9 to 12 may now go past source and tests, each step still on Adam's yes.

| # | Decision | Options | Proposed | Adam, 2026-11-12 |
|---|---|---|---|---|
| D1 | **Route** | 1 node-hosted typed MCP, 2 Gateway plugin plus Mac runner, 3 allowlisted `system.run` | **2** | **2** |
| D2 | **Waiver of hard gate 2** for this route, before M3 | Accept the text in "Waived gate" below, or refuse. Refusing means no remote iOS builds until M3 passes | Accept, if you want builds before M3 | **Accepted**, with the simulator addition below |
| D3 | **Apple team** that `jorah-build` signs with | Your paid Developer Program team, or a free Personal Team (7-day profiles, few devices) | Your paid team, Development certificate only, if you have one | **Paid team, Development certificate only.** **Company team** (Adam, 2026-11-12), the one `services/ios-runner/ios-projects.json` names |
| D4 | **Device install** | Allowed (each install is its own card, only to devices you list), or simulator and archive only | Allowed, iPhone only | **Allowed, iPhone only, and all simulator use allowed** |

**D4, simulator use.** Adam's words: "for D4 allow all simulator use as well". Read here as [inference, Claude's reading]: on the Mac's iOS Simulators the runner may build, boot and shut down a simulator, install, launch and stop the app, and take screenshots, for projects on the allowlist, on any simulator Xcode offers, with no device allowlist. Everything else in the waiver still holds for simulator use: fixed verbs with no free-form command, the project allowlist, and truthful tiers. **Cards on a simulator, decided 2026-11-12.** Adam: "No cards for simulator". Simulator actions (boot, shutdown, install, launch, terminate, screenshot) run without an approval card. This amends waiver condition (4) for those actions only. **Every build still waits for a card, a simulator build included** [Claude's reading, the narrow one]: a build runs the repo's own build scripts on the Mac, and the card is what ties it to a commit Adam saw. A simulator install only accepts a build that was approved that way. Device installs keep their card. The simulator verbs are in the contract and the runner since 0107f66.

## Where the facts come from

OpenClaw docs and code were read from the copy installed on this Mac: `/opt/homebrew/lib/node_modules/openclaw`, `package.json` version **2026.10.9**. That is the version the PC runs (`scripts/pc/wsl-jorah-setup.sh` pins `OPENCLAW_VERSION="2026.10.9"`). The Mac's Gateway is stopped since the cutover, and nothing here started it.

- **[verified: docs]** read in `docs/` of that install. File named.
- **[verified: source]** read in that install's `dist/` code. File named.
- **[inference]** reasoned, not read or measured.
- Nothing in this ADR was **measured**. No Gateway, node or runner was run.

## The question, as it stands today

**K10a** asked: with `system.run` denied and `gateway.nodes.pluginTools.enabled: true`, can `main` on the `claude-cli` runtime call a typed node-published MCP tool, given the global `tools.deny: ["nodes", ...]`?

That framing is out of date. Main left `claude-cli` on 2026-11-07 and runs on the embedded runtime with the API key (`docs/runbooks/jorah-on-pc.md`, "API lane"). Re-read for the embedded runtime:

1. **Node MCP tools are built into the embedded runtime's tool list.** `createNodePluginTools` adds every connected node's published descriptors to the agent's plugin tools, and a call goes out as `node.invoke` with command `mcp.tools.call.v1` [verified: source, `dist/openclaw-tools-CSSYZDKR.mjs`, region `src/agents/node-plugin-tools.ts`].
2. **The global `tools.deny: ["nodes"]` does not hide them.** That function drops a node tool only when the deny list matches its plugin ID (`node-mcp`), its published name, its exposed name, or `group:plugins` [verified: source, same file]. `nodes` matches none of these. So the global deny that keeps the `nodes` tool away from Jorah would **not** keep a node MCP tool away [inference from the source; not measured].
3. **`gateway.nodes.pluginTools.enabled: false` does hide them**, for every node at once, and `gateway.nodes.commands.deny: ["mcp.tools.call.v1"]` blocks the call [verified: docs, `nodes/mcp-and-skills.md`]. The PC sets `pluginTools.enabled: false` (`config/pc/stage0.patch.json5`, ruling 11). Changing it needs a Gateway restart [verified: docs, `gateway/configuration/hot-reload.md`, row "Gateway tools & nodes"].
4. **The tool must also pass main's allow list**: main has an explicit `alsoAllow` list, so a node tool would need its name added, as `github_*` were [verified: source, same function's allowlist check; the GitHub case was measured 2026-11-10, `config/pc/github-tools.patch.json5`].

**Answer:** on the embedded runtime, route 1 would very likely work once `pluginTools.enabled` is `true` and the names are allowed [inference from source]. It stays unmeasured. Under route 2 the question no longer matters, so this ADR does not spend a pairing to measure it. If you pick route 1, the test is step R1-T in "Steps for Adam".

**TOPO-S4: do two macOS users hold separate node identities?** Yes on paper. A headless node keeps its client ID, device keypair and pairing tokens in `~/.openclaw/state/openclaw.sqlite`, under the running user's home or `OPENCLAW_STATE_DIR` [verified: docs, `nodes/node-host.md`, "Headless identity state"]. So `jorah-build` and `adam` would hold different device IDs [inference]. Tailscale identity is per machine, not per user, so both share the Mac's tailnet identity (`02-architecture.md` 5.4). Not measured. Route 2 pairs no node, so it does not depend on this.

## The three routes

### Route 1: node-hosted typed MCP (the plan's earlier pick)

`jorah-build` runs `openclaw node run` with one MCP server in its `nodeHost.mcp.servers` [verified: docs, `nodes/mcp-and-skills.md`].

**Changes Gateway-wide:**
- `gateway.nodes.pluginTools.enabled` goes from `false` to `true`. This is one switch for all nodes: the iPhone and any later node may then publish agent-visible tools [verified: docs, `nodes/command-policy.md`].
- A second paired node before M3. That is hard gate 2.
- The node cannot shrink its own surface: `--commands` "also disables ... plugin-tool publication, MCP servers" [verified: docs, `nodes/node-host.md`, "Restrict the node command surface"]. So it keeps the default desktop surface (`system.run`, `system.which`, `browser.proxy`, `file.*`, `screen.snapshot`, `desktop.stream` and more) minus the Gateway's deny list, and its approved pairing surface carries those forward [verified: docs, `nodes/command-policy.md`]. Today's deny list covers `system.run` and `computer.act` but not `system.which`, `browser.proxy`, `screen.snapshot` or `desktop.stream`; each would need adding.
- Node skills would publish unless `nodeHost.skills.enabled: false` is set on the node [verified: docs, `nodes/mcp-and-skills.md`].
- The node runs OpenClaw on the Mac, so every Gateway upgrade has to move the Mac node in step.
- A Gateway plugin is still needed for the approval card, because a node MCP tool has no card of its own [inference]. So route 1 is route 2's plugin plus a node and a global switch.
- Logs come back through `file.fetch`, capped at 16 MiB per file [verified: docs, `nodes/file-transfers.md`].

### Route 2: Gateway plugin plus a Mac runner (recommended)

`plugins/jorah-ios` on the PC, the same shape as `plugins/jorah-github`: typed tools, a `before_tool_call` hook that returns `requireApproval` with `allow-once` and `deny` only, config through `plugins.entries`. Its tools call `services/ios-runner` on the Mac over HTTP on the tailnet, with a signed request per call (contract, section "Transport and auth").

**Changes Gateway-wide:**
- `plugins.allow` gains `jorah-ios`, and main's `alsoAllow` gains `ios_build`, `ios_install`, `ios_status` ([`config/pc/ios.patch.json5`](../../config/pc/ios.patch.json5), draft). Nothing else.
- `gateway.nodes` is unchanged: no pairing, `pluginTools.enabled` stays `false`, `system.run` stays denied.
- Outside OpenClaw: one tailnet grant from the PC to the Mac on one TCP port, and one key file on each machine.

**What it costs:** the plugin runs inside the Gateway process, unsandboxed, as `jorah-github` does [inference from the plugin model]. Its code is ours and reviewed, and it does three things: build a request from fixed fields, sign it, and show the card. It never runs a shell. The runner is new code on the Mac, which a node would have needed as its MCP server anyway.

### Route 3: allowlisted `system.run` wrapper (rejected)

`system.run` leaves `gateway.nodes.commands.deny`. That list is one Gateway-wide list with no per-node form [verified: docs, `nodes/command-policy.md`], so every node that declares `system.run` gets that layer back, and only per-node exec approvals stand in the way. Main would also need `tools.exec` with `host: "node"`. Approvals have been bypassed before (CVE-2026-28466, `03-security-and-privacy.md`). The wrapper's arguments are still a command line, not typed fields. **Rejected.** M19 already says so (`10-roadmap.md` 19.1).

### Side by side

| | Route 1 | Route 2 | Route 3 |
|---|---|---|---|
| New paired node | Yes | **No** | Yes |
| `pluginTools.enabled` | `true`, all nodes | **unchanged** | unchanged |
| `system.run` | denied | **denied** | reopened Gateway-wide |
| Free-form command string | No | **No** | Yes, through the wrapper |
| Gateway restart to switch | Yes | **No**: `plugins.*` reloads the plugin runtime [verified: docs, `hot-reload.md`, row "Plugin config"] | Yes |
| OpenClaw on the Mac | Yes, in lockstep | **No** | Yes, in lockstep |
| Approval card | Needs a plugin anyway | **The plugin** | Exec approval prompt |
| Logs over 16 MiB | Capped by `file.fetch` | **Paged by the runner** | Capped |
| Off switch | Unpair or flip the global | Remove the grant, or stop the runner, or drop the plugin | Re-deny, Gateway-wide |

**Why route 2.** It is the only route that adds no node, leaves every `gateway.nodes` setting as Stage 0 set it, and keeps the request typed from the model all the way to `xcodebuild`. It needs the card plugin that route 1 needs too, and drops the rest. The cost is one small authenticated HTTP service we write and own, which is the same code route 1 would have wrapped in MCP.

## Waived gate

Hard gate 2 says: before M3, the iPhone is the only node, and any other node waits for M3 or gets its own recorded exception (`10-roadmap.md` 2a). Route 2 adds no node, so the letter of the gate holds. Its spirit is about a second machine doing work for Jorah before M3, so this route still asks for your written yes.

**Text for Adam to accept or refuse** (copy it into issue 7 with "Accepted" or "Refused", your name and the date):

> **Waived gate: hard gate 2 (spirit), for iOS builds on the Mac before M3.** I accept that, before M3's security gate passes, Jorah on the PC may ask a runner on my Mac, under the macOS user `jorah-build`, to build, archive and install my iOS apps, by route 2 of ADR 0002. This waiver holds only while all of these hold: (1) Jorah has exactly three tools, `ios_build`, `ios_install` and `ios_status`, with fixed fields and no free-form command, path or flag; (2) the runner builds only projects on its allowlist, from their GitHub repo at a commit the card showed me; (3) signing uses a Development certificate only, with no distribution certificate on that account; (4) every build and every install waits for my tap on an approval card, with allow-once and deny only (amended 2026-11-12: actions on the iOS Simulator need no card; builds and device installs still do); (5) nothing is distributed or uploaded by Jorah or the runner, and I upload with Transporter myself; (6) no OpenClaw node is paired, `gateway.nodes.pluginTools.enabled` stays `false`, and `system.run` stays denied; (7) results claim only the tier they reached. If any of these stops holding, the waiver ends and the route stops until I decide again. It ends anyway when M3's gate passes, and M19's gate (SEC-T15 on `jorah-build`) still applies then.

**Accepted** by Adam on 2026-11-12, in the build session, with the D4 simulator addition recorded under "Adam's decisions". The waiver's scope therefore reads "build, archive, install and run in the iOS Simulator".

## The limits that carry the weight before M3

M3's checks (outbound filter, taint rewrite, the typed reader path) have not run. Until they do, these limits are what stops a bad turn from doing harm, so each one is enforced in code, not in a prompt:

1. **Fixed verbs.** Three tools, every field an enum, a known name or a commit SHA. The runner rejects any unknown field. No command, path, flag, environment variable or build setting is ever taken from the model.
2. **Project allowlist.** The runner's own config, owned by an admin and not writable by `jorah-build`, names each project: repo, workspace or project file, scheme, bundle ID, team. The plugin carries a copy for early refusal and card text; the runner's copy decides.
3. **Development certificate only.** `jorah-build`'s keychain holds no distribution certificate. The runner refuses an export method other than `development` and checks the signing identity before it builds.
4. **A card per build and per install.** `allow-once` and `deny` only, never "always". The card shows project, repo, the exact commit, the kind of build and, for install, the device. A build runs the commit the card showed.
5. **No distribution, no upload.** No `altool`, no `xcrun notarytool`, no App Store Connect key on `jorah-build`. Artifacts stay at `/Users/Shared/jorah-handoff/<run-id>` and Adam uploads with Transporter.
6. **Truthful tiers.** `build`, `install`, `launch`. A missing or failed step reports `none` or the last tier reached, never more. Launch means the process started, not that the app works.
7. **The Mac's own boundary.** `jorah-build` is a Standard user, with `/Users/adam` closed to it first (`02-architecture.md` 5.2). The runner listens only on loopback, and the tailnet grant admits only the PC.
8. **Build output is data.** Logs and compiler messages come from repo content and go back to Jorah marked as untrusted.

## Consequences

- Issue 8 builds the runner to the contract's HTTP section. Issue 9 builds `plugins/jorah-ios`. Issue 10 creates `jorah-build` and its signing. Issue 11 writes the per-app recipes as allowlist entries. Issue 12 tests.
- `02-architecture.md` Case E and `10-roadmap.md` 19.1 name typed node MCP as the route. If Adam accepts D1 = 2, both point here instead. N5's switch stays off for iOS; the robot and Lab routes still need their own answer.
- M19's own gate (SEC-T15 on `jorah-build`) still runs at M19.
- The route needs the Mac awake and on the tailnet. When it isn't, the tools say "waiting for the Mac" (`10-roadmap.md` 2a, M19 row).

## Steps for Adam

Nothing below has been done except step 1. Each is yours.

1. ~~Answer D1 to D4~~ Done 2026-11-12, recorded above and on issue 7.
2. **Tailnet grant** (only after D1 = 2 and D2 accepted). In the Tailscale admin console, Access controls, add to `grants`:
   `{ "src": ["tag:jorah-pc"], "dst": ["adam-mac"], "ip": ["tcp:47820"] }`
   If the PC is not tagged yet, use its device name instead, and say so in the issue. Expected: the policy saves, and its `tests` still pass.
3. **Mac Serve forward** (after issue 8's runner exists). In a Terminal on the Mac as `adam`: `tailscale serve --bg --tcp=47820 tcp://127.0.0.1:47820`. Expected: `tailscale serve status` lists TCP 47820. Off switch: `tailscale serve --tcp=47820 off`.
4. **Shared key** (after issue 9). Create it in a Terminal attached to no agent, as the contract's "Key" section says. Never paste it into a chat.
5. **Config** (after issue 9's plugin is installed on the PC). `openclaw --profile jorah config patch --file /opt/jorah/config/pc/ios.patch.json5 --dry-run`, then apply on your yes. Expected: the dry-run line in the patch's header.

**R1-T, only if you pick route 1.** On a scratch Gateway profile, never `jorah`: set `pluginTools.enabled: true`, pair a throwaway headless node whose MCP server publishes one tool `echo_fixed { word: enum }`, add `echo_fixed` to the scratch main's allow list, keep `tools.deny: ["nodes"]` and `system.run` denied. Ask main to call it. Expected per the source read above: the tool appears and the call returns. This needs a pairing, so it's yours to run or approve.
