# Issue 8 evidence: the Mac iOS runner

## Third pass, 2026-11-12: simulator verbs, after ADR 0002 D4 "all simulator use" (runner 2.1.0)

| Check | Result |
|---|---|
| `just check` | passes; `services/ios-runner/tests`: 68 tests, 12 of them new for the simulator with a stubbed `simctl` (selection by name and OS only, duplicates and non-iOS refused, `simulatorAllowed` off by default, install proved by `get_app_container`, launch by a process ID, screenshot PNG check, tamper check, paged read, one signed round trip over HTTP). Also on `/usr/bin/python3` 3.9.6 |
| `just ios-runner-sample-sim` on f89821a: real `simctl`, loopback HTTP, signed requests, simulator "iPhone 17" on iOS 27.0, shut down at the start | `build-sim` **build** (`bytes` 200272); `sim-boot` booted; `sim-install` with `launch` **launch**, `process_id` 79575; `sim-screenshot` succeeded at tier `none`, PNG 76943 bytes; `sim-screenshot-read` pages joined match the artifact `sha256`; `sim-terminate` ok; `sim-shutdown` shut down. [`sim-over-http.json`](sim-over-http.json) (temp paths as `<temp>`), and the screenshot itself, [`sim-screenshot.png`](sim-screenshot.png): the fixture's "Jorah runner fixture" screen |

Tiers on the simulator: build, install and launch, through HTTP on loopback, as Adam's user. A simulator tier proves nothing about the phone. Not proved: any of this as `jorah-build` under the LaunchAgent (CoreSimulator may need that user's GUI session [inference]), from the PC, or through the plugin and its cards.

Open, Adam's: whether simulator actions go without an approval card (the contract keeps a card for each until he says), and whether to amend waiver condition (1) for the proposed fourth tool `ios_simulator` (contract section 1). Until then the contract folds simulator actions into `ios_install` and `ios_status`.

## Second pass, 2026-11-11: to contract `jorah-ios/1`, with the HTTP front end (commit e104d46)

| Check | Result |
|---|---|
| `just check` | passes; `services/ios-runner/tests`: 56 tests (stubbed `xcodebuild`, `simctl`, `devicectl`, `codesign`, `pnpm`, `npx`, `pod`; real git; the HTTP server on a free loopback port). Also passes on `/usr/bin/python3` 3.9.6, the Python the issue 10 LaunchAgent runs |
| `just ios-runner-sample` on e104d46: `serve` on loopback, signed `build-sim`, then `status { wait_seconds }` | `state: succeeded`, `tier: build`, about 8 s, `artifact` `.app` copied to the handoff folder with `bytes` 200272 and its `sha256`, `summary` 0 errors, `log.complete` true, log ends `** BUILD SUCCEEDED **`. [`build-sim-over-http.json`](build-sim-over-http.json), temp paths shortened to `$TMPDIR` |

Still not proved: `build-device`, `archive`, `install-device`, launch and `devices` against real signing or a real phone, anything as `jorah-build`, and the route from the PC. Those are issues 10 and 12.

## First pass

2026-11-11, on Adam's Mac (Xcode 27.2, build 27B52), as user `adam`. Not as `jorah-build`, which doesn't exist yet (issue 10).

## Tier reached: source, tests, and `build` for the fixture app

| Check | Result |
|---|---|
| `just check` | passes; `services/ios-runner/tests`: 30 tests with stubbed `xcodebuild`, `xcrun simctl`, `xcrun devicectl`, `codesign`; real git |
| `just ios-runner-sample`, then the CLI form (real `xcodebuild`, simulator, the fixture in `services/ios-runner/tests/fixtures/Sample`) | `outcome: ok`, `tier: build`, 8.5 s, commit `083fcd6`, tree clean. The `.app`'s `CFBundleIdentifier` read back as `dev.jorah.fixture.sample`; log ends `** BUILD SUCCEEDED **`. [`build-sim-result.json`](build-sim-result.json), temp paths shortened to `$TMPDIR` |

Not run, and not proved: `build-device`, `install-device`, `archive`, `devices` against a real device or real signing. They need the `jorah-build` account, a Development identity and an allowlisted device (issues 10, 11, 12). `sync` was run only in tests, against throwaway repositories.

## Against the contract `docs/contracts/jorah-ios-v1.md`

First noted against issue 7's draft at 73819a7; the status column is after the second pass (e104d46).

| # | Contract | Runner at 541f233 | Now |
|---|---|---|---|
| 1 | HTTP on `127.0.0.1:47820`, HMAC headers, `GET /v1/health` | CLI only | **Closed.** `jorah-ios-runner serve`; loopback only; signature, ±60 s, 10-minute nonce window, 401 with no body; key file read per request and refused unless private to the runner's user |
| 2 | Envelope `{contract, ok, run, error}` | Flat object | **Closed.** Non-run replies put their fields beside `ok` (amended into the contract) |
| 3 | States queued, running, succeeded, failed, cancelled, unknown | `outcome` | **Closed.** A run whose process died reads back as `unknown`; runs stopped by SIGTERM to `serve` are `cancelled` |
| 4 | `tier: none` when nothing passed; failed install after a good build is `tier: build` | `unknown` | **Built to the contract. Open: Adam's decision** (the parent session's proposed default) |
| 5 | Build verbs take `commit`; `sync` resolves a ref | Branch builds | **Closed both ways.** Build verbs take a 40-hex commit and check it out detached; `sync` only fetches and resolves, and takes only `main` or `jorah/<task>`. Contract `ref` amended to that. **Open: Adam's decision** |
| 6 | Build verbs reply within 2 s; `status { wait_seconds }` | Synchronous | **Closed** (`serve`); `call` stays synchronous for hand runs |
| 7 | `install-device { build_run_id, device, launch }` | By project | **Closed.** `NOT_INSTALLABLE`, `RUN_NOT_FOUND`, and `ARTIFACT_MISSING` when the artifact's `sha256` changed |
| 8 | Run ID `<UTC>Z-<project>-<6 hex>` | Other format | **Closed** |
| 9 | Error codes | Free text | **Closed.** All runner codes from section 3, plus `TREE_DIRTY` (added to the contract) |
| 10 | `artifact {kind, path, bytes, sha256}` in the handoff folder | Path only | **Closed.** `.app` copied to `<handoff>/<run-id>/`; folder `sha256` defined in the contract |
| 11 | `archive` is a Development `.xcarchive` | Development `.ipa` | **Built to the contract.** Nothing is exported. README says a Development build can't go to Transporter. **Open: Adam's decision** |
| 12 | Log paging, `log.tail`, `summary.first_errors` | Whole log | **Closed.** Contract amended: logs stay in the runner's state folder, not the handoff folder, so rotation never touches artifacts |
| 13 | Install proved by the device listing the bundle; launch by a process ID | Exit codes | **Closed.** `devicectl ... --json-output`: `installedApplications`, then `device info apps --bundle-id`, then `process.processIdentifier`. Key names are from Apple's JSON as far as read on this Mac [inference for install and launch output; checked in issue 12] |
| 14 | Devices `alias, model, os_version, connected` | Two fields | **Closed.** `connected` is null when devicectl can't answer; it is "paired and booted" [inference: matches devicectl's "available (paired)" for both phones on this Mac; checked in issue 12] |
| 15 | Allowlist with `contract`, `installAllowed`, `team`, `repo`, `bundleId` | Other shape | **Closed**, as plain JSON (contract amended from JSON5) |
| 16 | Build 45 min, install 5 min | 60 and 10 | **Closed** |

## Recipe gaps from `docs/runbooks/ios-recipes.md`

| Gap | Now |
|---|---|
| Per-project environment for variants and `EXPO_PUBLIC_*` | **Closed.** `env` map of fixed values in the admin-owned allowlist; secret-looking names and names that change what runs are refused. The values in Mizyun's gitignored `.env.dev` still have to be copied into the allowlist by Adam (issue 11) |
| `expo prebuild` in `apps/mobile`, through `npx` for npm projects, with `--clean` | **Closed.** Steps take `dir`; `expo-prebuild-npx` added; both prebuild steps pass `--clean` |
| Threadfolio's prebuild rewrites `package.json` | **Closed.** `restore` puts listed files back after prepare, even on failure |
| Signing: `-allowProvisioningUpdates` can't work in `jorah-build` | **Closed as asked.** Manual signing per target through one `-xcconfig` per run (`PROVISIONING_PROFILE_SPECIFIER = $(JORAH_PROFILE_$(TARGET_NAME))`); `allowProvisioningUpdates` per project, off by default. Whether Xcode applies the per-target `-xcconfig` to CocoaPods targets without complaint is untested [inference; issue 12] |

## Still open

- Adam's decisions on rows 4, 5 and 11 (proposed defaults built in).
- Source access for `sync` (runbook section 6, decision S1). The runner fetches with whatever git credentials `jorah-build` has; no per-run token is passed yet.
- Device build, archive, install and launch on real signing and a real phone, as `jorah-build` through the LaunchAgent, and the route from the PC: issues 10 and 12.
- Simulator: whether actions need a card each, the fourth-tool proposal, and the simulator verbs as `jorah-build` (third pass above).
