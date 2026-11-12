# Contract: Jorah iOS tools and the Mac runner, version 1

**Status:** draft, 2026-11-11, from issue 7. Route 2 of [ADR 0002](../adr/0002-ios-builds-on-the-mac.md). Issues 8 (runner), 9 (plugin), 10 (account and signing) and 11 (recipes) build to this. A change that breaks it bumps `contract` to `jorah-ios/2`.

```text
 Jorah (main, PC)  --tool call-->  plugins/jorah-ios (Gateway, PC)  --card-->  Adam: allow once / deny
                                        |
                                        |  HTTP + HMAC, tailnet, tcp 47820
                                        v
                         services/ios-runner (Mac, user jorah-build, 127.0.0.1:47820)
                                        |  fixed verbs only
                                        v
                      git fetch, xcodebuild, simctl, devicectl   ->  /Users/Shared/jorah-handoff/<run-id>
```

## 1. Tools Jorah sees

Three tools, registered by `plugins/jorah-ios` with `catalogMode: "direct-only"` like `jorah-github`. Every schema has `additionalProperties: false`. No field takes a command, a path, a flag, an environment variable or a build setting.

### `ios_build`

Starts a build on the Mac. **Card first.** Returns at once with a `run_id`; the build continues on the Mac.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `project` | string, a key in the allowlist (`^[a-z0-9][a-z0-9-]{0,39}$`) | yes | e.g. `threadfolio`, `mizyun` |
| `kind` | `"simulator"` \| `"device"` \| `"archive"` | yes | Simulator build, device build signed for Development, or an `.xcarchive` |
| `ref` | string: `main` or `jorah/<task>`, where `<task>` matches `^[a-z0-9][a-z0-9._-]{0,62}$`, has no `..` and doesn't end in `.` or `.lock` | no, default `main` | What to build. Amended 2026-11-11 (issue 8): only these two forms, the limit from issue 8, so Jorah can build `main` or its own branches and nothing else. Proposed default, waiting for Adam |
| `configuration` | `"Debug"` \| `"Release"` | no, default `"Debug"` | |

Card text (title "Jorah wants to build an iOS app"): project, repo, `ref` and the exact commit it resolved to, kind, configuration, signing team (device and archive), and "Development certificate. Nothing is uploaded." The plugin resolves the commit by calling runner `sync` inside the hook; if that fails, the call is blocked and the card is not shown, because the card must not ask about a commit it can't name. After `allow-once`, the plugin calls `build-sim`, `build-device` or `archive` with that exact `commit`.

An `archive` is signed for Development. To upload, Adam exports it with his distribution signing in Xcode and uploads with Transporter [inference: App Store uploads need distribution signing]. Jorah never does.

### `ios_install`

Installs the app from a finished `device` build on an allowlisted device. **Card first.** Only exists if Adam allows device install (ADR D4); otherwise the runner answers `INSTALL_DISABLED`.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `run_id` | string, a run ID from `ios_build` with `kind: "device"`, `state: "succeeded"` | yes | Which build to install |
| `device` | string, a device alias in the runner's allowlist (`^[a-z0-9][a-z0-9-]{0,39}$`) | yes | e.g. `adam-iphone` |
| `launch` | boolean | no, default `false` | Start the app after installing |

Card text (title "Jorah wants to install an app on your iPhone"): project, commit, configuration, device alias and model, and whether it launches. Waits for the result; install takes seconds to a minute.

**On a simulator** (added 2026-11-12, issue 8, after ADR 0002 D4 "all simulator use"). The same tool also acts on the Mac's iOS Simulators, so Jorah keeps exactly three tools (waiver condition 1). Give `simulator` instead of `device`:

| Field | Type | Required | Meaning |
|---|---|---|---|
| `simulator` | `{ "name": string, "os": string }`, exactly as `ios_status { simulators: true }` lists them | instead of `device` | e.g. `{ "name": "iPhone 17", "os": "27.0" }`. The runner looks the pair up in `simctl list` and uses the UDID it found; the strings never reach a command line |
| `action` | `"install"` (default) \| `"launch"` \| `"terminate"` \| `"screenshot"` \| `"boot"` \| `"shutdown"` | no | Only `install` exists for a `device` |
| `run_id` | a run ID from `ios_build` with `kind: "simulator"`, `state: "succeeded"` | for `install` only | |
| `project` | an allowlisted project name | for `launch`, `terminate`, `screenshot` | Gives the bundle ID, from the allowlist |
| `launch` | boolean | no, `install` only | Launch after installing |

Runner routes per action: `install` → `sim-install`, `launch` → `sim-launch`, `terminate` → `sim-terminate`, `screenshot` → `sim-screenshot`, `boot` → `sim-boot`, `shutdown` → `sim-shutdown` (section 4a). Card text (title "Jorah wants to use the iOS Simulator"): the action, simulator name and iOS version, project, and for `install` the commit and configuration.

**Cards on a simulator: open.** Every simulator action waits for a card, allow-once or deny, like a device install, because waiver condition (4) was accepted as written. Whether simulator actions may go without a card is Adam's to decide (ADR 0002, "D4, simulator use"); until he does, the plugin shows one.

**Proposal, needs Adam's amendment to waiver condition (1).** A fourth tool, `ios_simulator { action, simulator, project?, run_id?, launch? }`, would read better than `ios_install { action: "screenshot" }`: `ios_install` would stay "put a build on a target", and every simulator action, including `boot` and `screenshot`, would sit in one tool with one card title. Same runner routes, same fields. Not decided: the three-tool form above is the contract until Adam amends condition (1).

### `ios_status`

Read-only, no card. One question per call.

| Field | Type | Required | Meaning |
|---|---|---|---|
| `run_id` | string | no | One run. Without it: the 10 most recent runs, newest first |
| `wait_seconds` | integer 0 to 120 | no, default 0 | Wait up to this long for the run to finish before answering |
| `log` | `{ "offset": integer >= 0, "max_bytes": integer 1 to 262144 }` | no, needs `run_id` | A page of the run's full log |
| `devices` | `true` | no, alone | List allowlisted devices and whether each is connected now |
| `simulators` | `true` | no, alone | List the Mac's available iOS Simulators: `{ name, os, state }` (added 2026-11-12) |
| `screenshot` | `{ "offset": integer >= 0, "max_bytes": integer 1 to 262144 }` | no, needs the `run_id` of a finished `screenshot` | One page of the PNG, base64 (added 2026-11-12). The plugin reads all pages, checks the `sha256`, and shows the image |

Jorah polls a running build with `ios_status { run_id, wait_seconds: 120 }`.

## 2. Result JSON

Every tool returns a text summary for the chat plus this object as `details`. The runner returns the same object (`run` below) in its HTTP body, and the plugin adds only `error` codes of its own (`MAC_UNREACHABLE`, `AUTH_FAILED`, `DENIED`, `CONTRACT_MISMATCH`). Replies that carry no run (`sync`, `log`, `devices`, `status` without `run_id`) put their fields beside `ok`: `{ contract, ok, commit, repo, default_branch, error }` and so on.

```json
{
  "contract": "jorah-ios/1",
  "ok": true,
  "run": {
    "run_id": "20261111T213005Z-threadfolio-3f9c2e",
    "project": "threadfolio",
    "kind": "device",
    "configuration": "Debug",
    "repo": "AdamHikl/threadfolio",
    "commit": "3f9c2e0d1a4b5c6d7e8f90123456789abcdef012",
    "state": "succeeded",
    "tier": "build",
    "tier_note": "Built and signed for Development. Not installed, not launched.",
    "started_at": "2026-11-11T21:30:05Z",
    "finished_at": "2026-11-11T21:36:40Z",
    "artifact": {
      "kind": "app",
      "path": "/Users/Shared/jorah-handoff/20261111T213005Z-threadfolio-3f9c2e/Threadfolio.app",
      "bytes": 48213760,
      "sha256": "…64 hex…"
    },
    "device": null,
    "summary": { "errors": 0, "warnings": 12, "first_errors": [] },
    "log": { "bytes": 31457280, "tail": "…last 16 KiB…", "complete": true }
  },
  "error": null
}
```

| Field | Values | Rule |
|---|---|---|
| `run_id` | `<UTC yyyymmddThhmmssZ>-<project>-<6 hex>` | Made by the runner. Also the handoff folder name |
| `state` | `queued`, `running`, `succeeded`, `failed`, `cancelled`, `unknown` | `unknown` when the runner lost track (restart, Mac slept). Never guessed |
| `tier` | `none`, `build`, `install`, `launch` | **The highest step that finished and was checked.** See below |
| `tier_note` | one sentence | Says what the tier does not prove |
| `artifact.kind` | `app`, `xcarchive`, `png` (a simulator screenshot, a file, added 2026-11-12) | `null` until a build succeeds. `path` is on the Mac, in `<handoff>/<run-id>/`. `bytes` and `sha256` from the files, never estimated. Both kinds are folders: `bytes` is the sum of their files, and `sha256` is SHA-256 over one line per entry, sorted by relative path: `<path>\0file\0<sha256 of the file>`, `<path>\0link\0<target>` or `<path>\0dir` (amended 2026-11-11, issue 8) |
| `kind` | `simulator`, `device`, `archive`, `install`, `sim-install`, `sim-launch`, `sim-screenshot` | The last three added 2026-11-12 (simulator runs, section 4a) |
| `device` | `{ "alias", "model", "os_version" }` or `null` | Device install runs only |
| `simulator` | `{ "name", "os", "state" }` or `null` | Simulator runs only (added 2026-11-12) |
| `process_id` | integer, or absent or `null` | Set when a launch was proved (added 2026-11-12) |
| `summary` | counts from the build result, `first_errors` at most 5 strings of at most 300 characters | A count that couldn't be read is `null`, never `0` |
| `log.tail` | the last 16 KiB of the log, UTF-8, cut at a line start | Marked untrusted by the plugin (section 5) |
| `log.complete` | `false` while running, or if the log was cut short | |

**Tiers.** Each tier is claimed only when its own check passed:

| Tier | Claimed when | Does not prove |
|---|---|---|
| `none` | Nothing below passed | |
| `build` | `xcodebuild` exited 0 and the artifact exists with the size and hash reported | That it installs or runs |
| `install` | Device: `devicectl` reported the install complete and the device lists the bundle ID. Simulator: `simctl install` exited 0 and `simctl get_app_container` then lists the bundle ID, with an `Info.plist` that carries it | That it launches |
| `launch` | `devicectl` (device) or `simctl launch` (simulator) reported a process ID for the bundle | That any feature works. That is Adam's signed-in device acceptance |

A simulator is not the phone: a simulator tier proves nothing about the device. `sim-launch` alone reaches `launch` for whatever copy is installed on that simulator, and its `tier_note` says which build that is was not checked. A `sim-screenshot` run stays at `tier: "none"`: it proves no install or launch, and its result is the PNG.

A failed install after a good build is `state: "failed"` with `tier: "build"` on the install run. An install run has its own `run_id` and points to the build with `build_run_id`.

## 3. Errors

`ok: false`, `error: { "code", "message", "retryable" }`. `message` is one plain sentence for Adam, without secrets or Mac paths outside the handoff folder.

| Code | When | Retryable | Who returns it |
|---|---|---|---|
| `MAC_UNREACHABLE` | No TCP connection in 5 s, or the Mac is asleep or off the tailnet. Jorah says "waiting for the Mac" | yes | plugin |
| `AUTH_FAILED` | Runner rejected the signature, time or nonce | no | plugin, from runner 401 |
| `CONTRACT_MISMATCH` | Runner speaks another major version | no | plugin; also the runner, with HTTP 400, to a signed request whose `X-Jorah-Contract` it doesn't speak |
| `TREE_DIRTY` | The runner's clone has uncommitted or untracked changes. The runner never resets or stashes; Adam looks (added 2026-11-11, issue 8) | no | runner |
| `DENIED` | Adam denied the card, or it timed out (10 minutes) | no | plugin |
| `BAD_ARGUMENT` | A field fails the schema or the runner's own check | no | both |
| `PROJECT_NOT_ALLOWED` | `project` is not in the allowlist | no | both |
| `REF_NOT_FOUND` | Branch or commit not in the repo | no | runner |
| `SYNC_FAILED` | Fetch from GitHub failed | yes | runner |
| `BUSY` | Another run is `running`. One run at a time | yes | runner |
| `BUILD_FAILED` | `xcodebuild` exit not 0 | no | runner |
| `SIGNING_FAILED` | No valid Development identity or profile, or a non-Development identity was found | no | runner |
| `INSTALL_DISABLED` | Device install is off (ADR D4) | no | runner |
| `DEVICE_NOT_ALLOWED` | Alias not in the allowlist | no | runner |
| `DEVICE_UNAVAILABLE` | Allowlisted device not connected, locked or not trusted | yes | runner |
| `RUN_NOT_FOUND` | Unknown `run_id` | no | runner |
| `NOT_INSTALLABLE` | `run_id` is not a succeeded `device` build | no | runner |
| `ARTIFACT_MISSING` | The handoff file is gone or its hash changed | no | runner |
| `INSTALL_FAILED`, `LAUNCH_FAILED` | `devicectl` failed at that step | no | runner |
| `TIMEOUT` | Build over 45 minutes, install over 5 | no | runner |
| `SIMULATOR_DISABLED` | `simulatorAllowed` is off in the runner's allowlist (added 2026-11-12) | no | runner |
| `SIMULATOR_NOT_FOUND` | No available iOS simulator with that name and OS, or more than one: the runner won't guess (added 2026-11-12) | no | runner |
| `SIMULATOR_UNAVAILABLE` | `simctl` could not list, boot or shut down, or the simulator isn't booted when it must be (added 2026-11-12) | yes | runner |
| `TERMINATE_FAILED`, `SCREENSHOT_FAILED` | `simctl` failed at that step, or the screenshot is not a PNG (added 2026-11-12) | no | runner |
| `RUNNER_ERROR` | Anything else. Message says what is known | no | runner |

## 4. Transport and auth

**Network.** The runner listens on `127.0.0.1:47820` only. Adam's Mac Tailscale Serve forwards tailnet TCP 47820 to it (`tailscale serve --bg --tcp=47820 tcp://127.0.0.1:47820`). The tailnet policy admits only the PC to that port (ADR, step 2). Tailscale's WireGuard tunnel encrypts the hop [inference; not read or measured in this session]. The plugin reaches it at `http://<mac MagicDNS name>:47820` from `plugins.entries.jorah-ios.config.runnerUrl`. Two things are unmeasured and issue 9 checks them first: that the WSL distro reaches the Mac's tailnet address and name [inference: Tailscale runs on the Windows host], and that a macOS Serve TCP forward works for a tagged source [inference]. Fallback if the forward doesn't: the runner binds the Mac's tailnet address and rejects any peer but the PC's tailnet address.

**HTTP.** JSON in, JSON out, `Content-Type: application/json`, request body at most 8 KiB, one route per runner verb:

| Runner verb | Route | Body | Used by |
|---|---|---|---|
| `sync` | `POST /v1/sync` | `{ project, ref }` → `{ commit, repo, default_branch }` | `ios_build` hook, before the card |
| `build-sim` | `POST /v1/build-sim` | `{ project, commit, configuration }` → `run` | `ios_build`, `kind: "simulator"` |
| `build-device` | `POST /v1/build-device` | `{ project, commit, configuration }` → `run` | `ios_build`, `kind: "device"` |
| `archive` | `POST /v1/archive` | `{ project, commit, configuration }` → `run` | `ios_build`, `kind: "archive"` |
| `install-device` | `POST /v1/install-device` | `{ build_run_id, device, launch }` → `run` | `ios_install` |
| `status` | `POST /v1/status` | `{ run_id?, wait_seconds? }` → `run` or `{ runs: [run] }` | `ios_status` |
| `log` | `POST /v1/log` | `{ run_id, offset, max_bytes }` → `{ offset, bytes, total_bytes, eof, text }` | `ios_status` with `log` |
| `devices` | `POST /v1/devices` | `{}` → `{ devices: [{ alias, model, os_version, connected }] }` | `ios_status` with `devices` |
| `sim-list`, `sim-boot`, `sim-shutdown`, `sim-install`, `sim-launch`, `sim-terminate`, `sim-screenshot`, `sim-screenshot-read` | `POST /v1/<verb>` | section 4a | `ios_install` with `simulator`, `ios_status` with `simulators` or `screenshot` |
| (health) | `GET /v1/health` | → `{ contract, runner_version, busy }`, unsigned, nothing private | plugin before each call |

Build verbs take a `commit`, never a branch: the plugin always passes the commit the card showed. Build verbs answer within 2 s with `state: "queued"` or `"running"`; `install-device` waits for its result. Unknown fields and unknown routes are `BAD_ARGUMENT`. HTTP status: 200 for every JSON reply, `ok` true or false; 401 with an empty body for any auth failure; 404 unknown route, 411 no length, 413 over 8 KiB, 415 not JSON, 400 unreadable JSON or contract mismatch, each with a `BAD_ARGUMENT` (or `CONTRACT_MISMATCH`) body.

**Key.** One random 32-byte key, the same on both machines, never in config, a chat, an environment variable or the repo:
- PC: `/home/jorah/.config/jorah-ios/runner.key`, owner `jorah`, mode 600. The plugin reads it per call, as `jorah-github` reads its App key.
- Mac: `/Users/jorah-build/.config/jorah-ios/runner.key`, owner `jorah-build`, mode 600.

Adam creates it in a Terminal attached to no agent, on the Mac as `jorah-build`: `umask 077 && mkdir -p ~/.config/jorah-ios && openssl rand -out ~/.config/jorah-ios/runner.key 32`, then copies it to the PC with `scp`. The exact steps go in issue 10's runbook.

**Signature.** Every request except health carries:

```text
X-Jorah-Contract: jorah-ios/1
X-Jorah-Time:     <unix seconds>
X-Jorah-Nonce:    <16 random bytes, hex>
X-Jorah-Sig:      hex(HMAC-SHA256(key, "POST\n" + path + "\n" + time + "\n" + nonce + "\n" + hex(SHA-256(body))))
```

The runner rejects, with 401 and no detail: a missing header, a time more than 60 s off, a nonce seen in the last 10 minutes, or a wrong signature (constant-time compare). Responses are not signed; the tailnet and loopback carry them.

## 4a. Simulator routes (added 2026-11-12, issue 8)

ADR 0002 D4: "all simulator use" for allowlisted projects, on any iOS Simulator Xcode offers, with no device allowlist. The runner still needs `simulatorAllowed: true` in its own allowlist (section 6), as device install needs `installAllowed`.

**Choosing a simulator.** Requests name one as `{ "name", "os" }`. The runner runs `xcrun simctl list --json devices runtimes`, keeps simulators that are available on an available iOS runtime, and needs exactly one with that name and the runtime's `version`. None, or two of the same name and OS, is `SIMULATOR_NOT_FOUND`. The name must match `^[A-Za-z0-9][A-Za-z0-9 ().,'-]{0,63}$` and the OS `^[0-9]{1,2}\.[0-9]{1,2}(\.[0-9]{1,2})?$` before the lookup. Only the UDID simctl reported goes on a command line; replies never carry it.

| Verb | Body | Reply | Runs |
|---|---|---|---|
| `sim-list` | `{}` | `{ simulators: [{ name, os, state }] }`, `state` one of `booted`, `shutdown`, `booting`, `shutting-down`, `unknown` | `simctl list` |
| `sim-boot` | `{ simulator }` | `{ simulator }`, `state: "booted"` checked by a fresh list | `simctl bootstatus <udid> -b`, waits until booted; nothing if already booted |
| `sim-shutdown` | `{ simulator }` | `{ simulator }`, `state: "shutdown"` checked by a fresh list | `simctl shutdown <udid>`; nothing if already shut down |
| `sim-install` | `{ build_run_id, simulator, launch? }` | `run`, `kind: "sim-install"`, when done | Checks the build's `sha256`, needs the simulator booted, `simctl install`, `simctl get_app_container`, then `simctl launch --terminate-running-process` if `launch` |
| `sim-launch` | `{ project, simulator }` | `run`, `kind: "sim-launch"`, `commit` and `configuration` `null` | Needs it booted and the app installed, then `simctl launch` |
| `sim-terminate` | `{ project, simulator }` | `{ project, simulator, terminated: true }` | `simctl terminate` |
| `sim-screenshot` | `{ project, simulator }` | `run`, `kind: "sim-screenshot"`, `artifact: { kind: "png", path, bytes, sha256 }` | Needs it booted, `simctl io <udid> screenshot --type=png` to `<handoff>/<run-id>/screenshot.png` |
| `sim-screenshot-read` | `{ run_id, offset?, max_bytes? }` (at most 262144) | `{ run_id, offset, bytes, total_bytes, eof, sha256, media_type: "image/png", data_base64 }` | Reads the file |

**Screenshots come back as a file, never by a path from the request.** The runner writes the PNG to `<handoff>/<run-id>/screenshot.png`, a name it makes. `sim-screenshot-read` rebuilds that path from the `run_id`, refuses anything that isn't a finished `sim-screenshot` run, rechecks the `sha256` (`ARTIFACT_MISSING` if it changed) and returns one page. A page of 262144 bytes is about 350 KiB of JSON. A phone screenshot is usually under 1 MiB, so a few pages.

Every simulator verb but `sim-list` takes the one-run lock (`BUSY`). Simulator runs answer when done, like `install-device`. `sim-boot` can take a minute or two on a cold simulator.

## 5. Logs, including over 16 MiB

- The full log stays on the Mac in the runner's state folder (`<stateDir>/runs/<run-id>/run.log`), not the handoff folder, so the runner can rotate old logs without touching Adam's artifacts (amended 2026-11-11, issue 8). It is capped at `maxLogBytes` (default 64 MiB): the first three quarters and the last quarter are kept, the middle is dropped with a note, and `log.complete` is then `false`. Error and warning counts in `summary` cover every line, dropped ones included. Nothing large crosses to the PC, and there is no 16 MiB `file.fetch` cap on this route because it uses no node.
- Every `run` carries `log.tail` (last 16 KiB) and `summary.first_errors`. That answers most questions.
- For more, `ios_status { run_id, log: { offset, max_bytes } }` returns one page of at most 256 KiB. A log of any size is read page by page; Jorah should read from the end back, or around `first_errors`, rather than all of it.
- `text` is UTF-8 with invalid bytes replaced; pages are cut on byte offsets and the plugin trims to whole lines.
- The plugin wraps every log page, `tail` and `first_errors` as untrusted content in the chat text, because they repeat repo content. Jorah treats them as data.

## 6. Allowlists (runner side, decides)

Owned by an admin, readable by `jorah-build`, not writable by it. Issue 11 fills it. Plain JSON, not JSON5, because the runner uses the Python standard library only (amended 2026-11-11, issue 8). The runner refuses to start on a file that group or others can write, on unknown keys, or on any field that fails its check. Full shape, with placeholders: `services/ios-runner/projects.example.json`; every key is described in `services/ios-runner/README.md`. In short:

```json
{
  "contract": "jorah-ios/1",
  "installAllowed": false,
  "team": "<Apple team ID>",
  "projects": {
    "threadfolio": {
      "repo": "AdamHikl/threadfolio", "path": "/Users/jorah-build/src/threadfolio",
      "workspace": "ios/ThreadfolioDev.xcworkspace", "scheme": "ThreadfolioDev", "bundleId": "com.threadfolio.dev",
      "prepare": ["npm-ci", "expo-prebuild-npx", "pod-install"], "restore": ["package.json"],
      "env": { "THREADFOLIO_APP_VARIANT": "dev" },
      "signing": { "style": "manual", "profiles": { "ThreadfolioDev": "Jorah com.threadfolio.dev" } }
    }
  },
  "devices": { "adam-iphone": { "udid": "<udid>" } }
}
```

`installAllowed` is ADR D4 and `team` is D3. `simulatorAllowed` (default `false`) is D4's simulator use, added 2026-11-12; the `simulator` timeout (default 300 s) covers each `simctl` step. `env` holds fixed, non-secret values only: names that look like secrets (containing `TOKEN`, `SECRET`, `PASSWORD`, `PRIVATE`, `CREDENTIAL` or `API_KEY`), and names that change what runs (`PATH`, `DYLD_*`, `GIT_*`, `NODE_OPTIONS` and others), are refused. Manual signing writes one `-xcconfig` per run with `CODE_SIGN_STYLE = Manual`, `CODE_SIGN_IDENTITY = Apple Development`, the team, and `PROVISIONING_PROFILE_SPECIFIER = $(JORAH_PROFILE_$(TARGET_NAME))`, so each target gets its own profile (`docs/runbooks/ios-builds.md` 3.1). `allowProvisioningUpdates` is per project, off by default, and can't work in `jorah-build`, which has no Apple Account (same runbook).

The plugin's config carries only `runnerUrl`, `keyFile` and the project names for early refusal.

## 7. What the runner session (issue 8) keeps compatible

Its verbs map one to one onto the routes in section 4. It adds the HTTP and HMAC layer in front of them. Its `install-device` takes `launch`. Its results use section 2's object and section 3's codes.

Done on 2026-11-11 (runner 2.0.0): `jorah-ios-runner serve` is the HTTP front end, and `jorah-ios-runner call <verb> '<json>'` runs the same checks without HTTP, for hand runs. What is still open is listed in `docs/evidence/issue-8/README.md`.

Done on 2026-11-12 (runner 2.1.0): the simulator routes of section 4a, run for real on the fixture over loopback HTTP (evidence in `docs/evidence/issue-8/`).
