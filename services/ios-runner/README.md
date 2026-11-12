# ios-runner

The Mac side of Jorah's iOS builds (issue 8), built to [`docs/contracts/jorah-ios-v1.md`](../../docs/contracts/jorah-ios-v1.md). It is a fixed-verb runner: every verb takes a JSON object of checked fields, never a command. The Gateway plugin `plugins/jorah-ios` (issue 9) calls it over HTTP. The `jorah-build` account, signing and the LaunchAgent are issue 10, and the real project entries are issue 11.

It uses the Python 3 standard library only, so there is nothing to install. It runs on `/usr/bin/python3` (3.9) as the LaunchAgent starts it, and on newer versions.

## Running it

```text
jorah-ios-runner serve                  HTTP on the allowlist's loopback address (default 127.0.0.1:47820)
jorah-ios-runner call <verb> '<json>'   one verb with the same checks, no HTTP; builds wait to finish
jorah-ios-runner health
```

The allowlist path comes from `$JORAH_IOS_RUNNER_CONFIG`, default `~/.config/jorah-ios-runner/projects.json`. Issue 10's agent sets it to `/Library/Application Support/Jorah/ios-projects.json` (root-owned).

| Route | Body | Reply |
|---|---|---|
| `POST /v1/sync` | `{ project, ref? }`, ref `main` (default) or `jorah/<task>` | `{ commit, repo, default_branch, project, ref }`. Fetches only; the tree is not touched |
| `POST /v1/build-sim`, `/v1/build-device`, `/v1/archive` | `{ project, commit, configuration? }` | `run`, at once, `queued` or `running` |
| `POST /v1/install-device` | `{ build_run_id, device, launch? }` | `run`, when done |
| `POST /v1/status` | `{ run_id?, wait_seconds? }` (0 to 120) | `run`, or `{ runs }` (newest 10) |
| `POST /v1/log` | `{ run_id, offset?, max_bytes? }` (at most 262144) | `{ offset, bytes, total_bytes, eof, text }` |
| `POST /v1/devices` | `{}` | `{ devices: [{ alias, model, os_version, connected }] }` |
| `POST /v1/sim-list` | `{}` | `{ simulators: [{ name, os, state }] }`, available iOS simulators |
| `POST /v1/sim-boot`, `/v1/sim-shutdown` | `{ simulator: { name, os } }` | `{ simulator }`, state checked after |
| `POST /v1/sim-install` | `{ build_run_id, simulator, launch? }` | `run`, when done |
| `POST /v1/sim-launch` | `{ project, simulator }` | `run`, when done |
| `POST /v1/sim-terminate` | `{ project, simulator }` | `{ project, simulator, terminated }` |
| `POST /v1/sim-screenshot` | `{ project, simulator }` | `run` with a `png` artifact |
| `POST /v1/sim-screenshot-read` | `{ run_id, offset?, max_bytes? }` (at most 262144) | `{ offset, bytes, total_bytes, eof, sha256, media_type, data_base64 }` |
| `GET /v1/health` | | `{ contract, runner_version, busy }`, unsigned |

Every reply is `{ contract: "jorah-ios/1", ok, …, error }`, where `error` is `{ code, message, retryable }` with a code from contract section 3.

## Rules it keeps

- **Signed requests only.** HMAC-SHA256 as in contract section 4. The key file must be private to the runner's user. It is read on every request, so a new key needs no restart. Requests are refused if they are more than 60 s off or reuse a nonce from the last 10 minutes. A bad signature gets 401 with no detail. Bodies are limited to 8 KiB.
- **Loopback only.** The allowlist can't name any other address.
- **No shell.** Every command is an argument array run with `shell=False`. Nothing from a request becomes a path, a flag, an environment variable or a build setting. Unknown fields are refused. Projects and devices are names looked up in the allowlist, and a device's UDID comes from the allowlist, never the request.
- **The allowlist decides.** It is refused if group or others can write it, if it isn't owned by root or the runner's user, or if it has unknown keys. Paths stay inside the project folder, and prepare steps come from a fixed set:

  | Step | Runs | Where by default |
  |---|---|---|
  | `pnpm-install` | `pnpm install --frozen-lockfile` | project folder |
  | `npm-ci` | `npm ci` | project folder |
  | `pod-install` | `pod install` | folder of the workspace or project |
  | `expo-prebuild` | `pnpm exec expo prebuild --platform ios --no-install --clean` | project folder |
  | `expo-prebuild-npx` | `npx --no expo prebuild --platform ios --no-install --clean` | project folder |

  Any step may name a sub-folder: `{ "step": "expo-prebuild", "dir": "apps/mobile" }`.
- **Fixed environment.** Commands get `PATH` from the allowlist, `HOME`, `TMPDIR`, `LANG`, `CI=1`, an optional `DEVELOPER_DIR`, and the project's `env` map for prepare steps and `xcodebuild`. The map holds non-secret values only. Names that look like secrets, or that change what runs (`PATH`, `DYLD_*`, `GIT_*`, `NODE_OPTIONS` and others), are refused.
- **envFile, for values Adam keeps out of git.** A project may name `envFile`, an absolute path outside its clone, holding `NAME=VALUE` lines (`#` comments, an optional `export`, one pair of quotes stripped). It is read at the start of each build, never at load, so the runner starts without it. The build fails with `RUNNER_ERROR` before anything runs if the file is missing, writable by group or others, owned by anyone but root or the runner's user, over 16 KiB, repeats a name from the `env` map, or breaks the `env` name rules. Its values go to the prepare steps and `xcodebuild` like the `env` map; the log gets the names only. It is for values that are private but not secret, like Mizyun's Supabase publishable key, which ships inside the app.
- **Clean tree, exact commit.** Build verbs refuse a dirty clone (`TREE_DIRTY`) and never reset or stash. They check out the requested commit, detached, only if `HEAD` isn't already there. `restore` lists tracked files the prepare steps rewrite, such as Threadfolio's `package.json`. They are put back with `git checkout -- <file>` after the prepare steps, even when a step fails. The tree was clean before the run, so this undoes only the run's own changes.
- **Signing.** Simulator builds don't sign. Device builds and archives use manual signing by default: one `-xcconfig` per run sets `CODE_SIGN_STYLE = Manual`, `CODE_SIGN_IDENTITY = Apple Development`, the team, and `PROVISIONING_PROFILE_SPECIFIER = $(JORAH_PROFILE_$(TARGET_NAME))` from the project's `signing.profiles` map, so each target (app, widget, watch app) gets its own profile, as `docs/runbooks/ios-builds.md` 3.1 asks. `"style": "automatic"` passes `CODE_SIGN_STYLE=Automatic` and the team instead. `allowProvisioningUpdates` adds `-allowProvisioningUpdates`; it is per project and off by default, and it can't work in `jorah-build`, which has no Apple Account (same runbook). After the build, `codesign` must show an `Apple Development` identity, or the run is `SIGNING_FAILED`.
- **One run at a time on the Mac**, by `flock` on `<stateDir>/locks/runner.lock`, held for a sync or a whole build or install. The lock goes with the process, so a crash can't leave it stuck. Health reports `busy`.
- **Timeouts per step.** Defaults are build 45 min and install 5 min, as in the contract; git, prepare, launch, devices and codesign have their own. On timeout the whole process group gets SIGTERM, then SIGKILL, and the run is `TIMEOUT`.
- **Logs.** Each run's log is at `<stateDir>/runs/<run-id>/run.log`, capped at `maxLogBytes` (default 64 MiB). The first three quarters and the last quarter are kept, and the middle is dropped with a note. Error and warning counts cover every line. The newest `keepRuns` run records are kept (default 200). Artifacts in the handoff folder are never deleted by the runner.
- **Lost track is unknown.** A run whose owning process died while it was `queued` or `running` reads back as `state: "unknown"`, never as succeeded or failed.

## Tiers

`tier` is the highest tier this run proved, `none` when nothing was. Each tier is claimed only after its own check:

| Tier | Claimed when |
|---|---|
| `build` | `xcodebuild` exited 0, an `.app` with the project's bundle ID exists, and for device builds and archives `codesign` shows `Apple Development`. The `.app` is copied to `<handoff>/<run-id>/` (archives are built there as `<Scheme>.xcarchive`), and `bytes` and `sha256` are computed from the files |
| `install` | `devicectl device install app` reported the bundle ID as installed **and** `devicectl device info apps --bundle-id` lists it on the device |
| `launch` | `devicectl device process launch` reported a process ID |

An install run checks that the build's artifact still has its `sha256` (`ARTIFACT_MISSING` otherwise), and that the phone is listed, paired and booted (`DEVICE_UNAVAILABLE` otherwise). A failed install after a good build is `state: failed`, `tier: build`. A failed launch after a good install is `tier: install`, `LAUNCH_FAILED`.

## The real allowlist

[`ios-projects.json`](ios-projects.json) holds Threadfolio and Mizyun as `jorah-build` will run them. Adam installs it with the command in `docs/runbooks/ios-builds.md` section 5 (`sudo install -o root -g wheel -m 0644 … "/Library/Application Support/Jorah/ios-projects.json"`). Both apps build as Release for the simulator and the device, so the JS is bundled and no Metro is needed (`docs/runbooks/ios-recipes.md`). What only Adam can add:

- `devices`: his iPhone's alias and UDID, before any device install.
- `/Library/Application Support/Jorah/env/mizyun-dev.env`, root-owned, mode 644: `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<the dev publishable key from his apps/mobile/.env.dev>`. Until it exists, every Mizyun build stops with `RUNNER_ERROR`, envFile missing. Without the key, the app opens to its own "Supabase public configuration has not been provided" screen.
- The `Jorah …` profiles named under `signing`, for device builds (runbook section 3.5).

## Simulators

ADR 0002 D4 allows all simulator use for allowlisted projects; the allowlist must also say `"simulatorAllowed": true`. A request names a simulator as `{ name, os }`, exactly as `sim-list` shows it. The runner finds it in `xcrun simctl list --json devices runtimes` (available iOS runtimes only) and uses the UDID simctl gave. It refuses a name or OS that fails its pattern, one that isn't listed, and two simulators with the same name and OS. Install, launch and screenshot need the simulator booted; boot it with `sim-boot`.

- `sim-install` claims `install` only when `simctl get_app_container` lists the bundle ID afterwards, and `launch` only when `simctl launch` printed a process ID.
- `sim-launch` alone reaches `launch` for whatever copy is installed; its note says the build was not checked.
- `sim-screenshot` writes `<handoff>/<run-id>/screenshot.png`, stays at tier `none`, and `sim-screenshot-read` returns it in base64 pages from that fixed path after rechecking its `sha256`.

## Archives and Transporter

`archive` makes an `.xcarchive` signed for Development, in `<handoff>/<run-id>/`. Nothing is exported or uploaded. A Development-signed build cannot go to App Store Connect, because uploads need distribution signing. So the upload path for a Production build is still Adam's own: his distribution signing in Xcode, or the app's own release script under his account, then Transporter.

## Tests

`just unit` runs `services/ios-runner/tests`: 72 tests with stand-ins for `xcodebuild`, `xcrun simctl`, `xcrun devicectl`, `codesign`, `pnpm`, `npx` and `pod`, real git against throwaway repositories, and the HTTP server on a free loopback port. No Xcode, device or network is needed, so they run on the Linux CI too.

`tests/fixtures/Sample` is a tiny SwiftUI app. On the Mac:

```bash
just ios-runner-sample
```

It starts `serve` on a free loopback port with a temp allowlist and key, sends a signed `build-sim` for the fixture at `HEAD`, waits through `status`, and prints the final reply. Expect `"state": "succeeded"` and `"tier": "build"`. The fixture folder must have no uncommitted changes.

`just ios-runner-sample-sim` goes on to a real simulator: it picks an iPhone simulator that is shut down now (newest iOS, unique name), boots it, installs and launches the build, takes a screenshot, reads it back in pages, stops the app and shuts the simulator down. Expect `sim-install` at tier `launch` and `"sha256_matches_artifact": true`.
