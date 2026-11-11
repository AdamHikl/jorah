# Issue 8 evidence: the Mac iOS runner

2026-11-11, on Adam's Mac (Xcode 27.2, build 27B52), as user `adam`. Not as `jorah-build`, which doesn't exist yet (issue 10).

## Tier reached: source, tests, and `build` for the fixture app

| Check | Result |
|---|---|
| `just check` | passes; `services/ios-runner/tests`: 30 tests with stubbed `xcodebuild`, `xcrun simctl`, `xcrun devicectl`, `codesign`; real git |
| `just ios-runner-sample` (real `xcodebuild`, simulator, the fixture in `services/ios-runner/tests/fixtures/Sample`) | `outcome: ok`, `tier: build`, 8.5 s, commit `083fcd6`, tree clean. The `.app`'s `CFBundleIdentifier` read back as `dev.jorah.fixture.sample`; log ends `** BUILD SUCCEEDED **`. [`build-sim-result.json`](build-sim-result.json), temp paths shortened to `$TMPDIR` |

Not run, and not proved: `build-device`, `install-device`, `archive`, `devices` against a real device or real signing. They need the `jorah-build` account, a Development identity and an allowlisted device (issues 10, 11, 12). `sync` was run only in tests, against throwaway repositories.

## Against the draft contract `docs/contracts/jorah-ios-v1.md` (issue 7, on `main` at 73819a7)

The runner was built to issue 8's brief. The contract landed while it was being written and is still waiting for Adam's D1-D4, so these are recorded, not changed. Section 7 asks the runner to use section 2's object and section 3's codes; today it doesn't.

| # | Contract | Runner now | Kind |
|---|---|---|---|
| 1 | HTTP on `127.0.0.1:47820`, HMAC headers, `GET /v1/health` | CLI only, JSON on stdout | Transport, out of scope for issue 8; a thin front end can call the verbs |
| 2 | Envelope `{contract, ok, run, error}` | Flat object with `schema: 1` | Shape |
| 3 | `state`: queued, running, succeeded, failed, cancelled, unknown | `outcome`: running, ok, failed, timeout, refused, busy | Names |
| 4 | `tier: none` when nothing passed; a failed install after a good build is `tier: build` | `tier: unknown` when the verb's own tier wasn't proved (the brief: "a failed or missing step is unknown"); install runs don't claim `build` | **Semantic conflict between the brief and the contract. Adam decides** |
| 5 | Build verbs take `commit` (40 hex); `sync {project, ref}` resolves to a commit without switching | Build verbs build whatever is checked out; `sync <project> <branch>` switches and fast-forwards, branch limited to `main` and `jorah/<task>` | Flow. Contract accepts any branch name in `ref`; the brief limits it |
| 6 | Build verbs return in 2 s (`queued`), polled with `status { wait_seconds }` | Synchronous; `status <run-id>` reads the result file, which says `running` while a run is in progress | Async belongs with the transport front end |
| 7 | `install-device {build_run_id, device, launch}`; `NOT_INSTALLABLE` | `install-device <project> <device> [--launch]` installs the project's latest device build | Flow |
| 8 | `run_id` = `<UTC>Z-<project>-<6 hex>` | `<UTC to the ms>Z-<8 hex>` | Format |
| 9 | Error codes (`PROJECT_NOT_ALLOWED`, `BUSY`, `SIGNING_FAILED`, …) | `outcome` plus a free-text `error` | Missing |
| 10 | `artifact {kind, path, bytes, sha256}`, `.app` copied into the handoff folder | `artifact_path` only; only `archive` writes to the handoff folder (`.ipa`) | Missing fields |
| 11 | `archive` is an `.xcarchive` signed for Development | `archive` exports a Development `.ipa` (`method: debugging`, `destination: export`), as issue 8 asks | Brief and contract differ |
| 12 | `log {offset, max_bytes}` paging, `log.tail` 16 KiB, `summary.first_errors` | `log <run-id>` prints the capped log (≤ 8 MiB) | Missing |
| 13 | `install` tier needs the device to list the bundle ID; `launch` needs a process ID | Exit 0 from `devicectl install` / `process launch` | Weaker checks than the contract |
| 14 | `devices` returns `alias, model, os_version, connected` | `device, connected` (+ simulator count) | Missing fields |
| 15 | Allowlist JSON5 with `contract`, `installAllowed`, `team`, `projects.<name>.repo`, `bundleId` | JSON with `schema`, per-project `team_id`, `bundle_id`, `path`, `prepare`; no `installAllowed` | Shape |
| 16 | Build timeout 45 min, install 5 min | 60 min, 10 min defaults, set in the project file | Defaults |

## From the issue 11 recipes (`docs/runbooks/ios-recipes.md`)

Gaps the real apps will hit, for whoever wires them in: a fixed per-project `env` map (variant and `EXPO_PUBLIC_*` values at prebuild and xcodebuild time); `expo-prebuild` run in a sub-folder (Mizyun's `apps/mobile`) and via `npx` for npm projects (Threadfolio), with `--clean`; a restore step for the `package.json` Threadfolio's prebuild rewrites, or the next `sync` refuses a dirty tree; `-allowProvisioningUpdates CODE_SIGN_STYLE=Automatic`, which the runner doesn't pass today (issue 10 decides).
