# ios-runner

The Mac side of Jorah's iOS builds (issue 8). A fixed-verb runner: every verb takes names, never commands. It does not know how a request reaches it. The transport, auth and the `jorah-build` account are other issues (7, 9, 10), and the real Threadfolio and Mizyun entries are issue 11.

Python 3 standard library only, so nothing to install. Runs on macOS with Xcode.

## Verbs

```text
jorah-ios-runner sync <project> <branch>            branch: main or jorah/<task>
jorah-ios-runner build-sim <project>
jorah-ios-runner build-device <project>             Development signing, checked with codesign
jorah-ios-runner install-device <project> <device> [--launch]
jorah-ios-runner archive <project>                  .ipa to <handoff_dir>/<run-id>, never uploaded
jorah-ios-runner status <run-id>
jorah-ios-runner log <run-id>
jorah-ios-runner devices
```

Every verb prints one JSON object on stdout. Exit codes: 0 ok, 1 failed, 2 refused, 3 busy (another run holds the project's lock), 4 timeout.

## Rules it keeps

- **No shell.** Every command is an argument array run with `shell=False`. Nothing from a request is joined into a string. `argparse` runs with no abbreviations and no `--help`, and any parse error is a JSON refusal.
- **Names are checked before anything runs.** Project and device names must match `^[a-z0-9][a-z0-9-]{0,39}$` and be in the project file. A device's UDID comes from the file, never from the request. Branches are `main` or `jorah/<task>` with no `..`, `/` or `.lock`. Run IDs must match the runner's own format.
- **The project file decides.** `$JORAH_IOS_RUNNER_CONFIG`, default `~/.config/jorah-ios-runner/projects.json`. It is refused if group or others can write it, and every field is checked when it loads: workspace and project paths stay inside the project folder, prepare steps come from a fixed set, and bundle IDs, schemes and team IDs match patterns. See `projects.example.json` (placeholders only).
- **Prepare steps are a fixed set:** `pnpm-install` (`pnpm install --frozen-lockfile`), `npm-ci`, `pod-install` (in the folder of the workspace or project), `expo-prebuild` (`pnpm exec expo prebuild --platform ios --no-install`).
- **Fixed environment.** Commands get `PATH` from the project file, plus `HOME`, `LANG`, `TMPDIR`, `CI=1` and an optional `DEVELOPER_DIR`. Nothing from the caller's environment except `HOME` and `TMPDIR`.
- **`sync` never resets or stashes.** A dirty tree (tracked or untracked changes) is refused. It fetches the one branch, then switches and fast-forwards only.
- **One run at a time per project**, by `flock` on `<state_dir>/locks/<project>.lock`. The lock goes with the process, so a crash can't leave it stuck.
- **Timeouts per step.** On timeout the whole process group gets SIGTERM, then SIGKILL.
- **Logs are capped** at `max_log_bytes` (default 8 MiB, under the 16 MiB `file.fetch` limit): the first three quarters and the last quarter are kept, and the middle is dropped with a note, because `xcodebuild` errors come at the end. Only the newest `keep_runs` run folders are kept. Handoff artifacts are never deleted.

## Result JSON

Written to `<state_dir>/runs/<run-id>/result.json` at start (`outcome: "running"`) and again at the end.

| Field | Meaning |
|---|---|
| `run_id` | `<UTC yyyymmddThhmmssmmm>Z-<8 hex>` |
| `verb`, `project`, `branch`, `device`, `launch_requested` | What was asked |
| `commit_sha`, `tree_clean` | From git in the project folder, or `null` if git couldn't say |
| `exit_code` | Of the last step; `null` if it timed out or didn't start |
| `outcome` | `ok`, `failed`, `timeout`, `refused`, `busy` |
| `tier` | The highest tier proved: `build`, `install`, `launch`; `none` for `sync`; `unknown` when the verb's own tier wasn't proved |
| `tiers` | Each tier the verb tried, `proved` or `unknown` |
| `artifact_path`, `log_path`, `duration_s`, `started_at`, `finished_at`, `steps`, `error` | |

Each tier is claimed only after its own check:

- `build`: `xcodebuild` exited 0 **and** a `.app` with the project's bundle ID exists. For `build-device`, `codesign` also shows an `Apple Development` identity, and anything else (Distribution, unsigned) is `unknown`. For `archive`, export left exactly one valid `.ipa` in the handoff folder, with `method: debugging` and `destination: export`.
- `install`: `devicectl device install app` exited 0. Says nothing about launch.
- `launch`: `devicectl device process launch` exited 0. Says nothing about whether any feature works.

A failed launch after a good install is `outcome: failed`, `tier: install`, `tiers: {install: proved, launch: unknown}`.

## Tests

`just unit` runs `services/ios-runner/tests` with stand-ins for `xcodebuild`, `xcrun simctl`, `xcrun devicectl` and `codesign`, and real git against throwaway repositories. No Xcode, device or network is needed.

`tests/fixtures/Sample` is a tiny SwiftUI app for a real `build-sim` by hand on the Mac:

```bash
just ios-runner-sample
```
