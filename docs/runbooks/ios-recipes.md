# iOS build recipes: Threadfolio and Mizyun

Issue 11. How the Mac builds Adam's two iOS apps locally with `xcodebuild`, without EAS cloud, and
the runner's project entries for them (ADR 0002, runner from issue 8). Written 2026-11-11 from
reading both repos; nothing was built.

**Tier reached: source.** No build, install or launch was run for this file. Each claim is marked:

- **[verified]** read in the repo's source or seen with a read-only command (`xcodebuild -list` on
  Adam's existing generated project, `gh api` reads).
- **[docs]** said only in the repo's own docs or comments.
- **[inference]** reasoned, not checked.

Sources read: Threadfolio at `99d1be9`, Mizyun at `163caa53` (its `main` checkout, with unrelated
uncommitted docs edits). Neither repo's `.env*` contents nor `certs/` were read; env files were
checked only through their `.example` files and `.gitignore`.

## What both apps share

- **Expo with Continuous Native Generation: `ios/` is not in git** [verified: both `.gitignore`s
  list `/ios`]. A clean clone has no Xcode project. `expo prebuild` makes it, and the workspace and
  scheme names come from the app name of the chosen variant. The `ios/` folders in Adam's own
  checkouts are generated leftovers, not source.
- **The variant is picked by environment variables**, read by `app.config.js` at prebuild and again
  inside `xcodebuild`, whose "Bundle React Native code" phase runs Metro and inlines `EXPO_PUBLIC_*`
  values into the JS bundle [verified: `app.config.js` in both; bundling inside xcodebuild is
  inference from Expo's build phase]. The same variables must therefore be set for both steps.
- **Release embeds the JS bundle; Debug loads it from Metro on the Mac** [docs: Threadfolio's
  `scripts/ios-device-install.sh` comments, Mizyun `AGENTS.md` "a Metro development client still
  depends on Metro"; the Mizyun install script reports a launch "without Metro bundler" for
  Release]. Both repos' own device scripts build **Release** with Development signing. Use Release
  for the runner, so the app works with the Mac closed.
- **Signing:** automatic, team `LQJNDVBL43` [verified: Threadfolio `scripts/ios-device-install.sh`
  default, Mizyun `app.config.js` `appleTeamId` and its scripts]. Both scripts pass
  `-allowProvisioningUpdates CODE_SIGN_STYLE=Automatic DEVELOPMENT_TEAM=LQJNDVBL43`.
- **Install:** `xcrun devicectl device install app --device <udid> <app>`, then
  `xcrun devicectl device process launch --device <udid> --terminate-existing <bundle-id>`
  [verified: both scripts].
- **Build times:** neither repo documents an iOS build time [verified: searched README, docs,
  status]. Mizyun records an Android Release build of 3 min 51 s; that says nothing about iOS.

## Threadfolio

| Item | Value |
|---|---|
| Repo | `AdamHikl/threadfolio`, npm (`package-lock.json`), Expo SDK 58, RN 0.88 [verified] |
| Variants | `dev`: "Threadfolio Dev", `com.threadfolio.dev`, URL scheme `threadfolio-dev`. `production`: "Threadfolio", `com.threadfolio.app` [verified: `app.config.js`] |
| Picked by | `THREADFOLIO_APP_VARIANT` (default `dev`) [verified] |
| Target, workspace, scheme (dev) | target `ThreadfolioDev`, `ios/ThreadfolioDev.xcworkspace`, scheme `ThreadfolioDev` [verified: `xcodebuild -list` on Adam's generated project] |
| Scheme (production) | `Threadfolio`, `ios/Threadfolio.xcworkspace` [inference: prebuild names it after the app name] |
| Configurations | `Debug`, `Release` [verified] |
| Deployment target | iOS 16.4 [verified: generated `project.pbxproj`] |
| Team | not in the project; passed as `DEVELOPMENT_TEAM` on the command line [verified] |
| Dev client | `expo-dev-client` is a dependency, so a Debug build is a dev client that needs `npm run start:dev` on the Mac [verified: `package.json`, script comment] |

**Prepare, in order** [verified: `scripts/ios-device-install.sh`]:

1. `npm ci` [inference: the script assumes `node_modules` exists; `npm ci` is the lockfile install].
2. `THREADFOLIO_APP_VARIANT=dev npx expo prebuild --clean --platform ios --no-install`
3. `pod install` in `ios/`.
4. **Undo prebuild's edit to `package.json`:** prebuild rewrites the `ios` and `android` scripts,
   a tracked file. The repo's script puts them back with `sed` [verified]. A runner must restore
   the file (`git checkout -- package.json`) or its next clean-tree check fails [inference].

**Simulator** [inference: standard flags; the repo has no simulator script]:

```bash
THREADFOLIO_APP_VARIANT=dev xcodebuild -workspace ios/ThreadfolioDev.xcworkspace -scheme ThreadfolioDev \
  -configuration Debug -destination 'generic/platform=iOS Simulator' -derivedDataPath ios/build \
  CODE_SIGNING_ALLOWED=NO build
```

Debug on the simulator loads JS from `npm run start:dev`; Release embeds it.

**Device, Release (works without the Mac)** [verified: `scripts/ios-device-install.sh`]:

```bash
export THREADFOLIO_APP_VARIANT=dev
export SCAN_API_ORIGIN=<the dev scan host, as written in scripts/ios-device-install.sh>
xcodebuild -workspace ios/ThreadfolioDev.xcworkspace -scheme ThreadfolioDev -configuration Release \
  -destination 'generic/platform=iOS' -allowProvisioningUpdates CODE_SIGN_STYLE=Automatic \
  DEVELOPMENT_TEAM=LQJNDVBL43 EXTRA_PACKAGER_ARGS=--skip-server -derivedDataPath ios/build build
# app: ios/build/Build/Products/Release-iphoneos/ThreadfolioDev.app
```

The repo's script uses `-destination id=<udid>`; `generic/platform=iOS` is the runner's form and
needs the device already registered in the team [inference]. The script also refuses to build
Release when `$SCAN_API_ORIGIN/health` doesn't answer. Without `SCAN_API_ORIGIN`, scans go through
the Mac's dev server [verified: `app.config.js` comment].

**Production:** only `dev` installs to a device today ("until the scan service is deployed")
[verified]. A production build needs `SCAN_API_ORIGIN`, and with `THREADFOLIO_RELEASE=1` refuses
to build without it [verified].

**Env and config files:**

| File | Needed by the app build? | Secret? |
|---|---|---|
| `.env` (gitignored) | No. Read only by the server-side `/api/scan` route, never the app bundle [docs: `.env.example`]. Holds `ANTHROPIC_API_KEY` and optional scan overrides | **Yes. Stays out of the runner's clone** |
| `eas.json` | No (EAS cloud only) | No |
| `SCAN_API_ORIGIN` | Release dev build: yes, a URL | No |

Expo CLI loads a `.env` it finds at the project root [inference]. Since `.env` is gitignored, a
fresh clone has none, which is what we want.

## Mizyun

| Item | Value |
|---|---|
| Repo | `AdamHikl/mizyun`, pnpm 10.33.0 workspace, Node >= 22.13.0 [verified: root `package.json`] |
| App | `apps/mobile` (`@mizyun/mobile`), Expo SDK 57 [verified]. `apps/watch-ios` holds the watch app's sources, pulled in by a config plugin for the dev variant only [verified: `plugins/with-workout-companion.js`]. `apps/api` is the server |
| Variants | `dev`: "Mizyun Dev", **`com.mizyun.development`**, scheme `mizyun-dev`. `production`: "Mizyun", `com.mizyun.app`, scheme `mizyun` [verified: `app.config.js`]. Mizyun's `AGENTS.md` says `com.mizyun.dev` for the iOS dev app; that is the Android package, the code says `com.mizyun.development` |
| Picked by | `MIZYUN_APP_VARIANT` (default `dev`), `MIZYUN_BUILD_PROFILE` [verified] |
| Targets (dev) | `MizyunDev` (app), `MizyunWorkoutWatchDev` (watch, `com.mizyun.development.watchkitapp`), `ExpoWidgetsTarget` (`com.mizyun.development.ExpoWidgetsTarget`) [verified: `xcodebuild -list`, `app.config.js`] |
| Workspace, scheme (dev) | `apps/mobile/ios/MizyunDev.xcworkspace`, scheme `MizyunDev` [verified] |
| Workspace, scheme (production) | `Mizyun.xcworkspace`, `Mizyun` [inference: scripts find `Mizyun*.xcworkspace` and use its name] |
| Configurations | `Debug`, `Release` [verified] |
| Team | `LQJNDVBL43`, written into the project by `ios.appleTeamId` [verified] |
| Capabilities | HealthKit, Sign in with Apple (`MIZYUN_ENABLE_APPLE_AUTH=1`), push (unless `MIZYUN_IOS_DISABLE_PUSH=1`), App Group `group.<bundle id>` [verified: `app.config.js`]. Signing needs profiles for all three dev bundle IDs |
| Dev client | `expo-dev-client` is **not** a dependency [verified]; Debug would load from Metro [inference] |

**Mizyun's own rules that apply** [docs: Mizyun `AGENTS.md`, `apps/mobile/AGENTS.md`]: feature
work goes to Dev; Production promotion is its own release milestone; `app.json` holds one
version tuple (`1.0.N`, build `N`) raised together before a Production store build; release
artifacts live under `apps/mobile/dist/releases/`; and (Adam's rule) for Production the IPA is
built and verified and Adam uploads it with Transporter.

**Prepare, in order** [verified: `scripts/mobile-device-install.sh`,
`scripts/mobile-founder-dev-ios.sh`, `scripts/build-production-ios-ipa.sh`]:

1. `pnpm install --frozen-lockfile` at the repo root.
2. Load the variant's env (below), with `EXPO_NO_DOTENV=1` so a stray `.env.local` can't win.
3. `pnpm --filter @mizyun/mobile exec expo prebuild --clean --platform ios`, from the repo root
   (runs `pod install` itself unless `--no-install`; with `--no-install`, run `pod install` in
   `apps/mobile/ios`). Prebuild needs the env, because `app.config.js` checks the hosts.
4. Check the generated `project.pbxproj` has the expected bundle ID (the repo's scripts refuse
   otherwise).

**Env for each step** (fixed values, set for prebuild and xcodebuild) [verified]:

```bash
export EXPO_NO_DOTENV=1 MIZYUN_APP_VARIANT=dev MIZYUN_IOS_DISABLE_PUSH=0 MIZYUN_ENABLE_APPLE_AUTH=1
set -a; . apps/mobile/.env.dev; set +a   # EXPO_PUBLIC_API_URL, _SUPABASE_URL, _SUPABASE_PUBLISHABLE_KEY, _AUTH_REDIRECT_URI
```

The scripts refuse unless the three URL values equal the dev hosts written in them.

**Simulator** [inference: no simulator script in the repo]:

```bash
xcodebuild -workspace apps/mobile/ios/MizyunDev.xcworkspace -scheme MizyunDev -configuration Release \
  -destination 'generic/platform=iOS Simulator' -derivedDataPath apps/mobile/ios/build \
  CODE_SIGNING_ALLOWED=NO build
```

HealthKit, Sign in with Apple and push don't behave on an unsigned simulator build [inference].

**Device, Release, Dev variant** [verified: `scripts/mobile-device-install.sh`]:

```bash
xcodebuild -workspace apps/mobile/ios/MizyunDev.xcworkspace -scheme MizyunDev -configuration Release \
  -destination 'generic/platform=iOS' -allowProvisioningUpdates CODE_SIGN_STYLE=Automatic \
  DEVELOPMENT_TEAM=LQJNDVBL43 -derivedDataPath apps/mobile/ios/build build
# app: apps/mobile/ios/build/Build/Products/Release-iphoneos/MizyunDev.app
```

After the build the repo's script runs `node scripts/verify-ios-apple-auth.mjs --signed <app>`.

**Production IPA:** `pnpm mobile:founder-production:ios:ipa --sha <full-sha> --build-number <N>`
[verified: `scripts/build-production-ios-ipa.sh`]. It builds in a throwaway worktree, runs
`pnpm install --frozen-lockfile`, `expo prebuild --clean` and `pnpm check`, archives, exports with
**`method: app-store-connect`**, and verifies bundle IDs, entitlements, endpoints and signature. It
copies `apps/mobile/.env.production` in and deletes it after. **This needs a Distribution
identity, which `jorah-build` will not have (Development certificate only, ADR 0002)**
[inference from the export method]. So the uploadable Production IPA stays a step Adam runs under
his own Mac user; the runner's `archive` (export method `debugging`) makes a device-installable
IPA, not one Transporter can upload. Open: see the end.

**Env and config files:**

| File | Needed | Secret? |
|---|---|---|
| `apps/mobile/.env.dev` (gitignored) | Dev build: the four `EXPO_PUBLIC_*` values | Holds the dev Supabase **publishable** key, which ships inside the app, so not a server secret; still private and not in git. **Adam places it** |
| `apps/mobile/.env.production` (gitignored) | Production IPA | Same, for Production. **Adam places it**; only Mizyun's own IPA script uses it |
| `apps/mobile/.env.local` (gitignored) | No; `EXPO_NO_DOTENV=1` keeps it out | Private |
| `certs/` | Not read; not needed for an iOS build with automatic signing [inference] | Private |
| `apps/mobile/eas.json` | No (EAS cloud) | No |

## Runner project entries (ready to paste)

**The runner's project-file schema is not on `main` yet** (checked 2026-11-11: no
`services/ios-runner/` on `origin/main`), so these entries are not in a config file. They follow
the **uncommitted draft** in issue 8's worktree (`SCHEMA = 1`, JSON, keys `path`, `workspace`,
`scheme`, `configuration`, `bundle_id`, `team_id`, `prepare` from `pnpm-install`, `npm-ci`,
`pod-install`, `expo-prebuild`). Recheck against the merged schema before pasting.

`path` is the clone under `jorah-build`'s home; the exact folder is issue 10's to choose
[inference: ADR 0002 closes `/Users/adam` to `jorah-build`].

```json
{
  "projects": {
    "threadfolio": {
      "path": "/Users/jorah-build/work/threadfolio",
      "workspace": "ios/ThreadfolioDev.xcworkspace",
      "scheme": "ThreadfolioDev",
      "configuration": "Release",
      "bundle_id": "com.threadfolio.dev",
      "team_id": "LQJNDVBL43",
      "prepare": ["npm-ci", "expo-prebuild", "pod-install"]
    },
    "mizyun": {
      "path": "/Users/jorah-build/work/mizyun",
      "workspace": "apps/mobile/ios/MizyunDev.xcworkspace",
      "scheme": "MizyunDev",
      "configuration": "Release",
      "bundle_id": "com.mizyun.development",
      "team_id": "LQJNDVBL43",
      "prepare": ["pnpm-install", "expo-prebuild", "pod-install"]
    }
  }
}
```

**These entries alone will not produce working apps with the draft runner** [inference from its
code], because the recipes need things the draft has no field for:

1. **Fixed environment per project.** The draft gives commands only PATH, HOME, TMPDIR and
   DEVELOPER_DIR. Threadfolio Release needs `THREADFOLIO_APP_VARIANT=dev`, `SCAN_API_ORIGIN` and
   the build setting `EXTRA_PACKAGER_ARGS=--skip-server`. Mizyun needs the four fixed variables
   above plus `.env.dev`'s values. Without them Mizyun's prebuild still passes, but the app is
   built pointing at no API. Suggested: a fixed `env` map and an admin-owned `env_file` outside the
   clone, both in the project file, never from the model.
2. **`expo-prebuild` runs `pnpm exec expo` at the clone root.** Mizyun needs it in `apps/mobile`
   (or `pnpm --filter @mizyun/mobile exec`); Threadfolio is an npm project (`npx expo`). Both
   repos' scripts use `--clean`.
3. **Threadfolio's prebuild edits tracked `package.json`**; a restore step is needed before the
   next sync's clean-tree check.
4. **`-allowProvisioningUpdates CODE_SIGN_STYLE=Automatic`**, which both repos pass, aren't in the
   draft's device build.

These went to the runner session as a note; the runner decides how to cover them.

## Making Mizyun push-capable for Jorah

**Already done** [verified 2026-11-11 with `gh api`, read-only]: `AdamHikl/mizyun` has both
rulesets active, "jorah: only jorah/**" and "jorah/**: no force, no delete" (applied 2026-11-10,
`docs/evidence/github-rulesets/2026-11-10.md`, ids 26961398 / 26961402), and `main` reports rules
`creation, deletion, non_fast_forward, update`. The `jorah-bot` installation covers all
repositories (`repository_selection: all`, same evidence file) [docs]. So no step is needed.
If it ever has to be redone, Adam's steps:

1. GitHub → Settings → Applications → **jorah-bot** → **Configure**. Expected: "All repositories",
   or `mizyun` ticked under "Only select repositories".
2. A Mac Terminal signed in to `gh` as Adam, in `~/Documents/jorah`:
   `scripts/github/protect-repo.sh AdamHikl/mizyun --dry-run`. Expected: lists the existing
   rulesets and "Dry run: would add the two rulesets".
3. Same, without `--dry-run`. Expected: "ruleset present" (or "ruleset added") for both names,
   then "Rulesets now:" listing both as `active`.
4. Check: `gh api repos/AdamHikl/mizyun/rules/branches/main --jq '.[].type'`. Expected: includes
   `creation` and `update`. Jorah's plugin runs the same check before every push.

## Still open

- **Proving each recipe on the Mac** (issue 11's goal, issue 12's tests): no build was run. Tiers
  open: build, install, launch, signed-in device use.
- **Runner fields** for env, prebuild location and signing flags (above).
- **Mizyun Production upload** needs a Distribution identity that `jorah-build` won't hold. Either
  Adam keeps running `pnpm mobile:founder-production:ios:ipa` under his own user, or ADR 0002's
  limit changes. Adam's call.
- **Signing for `jorah-build`** (issue 10) must cover all three Mizyun dev bundle IDs and their
  capabilities, and Threadfolio's `com.threadfolio.dev`.
- **Adam places** `apps/mobile/.env.dev` (and only if ever needed, `.env.production`) where the
  runner reads it, in a Terminal attached to no agent.
- Mizyun's `AGENTS.md` names `com.mizyun.dev` as the iOS dev bundle ID; the code says
  `com.mizyun.development`. A one-line fix for Mizyun, not made here.
