# Issue 9: `plugins/jorah-ios`, evidence and notes

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
