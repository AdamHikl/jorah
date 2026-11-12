# Issue 11 evidence: Threadfolio and Mizyun built and run on the iOS Simulator through the runner

2026-11-12. Issues 8 and 11. Adam: "continue to do as much as you can without my help".

**How.**
- **Clones:** scratch clones of `/Users/adam/Documents/threadfolio` and `/Users/adam/Documents/mizyun` at their committed `main` (Threadfolio `99d1be9`, Mizyun `163caa53`). They live in `~/Library/Caches/jorah-ios-validation/src`, outside every repo. Nothing was written in Adam's checkouts, and no `.env*` or `certs/` file was read.
- **Runner:** `jorah-ios-runner serve` (2.1.0) on `127.0.0.1`, with a throwaway key and a scratch allowlist that has the same entries as [`services/ios-runner/ios-projects.json`](../../../services/ios-runner/ios-projects.json), apart from paths. Mizyun had no `envFile`.
- **Requests:** signed HTTP requests as the plugin sends them: `sync`, `build-sim` (Release), `status`, `sim-boot`, `sim-install` with `launch`, `sim-screenshot`, `sim-terminate`, `sim-shutdown`.
- **Setup:** Adam's Mac user, Xcode 27.2, Node 26.13 and pnpm 10.33 from Homebrew, CocoaPods 1.17. Dependencies came from the lockfiles only (`npm ci`, `pnpm install --frozen-lockfile`).

Results with temp paths shortened: [`simulator-runs.json`](simulator-runs.json). No env values are recorded. The screenshots are not committed; what they show is described below.

| App | sync | build-sim, Release | Time | install + launch | Screenshot shows |
|---|---|---|---|---|---|
| Threadfolio, first run, without `SCAN_API_ORIGIN` | ok | **build**, 0 errors, `.app` 89 MB | 8 min 34 s, fresh clone and caches | **launch** | The app's first screen: the "Welcome to Threadfolio" onboarding with "Get started" |
| Threadfolio, the committed entry | ok | **build**, 0 errors | 5 min 9 s, warm caches | **launch** | Same onboarding screen |
| Mizyun, the committed entry without its `envFile` | ok | **build**, 0 errors, `.app` 161 MB | 7 min 5 s, fresh clone and caches | **launch** | The app's own config screen: "Mizyun is ready. Supabase public configuration has not been provided. Set EXPO_PUBLIC_SUPABASE_URL and EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY." Not a crash and not a red error screen, but not usable either |

Every simulator step succeeded on "iPhone 17", iOS 27.0, and the simulator was shut down after each app. No simulator is booted now. After each build the clone was clean: Threadfolio's `package.json` restore worked, and Mizyun's prebuild changed nothing tracked.

**Tier reached: launch on the simulator, for both apps.** That says nothing about any feature or about the iPhone. Not run: device builds, signing, install on the iPhone, anything as `jorah-build`, anything through the Gateway plugin.

## What the run changed in the repo

- **No runner bug turned up.** The real apps did expose one gap: Mizyun needs a value that only Adam has, and the runner had nowhere admin-owned to keep it. Runner 2.2.0 adds a per-project **`envFile`**:
  - an admin-owned `NAME=VALUE` file outside the clone, read per build;
  - the same name rules as the `env` map;
  - names only in the log;
  - the build stops before anything runs if the file is missing or unsafe.
  - Tests: `test_env_file_*` in `services/ios-runner/tests`.
- **The real allowlist** is [`services/ios-runner/ios-projects.json`](../../../services/ios-runner/ios-projects.json), with paths for `jorah-build` (`/Users/jorah-build/src/<app>`). Adam installs it as `/Library/Application Support/Jorah/ios-projects.json` (`docs/runbooks/ios-builds.md` section 5).
- `docs/runbooks/ios-recipes.md` was corrected from the run:
  - Release for the simulator;
  - the prepare steps as they ran;
  - Mizyun needs no restore step;
  - the build times;
  - the old draft entries are replaced by a pointer to the real file.

## What only Adam can supply

1. **Mizyun's dev Supabase publishable key**, `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`.
   - It is only in his `apps/mobile/.env.dev`. Without it the app stops at the config screen above.
   - It goes in `/Library/Application Support/Jorah/env/mizyun-dev.env` as one line `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=…`, owned by root, mode 644.
   - Adam writes the file in a Terminal attached to no agent.
   - Until the file exists, the runner refuses to build Mizyun (`RUNNER_ERROR`, "envFile is missing").
2. **His iPhone's alias and UDID** in `devices`, before any device install.
3. **The `Jorah …` Development profiles** named under `signing`, and the `jorah-build` account, key and LaunchAgent (issue 10, `docs/runbooks/ios-builds.md`).

## Scratch area

`~/Library/Caches/jorah-ios-validation/` is left in place:
- `src/`: the two clones, with `node_modules`, `Pods` and generated `ios/`;
- `runner/`: the scratch allowlist, the throwaway key, run records, and handoff copies of the apps and screenshots.

Size on 2026-11-12: about 16 GB in all, 3.4 GB in `src/` and 13 GB in `runner/`, most of that Xcode derived data in `runner/state/derived`. Delete the folder whenever you like.
