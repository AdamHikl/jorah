# Issue 9: `plugins/jorah-ios`, evidence and notes

## Update 2026-11-12, evening: the plugin against the real runner on loopback

`just ios-e2e-local` (`plugins/jorah-ios/e2e/loopback.mjs`) starts the real runner
(`services/ios-runner`, `serve`) on 127.0.0.1 with a throwaway key and the fixture app, and drives
the plugin's `before_tool_call` hook and tool handlers through a stand-in for the Gateway's plugin
API. It answers each card the way the step needs, then calls `execute`, as the Gateway does. The
fixture is copied into its own temp git repo with a local bare `origin`. The runner's `sync` fetches
from `origin` and its build may `git switch --detach`, so it must never point at a jorah checkout.
No network is used, and everything is deleted at the end. It is not part of `just check` because it
needs Xcode and a simulator.

**Result: 21 of 21 steps passed** on this Mac (Xcode 27.2, runner 2.1.0, `jorah-ios/1`). The record
is in [`e2e-loopback.json`](e2e-loopback.json), with temp paths shown as `<temp>`. The first run also
passed 21 of 21; the recorded run is the second, with reply text added. It covered:
- A carded simulator build whose card names the commit `sync` resolved, then "State: succeeded. Tier
  proved: build." with the artifact hashed.
- A log page with whole lines in the untrusted wrapper, and the run list.
- With no card (the default): boot, then install with launch (tier `launch`, with a process ID),
  then launch, screenshot (image shown, sha256 checked against the run, tier `none`; read again in
  16 KiB pages through `ios_status`), terminate and shutdown.
- A denied card and a timed-out card, and `execute` without a card (`DENIED`).
- Refused before the Mac: an off-allowlist project and six injected arguments (shell string and
  option in `ref`, a flag in `configuration`, an extra `scheme`, a quote in a simulator name, a
  `path` field), and a simulator install of a build that never had a card. The run count was
  unchanged across all of these.
- A wrong key (the real runner's 401, reported as `AUTH_FAILED`), and the runner stopped ("Mac not
  reachable … Nothing was started", for a status read and for a build hook).

**Faults found:** one small one on the plugin side, fixed: a short log read "(0.0 MB)" in the
reply; sizes under 1 MB now show in KiB (the recorded run predates the fix). None in the runner or
the contract that this path reaches. Not covered here, because they need G1 to G4 of `docs/runbooks/ios-test-pass.md`:
- device builds and installs, signing, `sync` from GitHub;
- the runner as `jorah-build` under launchd;
- the tailnet hop and the Gateway itself: whether its plugin API calls `onResolution` before
  `execute`, and passes the same `toolCallId`.

**jorah-guard:** checked with jorah-guard's own `decide()` (read-only). With today's
`config/permission-matrix.json`, all three tools are blocked ("isn't in Jorah's permission list
yet"). With the diff below they are allowed, the chat is marked as having read outside text, and
they are blocked while Jorah is frozen. Proposal only, not applied:

```diff
--- a/config/permission-matrix.json
+++ b/config/permission-matrix.json
@@ -7,7 +7,7 @@
     "agentmemory__memory_recall", "agentmemory__memory_smart_search", "agentmemory__memory_sessions",
     "agentmemory__memory_diagnose"
   ],
-  "taintRead": ["sessions_history", "sessions_search", "github_clone", "github_sync"],
+  "taintRead": ["sessions_history", "sessions_search", "github_clone", "github_sync", "ios_build", "ios_install", "ios_status"],
   "search": ["web_search", "x_search"],
   "url": ["web_fetch", "browser"],
   "fileWrite": ["write", "edit", "apply_patch"],
```

---

## Update 2026-11-12: simulator actions (ADR 0002 D4, accepted)

Built to the contract on `main` at d253d4e (0107f66 plus Adam's no-cards decision). **Tier: source and tests** (50 unit tests).

- **Three tools only** (waiver condition 1). Simulator actions go through `ios_install` with
  `simulator: { name, os }` and `action` (`install` default, `launch`, `terminate`, `screenshot`,
  `boot`, `shutdown`), as contract 1 "On a simulator" states. The proposed fourth tool `ios_simulator`
  is **not** built: it waits for Adam to amend waiver condition (1).
- **The card switch:** `plugins.entries.jorah-ios.config.simulatorCards`, `"off"` (default) or
  `"required"`, read in `plugins/jorah-ios/ios.js` `settings()` and used by `cardless()` in
  `plugins/jorah-ios/index.js`. Default `"off"` per Adam, 2026-11-12, "No cards for simulator" (ADR
  0002 and contract 1, d253d4e); `config/pc/ios.patch.json5` writes it out. `"required"` turns the
  simulator cards back on. Every build, a simulator build included, and every device install shows a
  card whatever the switch says (tested in both positions). The checks behind a card run either way:
  field checks, the project allowlist, the simulator listed exactly once, and for an install a
  succeeded, proved simulator build.
- **A simulator install rests on the build's card.** The plugin keeps the run IDs of simulator builds
  it started after an allow-once card (in memory, newest 200) and installs only those on a
  simulator, in the hook and again in `execute`. Known limit: after a Gateway restart the list is
  empty, so earlier builds are refused until Jorah builds again (fails closed). A runner-side record
  of "approved" doesn't exist in the contract; the plugin is the only place that knows.
- **Simulator card** ("Jorah wants to use the iOS Simulator"): action, simulator name, iOS version and
  state, project, and for an install the commit, configuration, run and whether it launches. Before
  the card the hook checks the simulator appears exactly once in `sim-list`
  (`SIMULATOR_NOT_FOUND` otherwise) and that an install names a succeeded, proved `simulator` build of
  an allowlisted project (`NOT_INSTALLABLE` otherwise). A device install now also needs `tier: build`.
- **Screenshots:** after `sim-screenshot`, or with `ios_status { run_id, screenshot: { offset: 0,
  max_bytes } }`, the plugin reads the PNG whole with `sim-screenshot-read`, at most 8 MiB and 64 pages.
  It shows the image only if the bytes match the read reply's sha256, the run's artifact sha256 and
  the PNG signature, and the reply says `image/png`. Otherwise it shows the reason and no image. The
  base64 goes in the image block only, not in `details`.
- **Tiers:** a `sim-screenshot` run claiming any tier above `none`, a `launch` without a `process_id`,
  or an install tier without the artifact's size and hash is reported as tier `unknown`. Boot,
  shutdown and terminate say what the Mac confirmed (`booted`, `shutdown`, `terminated: true`), or
  that it's unknown. Every simulator result says it proves nothing about the iPhone.
- **Amendments adopted:** `ref` is `main` or `jorah/<task>` with `<task>` matching
  `^[a-z0-9][a-z0-9._-]{0,62}$`, no `..` and not ending in `.` or `.lock`. The log pointer is now the
  runner's state folder (`runs/<run-id>/run.log`), not the handoff folder. Replies without a run
  carry their fields next to `ok`.

### Contract points, 2026-11-12 (not changed; for the issue 7/8 owner)

8. `ios_status.screenshot` takes `{ offset, max_bytes }`, but the plugin "reads all pages and checks
   the sha256". A part of a PNG can't be checked, so the plugin refuses an `offset` other than 0 and
   treats `max_bytes` as the page size. A `{ max_bytes }` field only would be clearer.
9. Simulator `launch` and `terminate` take `project` but no commit: the card can't say which build
   is installed on that simulator (the runner's `tier_note` says so too).

### Proposed `config/permission-matrix.json` entries for jorah-guard (proposal only; P5's file)

```json
"taintRead": ["sessions_history", "sessions_search", "github_clone", "github_sync",
              "ios_build", "ios_install", "ios_status"]
```

Why `taintRead` for all three: their results carry repo content (log tail, first errors, log pages)
or a screenshot of the app's screen, so the chat should count as having read outside text. The guard
lets them through to this plugin's own card (one card, not two). They stay blocked while Jorah is
frozen (only `read` passes then). The guard records `params.project` as a repo read, which only
narrows later GitHub pushes from that chat. Not `read`, because that would leave them allowed when
frozen and untainted. Not `github`, because that class is for pushes.

---

2026-11-11, Claude Code build session. **Tier reached: source and tests.** Nothing installed, no
Gateway touched, no config applied, no secret read. Built to `docs/contracts/jorah-ios-v1.md` as
written on `main` at b73a55c, not to the runner's code.

## What is there

| File | What |
|---|---|
| `plugins/jorah-ios/index.js` | `ios_build`, `ios_install`, `ios_status` (`direct-only`, closed schemas) and a `before_tool_call` hook: `requireApproval`, `allow-once` and `deny` only, 10 minute timeout |
| `plugins/jorah-ios/ios.js` | Argument checks, HMAC signing (contract 4), runner client, run reading and chat text |
| `plugins/jorah-ios/test/` | 30 unit tests against `fake-runner.js`, an HTTP runner that checks signatures, time and nonces on its own |
| `config/pc/ios.patch.json5` | Draft: `plugins.allow` + `plugins.entries.jorah-ios` (runnerUrl, keyFile, projects). Not applied |
| `config/pc/ios-tools.patch.json5` | Draft: main's `alsoAllow` plus the three tools. Not applied |

## How the card binds the call

1. Hook: checks project (config list), ref (`main` or `jorah/<task>` only; a bare commit is refused),
   kind and configuration. Then `GET /v1/health` (5 s) and signed `POST /v1/sync`. A commit that
   isn't 40 lowercase hex blocks the call before any card.
2. Card names project, repo, ref, full commit, kind, configuration, and signing. Install card: project,
   commit, configuration, run, device alias and model, launch or not. The install hook first reads the
   build (`status`) and the devices list and refuses a build that isn't a succeeded, proved device build.
3. `onResolution` records the decision. `execute` sends only with a recorded `allow-once` for exactly
   the same arguments, once, within 12 minutes of the card. Deny, timeout, cancelled, no record, reuse
   or stale: `DENIED`, nothing sent.
4. Mac unreachable at either point: `MAC_UNREACHABLE`, "Mac not reachable … Nothing was started", and
   the approval is used up, so nothing fires later. A lost reply after a build or install request was
   sent: state **unknown**, never success.

## Contract points that were unclear for the plugin (not changed; for issue 7's owner)

1. **Signing team on the card.** Section 1 says the build card shows the signing team, but `sync`
   returns only `{ commit, repo, default_branch }` and the plugin config has no team. The card says
   "the team in the Mac's allowlist". Fix: add `team` to the `sync` reply.
2. **Response shape.** Section 2 says the runner returns the envelope; section 4's table says
   "→ `run`". The plugin accepts both (`{contract, ok, run, error}` or the bare object).
3. **Log pointer.** `run.log` has no path or file name. The plugin points to the handoff folder
   `/Users/Shared/jorah-handoff/<run_id>/` and to `ios_status` paging. A `log.path` would be exact.
4. **Lost reply.** No code for "request sent, no reply". The plugin uses `MAC_UNREACHABLE` with
   `retryable: false` and `state: "unknown"` in `details`, and tells Jorah to check `ios_status`.
5. **Key file errors.** A missing or group-readable key on the PC is reported as `AUTH_FAILED`
   (nothing sent). The contract lists `AUTH_FAILED` only for a runner 401.
6. **`ref` as a commit.** Section 1 allows a 40-hex `ref`; the brief for this issue limits refs to
   `main` and `jorah/<task>`, so the plugin refuses a bare commit. If that is wrong, it is one regex.
7. **`tier` with `state: unknown`.** The plugin also downgrades a `build`-or-higher tier with no
   artifact size and hash to `unknown`, stricter than section 2's wording.

## Interaction with jorah-guard (not edited)

`jorah-guard` runs first (priority 1000) and blocks any tool not in `config/permission-matrix.json`.
Until the matrix lists them, every `ios_*` call is blocked by the guard ("isn't in Jorah's permission
list yet"). Suggested class: `taintRead` for all three. That lets the call through to this plugin's
card (the guard adds none, so there is one card, not two), marks the chat as having read outside text
because results carry log lines from the repo, and still blocks while Jorah is frozen. The matrix is
P5's file, so this is a step for its owner, not done here.

## Unmeasured, for the first install

- That the host calls `onResolution("allow-once")` before `execute` (docs `plugins/hooks/tool-policy.md`
  say it receives the decision; order not measured). If it doesn't, every build fails closed with
  `DENIED`. Fix would be in `takeApproval`.
- That `event.toolCallId` in the hook equals the `execute` call ID. If not, the fallback key (tool and
  arguments) is used, which still binds the approval to the exact call.
- WSL reaching the Mac's tailnet name on TCP 47820 (contract 4).
