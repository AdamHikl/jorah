# iOS builds on the Mac: one-time setup

Issue 10. What Adam does once so Jorah, on the PC, can build Threadfolio and Mizyun on this Mac,
run them on the iOS Simulator and install them on the iPhone, without Adam's own login session.
Route 2 of ADR 0002 (accepted 2026-11-12): the `jorah-ios` plugin on the PC calls the runner
(`services/ios-runner`) on the Mac over the tailnet, under the contract
`docs/contracts/jorah-ios-v1.md`. Written 2026-11-11, updated 2026-11-12, on this Mac: macOS
27.0.1, Xcode 27.2 (27B52), devicectl 651.32, MacBookPro18,4. Nothing here was run by an agent
except read-only checks. **Tier reached: source and tests.**

Labels on each claim:

- **[verified]** checked read-only on this Mac, or in this repo, on the date above.
- **[docs-only]** from Apple's, GitHub's or a man page's text, not tried here.
- **[inference]** reasoned, not documented or tried. Each one has a check in section 8 or the test pass.

**Check where you are at any time** (read-only, no sudo). As `adam`:

```bash
~/Documents/jorah/scripts/mac/ios-preflight.sh
```

As `jorah-build`, which cannot read your home, the copy step A2 installs:
`/usr/local/libexec/jorah/ios-preflight`.

Each line says `done`, `missing` or `unknown`, and the step below that fixes it. Some checks can
only be seen from `jorah-build` and show `unknown` from `adam`, never `done`.

## Adam's steps

In order. Each step's section below has the full commands and what to expect.
- **Mac, adam**: a Terminal in your own account.
- **Mac, jorah-build**: a Terminal in the `jorah-build` login session (Control Center → Fast User
  Switching).
- **No agent**: a Terminal attached to no agent. Use it for every step marked so: those steps
  handle a key or a password.

Times are your hands-on time. After each step, the preflight shows that step as `done`.

| # | Where | What | Expected | Time |
|---|---|---|---|---|
| **A1** | Decision | ~~Which Apple team signs for `jorah-build`~~ **Done 2026-11-12: company team**, the one the tested allowlist names in `services/ios-runner/ios-projects.json`. Nothing to change before A9 | Recorded in ADR 0002 (D3) and on issue 10 | 0 min |
| **A2** | Mac, adam | `cd ~/Documents/jorah && git pull --ff-only && scripts/mac/setup-jorah-build.sh --dry-run`, then `sudo scripts/mac/setup-jorah-build.sh`, `yes`, and a new password for `jorah-build` (into your password manager). §1 | `Result:` shows `jorah-build` not an admin and in `_developer`; root-owned folders; the hand-off folder's ACL | 3 min |
| **A3** | Mac, jorah-build | First login. Skip every setup offer, **never** sign in to an Apple Account. Run `/usr/local/libexec/jorah/ios-preflight`. §2 | Xcode and simulators `done` | 5 min |
| **A4** | Mac, jorah-build, then a browser as adam | Development certificate made inside `jorah-build`, then the two `security` settings. §3.2, §3.3 | `security find-identity -v -p codesigning` shows `1 valid identities found` | 10 min |
| **A5** | Browser as adam, then Mac, jorah-build | Four Development profiles with the exact names in §3.5, moved into `jorah-build` | Preflight as jorah-build: profiles `done` | 15 min |
| **A6** | Mac, jorah-build | `xcrun devicectl list devices`. Note the iPhone's **Identifier** (UDID) for A9. §4 | iPhone `available (paired)`. If not: USB, unlock, `xcrun devicectl manage pair --device <UDID>`, tap Trust | 2 min |
| **A7** | Mac, jorah-build, then Mac, adam | Read-only deploy keys, then clones into `~/src/threadfolio` and `~/src/mizyun`. §6 | Preflight: both clones `done` | 10 min |
| **A8** | Mac, adam, **no agent** | Mizyun's env file: one line with the dev Supabase publishable key, copied from your `.env.dev` by `grep … \| sudo tee`. §5.1. The runner refuses to build Mizyun without it | Preflight: `done mizyun env file …` (root, 644) | 2 min |
| **A9** | Mac, adam | `scripts/mac/install-ios-allowlist.sh --dry-run <UDID>`, then `sudo scripts/mac/install-ios-allowlist.sh <UDID>`, `yes`. It installs the tested `services/ios-runner/ios-projects.json` with your iPhone added as `adam-iphone`. §5.1 | Preflight: allowlist and devices `done` | 2 min |
| **A10** | Mac, adam | `sudo scripts/mac/setup-jorah-build.sh --install-runner`, `yes`. §5.2 | `Result:` lists the LaunchAgent plist and wrapper as `root:wheel` | 2 min |
| **A11** | Mac, jorah-build, **no agent** | Make the shared runner key and note its SHA-256. §5.3 step 1 | Preflight as jorah-build: key `done` | 1 min |
| **A12** | Mac, jorah-build | Log `jorah-build` out and back in, run `curl -s http://127.0.0.1:47820/v1/health`, switch back to your account and leave it logged in. §5.4 | `{"contract": "jorah-ios/1", …}`; preflight: runner `done` | 3 min |
| **A13** | Tailscale admin console | The grant from ADR 0002 step 2. §5.5 | Policy saves, its tests pass | 5 min |
| **A14** | Mac, adam | `tailscale serve --bg --tcp=47820 tcp://127.0.0.1:47820`. §5.5 | Preflight: Serve forward `done` | 1 min |
| **A15** | Your yes, to a build session | Copy `main` into `/opt/jorah` on the PC: plugin, patches and `scripts/pc/receive-ios-key.sh`. §5.6a | The session reports the files and their hashes | 1 min |
| **A16** | Mac, adam, **no agent** | Send the key to the PC: `sudo base64 -i … \| ssh … receive-ios-key.sh`. §5.3 step 2 | The PC prints the same SHA-256 as A11 | 2 min |
| **A17** | PC, from a Mac Terminal | Install the `jorah-ios` plugin, set `runnerUrl`, then each patch: `--dry-run` first, then apply. §5.6b, §5.6c | Each dry run: "Dry run successful", updates only where its header says, nothing under `gateway.*` | 15 min |
| **A18** | Your yes, to the P5 work | The `jorah-guard` matrix line: `ios_build`, `ios_install`, `ios_status` under `taintRead` in `config/permission-matrix.json`. Belongs to P5, not issue 10. Needed only if `jorah-guard` is on. §5.6d | A P5 commit with the line, deployed by P5's own steps | 1 min |
| **A19** | Mac, adam | Check that Mizyun is push-capable for Jorah: `gh api repos/AdamHikl/mizyun/rules/branches/main --jq '.[].type'`. Already done on 2026-11-10. If not, §6b | Includes `creation` and `update` | 1 min |
| **A20** | Mac and Telegram | The test pass: `docs/runbooks/ios-test-pass.md`. Its gates G1 to G5 are steps A2 to A18 here. Then the extra checks in §8 | Each result PASS, FAIL or NOT RUN, in `docs/evidence/issue-12/test-pass.md` | 60 min, mostly waiting |
| **A21** | Mac, docked | TOPO-B5, the 24-hour dock test. §7 | Every check answered; no `Sleep` line | 10 min over 24 h |

After every Mac restart: FileVault waits for you, as it does now. Then log in to `jorah-build` once
and switch back (§3.4). That is the only recurring step.

## 0. Decisions

ADR 0002 is accepted (route 2, waiver, paid team with a Development certificate only, device
install on the iPhone, all simulator use, no cards for simulator actions). Still yours:

| # | Decision | Options | Recommendation |
|---|---|---|---|
| A1 / ADR D3 | Which of the two teams in your keychain | Personal team ("Adam Hikl"), or company team ("itinn s.r.o.") | **Company team.** Both apps' own device scripts sign with it, and Mizyun's bundle IDs, capabilities and existing profiles all sit there [verified: issue 11's `docs/runbooks/ios-recipes.md`; profile `TeamName` on this Mac]. The personal team would need new App IDs and capabilities. One certificate, one team. The tested allowlist `services/ios-runner/ios-projects.json` names the company team |
| S1 | Source access for the runner's clones | Read-only deploy key per repo, or a GitHub App token per run | **Deploy keys now, token later.** The runner today fetches with whatever git credentials `jorah-build` has and takes no token (`docs/evidence/issue-8/README.md`) [verified], so a token needs runner and plugin work first. Section 6 |
| S2 | When the runner may sign | Only while `jorah-build` is logged in (no stored secret), or a stored keychain password | **Logged in** (section 3.4) |

Both teams already have an Apple Development identity in your own keychain [verified:
`security find-identity -v -p codesigning` lists three, two on the personal team, one on the
company team]. Those stay yours. `jorah-build` gets its own (section 3).

## 1. Create the account and folders (A2)

```bash
cd ~/Documents/jorah && git pull --ff-only && scripts/mac/setup-jorah-build.sh --dry-run
```

**Expect** "This will:" with: create standard user `jorah-build`, add it to `_developer`, create
group `jorah-handoff`, add you to it, create `/usr/local/libexec/jorah`, create
`/Library/Application Support/Jorah` and its `env` folder, install the read-only preflight, set up
`/Users/Shared/jorah-handoff`. Two `note` lines:
runner not installed yet, and DevToolsSecurity is disabled. "Dry run: nothing changed."
[verified: dry run on this Mac]

```bash
sudo scripts/mac/setup-jorah-build.sh
```

sudo asks for **your** password; type `yes`; sysadminctl asks for the **new password for
`jorah-build`**. That is its login and login-keychain password.

**Expect** "Result:" with `uid=…(jorah-build)` showing `_developer`, `ok jorah-build is not an
admin`, `/usr/local/libexec/jorah` and `/Library/Application Support/Jorah` as
`root:wheel drwxr-xr-x`, and `/Users/Shared/jorah-handoff` as `jorah-build jorah-handoff` with
`group:jorah-handoff allow list,search,…`. Log out and in once so Finder sees your new group.

The script sets no autologin (it turns it off if it was `jorah-build`), no admin rights, no
keychain, certificate, pairing, power or security setting [verified: source]. `jorah-build` gets
no Secure Token, so it cannot unlock FileVault [docs-only: `sysadminctl` usage]. FileVault is on
[verified: `fdesetup status`], so after a restart nothing of Jorah's runs until you log in.

The hand-off ACL was tried on a scratch folder with group `staff`: a run folder and a file
created inside inherit read and delete for the group [verified]. On the real folder: section 8.

## 2. First login as jorah-build (A3)

One interactive login gives `jorah-build` a home folder, a login keychain and Xcode's per-user
state.

1. Control Center → **Fast User Switching** → **Jorah build**, and type its password.
2. Skip Apple Account sign-in, Siri, Screen Time and every other offer. **Never sign in to an
   Apple Account, or to Xcode → Settings → Accounts, in this user.**
3. Terminal:

```bash
/usr/local/libexec/jorah/ios-preflight
```

**Expect** `done` for Xcode, first-launch packages, simulator runtimes and simulators; the other
lines name the step that comes next. Runtimes are system-wide in
`/Library/Developer/CoreSimulator`, root-owned and readable by all [verified], and first-launch
packages are installed [verified: `xcodebuild -checkFirstLaunchStatus` exits 0 as `adam`].
Simulator *devices* are per user, under `~/Library/Developer/CoreSimulator/Devices` [verified:
24 in `adam`'s]; a new user should get a default set on first `simctl` use [inference]. If the
list is empty: `xcrun simctl create "iPhone 17 Pro" "iPhone 17 Pro"`. If xcodebuild asks for the
license, run `sudo xcodebuild -license accept` from **your** account.

## 3. Signing: a Development certificate only `jorah-build` holds (A4, A5)

### 3.1 Why manual signing

`xcodebuild -allowProvisioningUpdates` "Requires a developer account to have been added in
Xcode's Accounts preference pane", or an App Store Connect key [docs-only: `man xcodebuild`].
`jorah-build` has neither, by rule. So automatic signing cannot create, renew or register
anything there. The runner signs manually: one `-xcconfig` per run with
`CODE_SIGN_STYLE = Manual`, `Apple Development`, the team, and a profile per target from the
allowlist's `signing.profiles` [verified: `services/ios-runner/README.md`, "Signing"].

### 3.2 Make the key inside jorah-build, so it never leaves

In the **jorah-build** session:

1. Keychain Access → **Keychain Access → Certificate Assistant → Request a Certificate From a
   Certificate Authority…** [docs-only: Apple Developer help, "Create a certificate signing
   request"].
2. User email: any address of yours. Common name: `Jorah build`. CA email: empty. **Saved to
   disk.** Save as `/Users/Shared/jorah-handoff/jorah-build.certSigningRequest`.

**Expect** a new private key `Jorah build` under **login → Keys**.

In **your** session, in a browser:

3. developer.apple.com → Account → the team from A1 → Certificates → **+** → **Apple
   Development** → upload the request → Download. **Never** Apple Distribution.
4. Copy the downloaded `.cer` to `/Users/Shared/` (public; fine there for a minute).

Back in **jorah-build**:

5. Double-click the `.cer`, keychain **login**. Delete it from `/Users/Shared/` and the request
   from the hand-off folder.
6. `security find-identity -v -p codesigning`

**Expect** exactly `1 valid identities found`, named `"Apple Development: <your name> (…)"`
[inference: your own identities are named that way]. Note its expiry date: that is how you tell
it apart from yours in the developer website.

### 3.3 Let codesign use the key without a dialog

In **jorah-build**'s Terminal:

```bash
security set-key-partition-list -S apple-tool:,apple:,codesign: -s ~/Library/Keychains/login.keychain-db
```

It asks for the `jorah-build` password. **Expect** the key's attributes, no error. "If you'd like
to run /usr/bin/codesign with the key, 'apple:' must be an element of the partition list"
[docs-only: `man security`].

```bash
security set-keychain-settings ~/Library/Keychains/login.keychain-db && security show-keychain-info ~/Library/Keychains/login.keychain-db
```

**Expect** `no-timeout`: no lock on sleep or timer [docs-only: `man security`].

### 3.4 When is the key usable? (S2)

A login keychain is unlocked by logging in to that user. A build outside `jorah-build`'s login
session would most likely find it locked, and codesign would fail [inference]. Unlocking it there
needs its password at each run: a stored secret, a gate this runbook does not cross. So **you log
in to `jorah-build` once after each restart** and switch back; the runner runs as a LaunchAgent in
that background session (`scripts/mac/com.jorah.ios-runner.plist`, root-owned, starts only for
`jorah-build`) [inference until section 8, check 4]. Sleep does not end the session.

### 3.5 Profiles

Developer website, the team from A1, one **iOS App Development** profile per bundle ID
[verified: `docs/runbooks/ios-recipes.md`]. Use exactly these names: the allowlist
(`services/ios-runner/ios-projects.json`, `signing.profiles`) refers to them.

| Profile name | Bundle ID | Target in the allowlist |
|---|---|---|
| `Jorah com.threadfolio.dev` | `com.threadfolio.dev` | `ThreadfolioDev` [inference: target named like the scheme] |
| `Jorah com.mizyun.development` | `com.mizyun.development` | `MizyunDev` |
| `Jorah com.mizyun.development.ExpoWidgetsTarget` | `com.mizyun.development.ExpoWidgetsTarget` | `ExpoWidgetsTarget` |
| `Jorah com.mizyun.development.watchkitapp` | `com.mizyun.development.watchkitapp` | `MizyunWorkoutWatchDev` (pick the watchOS development type if the portal offers it [inference]) |

1. Profiles → **+** → development type → App ID → only the certificate from 3.2 → your iPhone →
   the name above → Generate → Download [docs-only: Apple Developer help].
2. Copy the four files to `/Users/Shared/`, then in **jorah-build**:

```bash
mkdir -p ~/Library/Developer/Xcode/UserData/"Provisioning Profiles" && mv /Users/Shared/*.mobileprovision ~/Library/Developer/Xcode/UserData/"Provisioning Profiles"/
```

Xcode 27 reads profiles from that folder [verified: your seven profiles are there and
`~/Library/MobileDevice/Provisioning Profiles` is empty]. A profile holds no private key.
Profiles expire, about yearly, and list the devices they allow [docs-only].

## 4. The iPhone (A6)

As `adam` [verified 2026-11-11 and 2026-11-12]: your iPhone 16 Pro is paired, Developer Mode
`enabled`, reached over the local network or by cable.

1. **Developer Mode** is on the phone, not per Mac user, and stays on [docs-only: Apple,
   "Enabling Developer Mode on a device"].
2. **Pairing for jorah-build.** USB trust records are system-wide under `/var/db/lockdown`, owned
   by `_usbmuxd` [verified: listing], so `jorah-build` may already see the phone paired
   [inference]. In **jorah-build**: `xcrun devicectl list devices`. **Expect** your iPhone
   `available (paired)`. If not: unlock the phone, USB, `xcrun devicectl manage pair --device
   <UDID>`, tap **Trust**, passcode on the phone [docs-only: `devicectl manage pair --help`].
   Note the **Identifier** column: that UDID goes into the allowlist as `adam-iphone` in step A9,
   the alias the test pass uses. It is not committed anywhere.
3. **USB or network.** Same LAN or cable. Not over Tailscale [inference: discovery is local].
4. **Phone locked.** Install expected to work, launch to fail until unlocked; the runner says
   "Is the phone locked?" with `LAUNCH_FAILED` [verified: runner source].
5. **Phone away.** `DEVICE_UNAVAILABLE`; the build stays in `/Users/Shared/jorah-handoff/<run-id>`
   [verified: runner README].

`DevToolsSecurity` is disabled [verified]. The runner has no debug verb, so leave it.

### 4b. Simulators under jorah-build

ADR D4 allows all simulator use, with no cards for simulator actions.

- **Verified as `adam`:** the runner booted a simulator, installed and launched the fixture app
  and took a screenshot over HTTP on loopback (`docs/evidence/issue-8/`). CoreSimulator's service
  runs per user in the login session (`com.apple.CoreSimulator.CoreSimulatorService` in
  `adam`'s `gui/` domain) [verified: `launchctl print`].
- **Inference:** under `jorah-build` the same works because the runner runs inside that user's
  login session (the LaunchAgent), while that session is in the background behind yours. A
  standard user with **no** login session at all would probably not get CoreSimulator; this
  setup never needs that.
- **Test:** section 8, check 5, with `jorah-build` switched to the background.

## 5. The runner service (A8 to A17)

### 5.1 Mizyun's env file and the allowlist (A8, A9)

**The allowlist** is `services/ios-runner/ios-projects.json`. Its entries built both apps and
launched them on the simulator through the runner (`docs/evidence/issue-11/README.md`)
[verified there]. It is the only copy. It is installed as `/Library/Application
Support/Jorah/ios-projects.json`, root-owned, `0644`. The runner refuses the file if group or
others can write it, if it is owned by anyone but root or the runner's own user, or if it has an
unknown key [verified: `services/ios-runner/ios_runner/config.py`]. The runner reads it when it
starts.

**A8, Mizyun's env file.** The app needs `EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY`. That value is only
in your `apps/mobile/.env.dev`, and it ships inside the app. Without the file the runner refuses
to build Mizyun (`envFile is missing`) [verified: runner source]. In a Terminal attached to no
agent, in your account, copy just that one line into place without displaying it:

```bash
grep -E '^(export )?EXPO_PUBLIC_SUPABASE_PUBLISHABLE_KEY=' ~/Documents/mizyun/apps/mobile/.env.dev | sudo tee "/Library/Application Support/Jorah/env/mizyun-dev.env" >/dev/null && sudo chmod 644 "/Library/Application Support/Jorah/env/mizyun-dev.env" && sudo wc -l "/Library/Application Support/Jorah/env/mizyun-dev.env" && ls -l "/Library/Application Support/Jorah/env/"
```

**Expect** `1 …/mizyun-dev.env` and `-rw-r--r--  root  wheel`. The runner only reads it at build
time and logs the name, never the value [verified: issue 11 evidence]. The preflight checks
that the file exists, its owner and its mode, never its content.

**A9, the allowlist with your iPhone.** In your account, with the UDID from A6:

```bash
cd ~/Documents/jorah && scripts/mac/install-ios-allowlist.sh --dry-run <UDID>
```

**Expect** `Adds: devices.adam-iphone = <UDID>` and "Installs … (new)". Then:

```bash
sudo scripts/mac/install-ios-allowlist.sh <UDID>
```

Type `yes`. **Expect** `root:wheel -rw-r--r-- …/ios-projects.json`. Running it again later shows a
diff against the installed copy first: use that after `main` changes the file. If the runner is
already running, restart it afterwards, as `jorah-build`:
`launchctl kickstart -k gui/$(id -u)/com.jorah.ios-runner`. A test loads this merged file with
the runner's own checker [verified: `scripts/mac/tests`].

### 5.2 Install the runner and its agent (A10)

```bash
cd ~/Documents/jorah && scripts/mac/setup-jorah-build.sh --dry-run --install-runner
```

**Expect** the plan to add three things:
- copy the runner to `/usr/local/libexec/jorah/ios-runner`;
- install `ios-runner-agent`;
- install `/Library/LaunchAgents/com.jorah.ios-runner.plist`.

Then run it again with `sudo`, without `--dry-run`, and type `yes`. The agent runs
`/usr/bin/python3 -I /usr/local/libexec/jorah/ios-runner/bin/jorah-ios-runner serve` on
`127.0.0.1:47820` [verified: runner README and `cli.py`]. For any user but `jorah-build`, the
wrapper exits at once [verified: source; a test checks that the plist and the wrapper agree].
After `main` updates the runner, run this step again.

### 5.3 The shared key (A11, A16)

One random 32-byte key, the same on both machines. It never goes in a chat, the repo, config or
an environment variable (contract, "Key"). Both sides read it per request [verified: runner
README].

1. **A11. Mac, jorah-build**, in a Terminal attached to no agent:

```bash
umask 077 && mkdir -p ~/.config/jorah-ios && openssl rand -out ~/.config/jorah-ios/runner.key 32 && shasum -a 256 ~/.config/jorah-ios/runner.key
```

   Note the hash. It is not secret.

2. **A16. Mac, adam**, in a Terminal attached to no agent, after A15:

```bash
sudo base64 -i /Users/jorah-build/.config/jorah-ios/runner.key | ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/receive-ios-key.sh
```

   **Expect** `Written /home/jorah/.config/jorah-ios/runner.key (600)` and the same hash as step 1.
   The key goes as base64 inside SSH, straight from your Terminal to the PC; no agent, chat, file
   or repo sees it. The script writes the key only if it decodes to exactly 32 bytes [verified:
   source; not run, because it runs on the PC]. If the hashes differ, run step 2 again.

### 5.4 Start it (A12)

Switch to `jorah-build` (Fast User Switching). Apple menu → **Log Out Jorah build**, log in again,
then in its Terminal:

```bash
curl -s http://127.0.0.1:47820/v1/health
```

**Expect** `{"contract": "jorah-ios/1", …, "busy": false}`. Switch back to your account **without
logging `jorah-build` out**. From your account, `scripts/mac/ios-preflight.sh` shows the runner
and its health as `done`.

Off switch, quickest first:
1. `tailscale serve --tcp=47820 off`
2. Log out `jorah-build`.
3. `sudo rm /Library/LaunchAgents/com.jorah.ios-runner.plist`

Note for issue 8: build scripts run third-party code as `jorah-build`, which can read its own
copy of the key. That code could sign requests to the runner, but the runner only does what the
allowlist already lets `jorah-build` do, and the PC accepts no requests [inference].

### 5.5 Tailnet (A13, A14)

- **A13, Tailscale admin console → Access controls**: add to `grants`
  `{ "src": ["tag:jorah-pc"], "dst": ["adam-mac"], "ip": ["tcp:47820"] }`. If the PC isn't
  tagged, use its device name (ADR 0002, step 2). **Expect** the policy to save, with its `tests`
  passing.
- **A14, Mac, adam**: `tailscale serve --bg --tcp=47820 tcp://127.0.0.1:47820`. **Expect**
  `tailscale serve status` to list TCP 47820, and the preflight to show it `done`.

### 5.6 The PC side (A15, A17, A18)

a. **A15, files.** A build session copies `main` into `/opt/jorah` on your yes, as for earlier PC
   changes (`docs/runbooks/jorah-on-pc.md`). That brings `plugins/jorah-ios`, both patches and
   `scripts/pc/receive-ios-key.sh`.

b. **A17, plugin.** Run as `jorah`: `openclaw --profile jorah plugins install --link
   /opt/jorah/plugins/jorah-ios`. This is the same way `scripts/pc/install-github.sh` installs
   `jorah-github`. If issue 9's own install step exists by then, use it instead.

c. **A17, config.** Each patch replaces whole arrays, so first compare against what is applied:
   `config get plugins.allow` and `config get agents.entries.main.tools.sandbox.tools.alsoAllow`,
   as each patch's header says. Set `runnerUrl` to the Mac's MagicDNS name. Then, as `jorah`:

```bash
openclaw --profile jorah config patch --file /opt/jorah/config/pc/ios.patch.json5 --dry-run
```

   **Expect** "Dry run successful", with updates only under `plugins.allow` and
   `plugins.entries.jorah-ios`, and nothing under `gateway.*` or `agents.*`. Then run it again
   without `--dry-run`. Then do the same two commands with `ios-tools.patch.json5`: one update,
   `agents.entries.main.tools.sandbox.tools.alsoAllow`. Neither patch needs a Gateway restart
   (ADR 0002: plugin config reloads).

d. **A18, `jorah-guard`.** This step belongs to the P5 work, not issue 10, and needs your yes. The
   guard blocks every tool that isn't in `config/permission-matrix.json`. The line to add, from
   `docs/evidence/issue-9/README.md`:
   `"taintRead": [..., "ios_build", "ios_install", "ios_status"]`. The tools are treated as
   reading outside text, because their results repeat repo content. They are still blocked while
   Jorah is frozen. The plugin shows the card, and the guard adds none. Needed only once the guard
   is enabled on the PC.

## 6. Source access for the runner's clones (A7)

Clones live in `jorah-build`'s home under `~/src/<app>`. That is the `path` in
`services/ios-runner/ios-projects.json`, and what the preflight checks.

| | Read-only deploy key, one per repo | GitHub App token, one per run |
|---|---|---|
| Scope | One repo per key, read-only by default [docs-only: GitHub, "Managing deploy keys"] | One repo, `contents: read` [verified: `plugins/jorah-github/github.js` `repoToken`] |
| Lifetime | Never expires [docs-only] | One hour [verified: same file] |
| Where the secret lives | `jorah-build`'s `~/.ssh`, on a laptop that travels | On the PC; a 1-hour token crosses to the Mac |
| If the Mac is lost | Read access to both repos until you delete the keys | Nothing to revoke |
| Works today | **Yes**: the runner fetches with `jorah-build`'s own git credentials [verified: issue 8 evidence] | **No**: needs a token field in the runner and plugin |

**Now: deploy keys.** Switch to a token once issues 8 and 9 support it, then delete the keys.

1. **Mac, jorah-build:**

```bash
mkdir -p ~/.ssh ~/src && chmod 700 ~/.ssh && for r in threadfolio mizyun; do ssh-keygen -q -t ed25519 -N '' -C "jorah-build $r read-only" -f ~/.ssh/jorah_${r}_ro && cp ~/.ssh/jorah_${r}_ro.pub /Users/Shared/; printf 'Host github-%s\n  HostName github.com\n  User git\n  IdentityFile ~/.ssh/jorah_%s_ro\n  IdentitiesOnly yes\n' "$r" "$r" >> ~/.ssh/config; done; ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null; ssh-keygen -lf ~/.ssh/known_hosts
```

   **Expect** the fingerprint `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`, GitHub's
   published Ed25519 key [docs-only: GitHub, "GitHub's SSH key fingerprints"]. If it differs,
   stop and delete `~/.ssh/known_hosts`.

2. **Mac, adam** (gh is signed in as you):

```bash
for r in threadfolio mizyun; do gh repo deploy-key add /Users/Shared/jorah_${r}_ro.pub --repo AdamHikl/$r --title "jorah-build read-only"; rm /Users/Shared/jorah_${r}_ro.pub; done
```

   Without `--allow-write`, the keys are read-only [docs-only: `gh repo deploy-key add --help`].
   Keys added by gh are removed if you ever de-authorize gh's token [docs-only, same help].

3. **Mac, jorah-build:**

```bash
git clone git@github-threadfolio:AdamHikl/threadfolio.git ~/src/threadfolio && git clone git@github-mizyun:AdamHikl/mizyun.git ~/src/mizyun
```

   **Expect** both clones. The runner's `sync` fetches from that `origin` [verified: runner
   source]. Leave the clones clean: the runner refuses a dirty tree and never resets it.

### 6b. Mizyun push-capable for Jorah (A19)

This is separate from builds. It lets Jorah push `jorah/<task>` branches to Mizyun. **Already
done** [verified 2026-11-11 by issue 11, `docs/runbooks/ios-recipes.md`]: both rulesets are
active, and `jorah-bot` covers all repositories. The check:

```bash
gh api repos/AdamHikl/mizyun/rules/branches/main --jq '.[].type'
```

**Expect** a list that includes `creation` and `update`. If not:
1. GitHub → Settings → Applications → **jorah-bot** → **Configure**: "All repositories", or
   `mizyun` ticked.
2. `scripts/github/protect-repo.sh AdamHikl/mizyun --dry-run`, then the same without
   `--dry-run`.
3. **Expect** both rulesets `active`.

## 7. Power: a MacBook that travels daily (A21)

Current settings [verified: `pmset -g custom`]: on the charger `sleep 0`, `womp 1`,
`tcpkeepalive 1`; on battery `sleep 1`. So docked with the lid open, the Mac does not sleep by
itself. **No `pmset` change is proposed**, and travel is unchanged.

- **Lid closed** sleeps the Mac unless in closed-display mode: charger, external display,
  external keyboard or mouse [docs-only, secondary sources quoting Apple; not rechecked]. A dummy
  display plug may stand in [inference].
- **Waking from the PC.** `womp` wakes on an Ethernet magic packet [docs-only: `man pmset`], so
  only docked on wired Ethernet [inference]. A sleeping Mac is not reachable over Tailscale
  [inference]. Jorah says "waiting for the Mac" (`10-roadmap.md` M19 row).

**TOPO-B5** ("Dock test: closed lid, power, display or dummy. Node stays connected 24 hours",
`research/topology.md`): dock, log in to `jorah-build` once and switch back, close the lid. Every
few hours ask Jorah for the iOS status (its `ios_status` tool reaches the runner over the
tailnet). After 24 hours, open the lid and, in your account, run `scripts/mac/ios-preflight.sh`
and:

```bash
pmset -g log | grep -E " (Sleep|Wake|DarkWake) " | tail -50
```

**Pass:** every check answered, no `Sleep` line. Save the output to `docs/evidence/10/topo-b5.txt`.

## 8. The test pass and extra checks (A20)

Run `docs/runbooks/ios-test-pass.md` (issue 12). Its gates map to the steps here:
- G1 is A2 to A5.
- G2 is A8 to A12, and A16.
- G3 is A6 and A9.
- G4 is A13 and A14.
- G5 is A17 and A18.

These extra checks turn this runbook's own inferences into results. Record them in
`docs/evidence/10/setup-checks.md`, with private parts removed.

1. `/usr/local/libexec/jorah/ios-preflight` as `jorah-build`: nothing `missing` or `unknown`.
2. A device build of Mizyun, with `jorah-build` **logged out** → it fails cleanly and doesn't hang
   (3.4).
3. A simulator boot, install, launch and screenshot through Jorah, with `jorah-build` in the
   **background** session → `tier: launch` and a PNG (4b).
4. A device install with the phone **locked** → `LAUNCH_FAILED`, but `tier: install` (4).
5. From your account: `ls -le /Users/Shared/jorah-handoff/<run-id>` shows it readable with the
   ACL inherited; deleting it works.

## 9. Evidence to record

In `docs/evidence/10/`, private content removed: preflight output, the setup script's `Result:`
blocks, the section 8 results with run IDs (the test pass has its own file), and TOPO-B5's log. Never a CSR, `.cer`,
`.mobileprovision`, key, `.env` value or UDID.

## 10. Rollback

1. Pairing, if wanted: in `jorah-build`, before step 2, `xcrun devicectl manage unpair --device
   <UDID>` [docs-only]. Your own pairing stays.
2. Account and folders:

```bash
scripts/mac/remove-jorah-build.sh --dry-run
```

```bash
sudo scripts/mac/remove-jorah-build.sh
```

   **Expect** "This will:" listing the runner agent, the user and its home (keychain, profiles,
   clones, deploy keys, runner key), `/usr/local/libexec/jorah`, `/Library/Application
   Support/Jorah` (allowlist and Mizyun's env file), the hand-off folder and the group; `yes`; then `ok … is gone` five times.
   `--keep-handoff` keeps built apps.
3. developer.apple.com: revoke the certificate with the expiry date from 3.2; delete the four
   `Jorah …` profiles.
4. GitHub: `gh repo deploy-key list --repo AdamHikl/<repo>`, then `gh repo deploy-key delete <id>
   --repo AdamHikl/<repo>`, for both repos.
5. Tailnet: `tailscale serve --tcp=47820 off`, and remove the grant in the admin console.
6. PC, as `jorah`: `rm ~/.config/jorah-ios/runner.key`, then undo the patches as their headers say.

## Open

- A1's answer (the team), then steps A2 to A21.
- A token per run instead of deploy keys: runner and plugin (issues 8 and 9).
- Every [inference] above: section 8, the test pass and TOPO-B5.
