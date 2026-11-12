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
- **[inference]** reasoned, not documented or tried. Each one has a check in section 8.

**Check where you are at any time** (read-only, no sudo). As `adam`:

```bash
~/Documents/jorah/scripts/mac/ios-preflight.sh
```

As `jorah-build`, which cannot read your home, the copy step A2 installs:
`/usr/local/libexec/jorah/ios-preflight`.

Each line says `done`, `missing` or `unknown`, and the step below that fixes it. Some checks can
only be seen from `jorah-build` and show `unknown` from `adam`, never `done`.

## Adam's steps

In order. "Mac, adam" is a Terminal in your own account. "Mac, jorah-build" is a Terminal in the
`jorah-build` login session (Control Center → Fast User Switching). Secrets, passwords and the
phone passcode are typed only into the prompt that asks for them, in a Terminal attached to no
agent. Times are your hands-on time.

| # | Where | What | Expected | Time |
|---|---|---|---|---|
| **A1** | Decision | **Which Apple team signs for `jorah-build`.** Company team (recommended: both apps, their bundle IDs and Mizyun's capabilities are already there) or personal team. Also confirm: source access by read-only deploy keys for now (section 6), and signing only while `jorah-build` is logged in (section 3.4) | Your answer on issue 10. If personal, change `"team"` in step A8's file | 2 min |
| **A2** | Mac, adam | `cd ~/Documents/jorah && git pull --ff-only && scripts/mac/setup-jorah-build.sh --dry-run`, then `sudo scripts/mac/setup-jorah-build.sh`, type `yes`, then a new password for `jorah-build` (save it in your password manager). Section 1 | `Result:` shows `jorah-build` not an admin, in `_developer`; folders root-owned; hand-off folder with an ACL line | 3 min |
| **A3** | Mac, jorah-build | First login (Fast User Switching → Jorah build). Skip every setup offer, **never** sign in to an Apple Account. In Terminal: `/usr/local/libexec/jorah/ios-preflight` (section 2) | Xcode and simulators `done`; the rest says which step comes next | 5 min |
| **A4** | Mac, jorah-build, then browser as adam | Development certificate made inside `jorah-build` (section 3.2), then `security set-key-partition-list …` and `security set-keychain-settings …` (section 3.3) | `security find-identity -v -p codesigning` shows exactly `1 valid identities found` | 10 min |
| **A5** | Browser as adam, then Mac, jorah-build | Four Development profiles, then move them into `jorah-build` (section 3.5) | Four `.mobileprovision` files in its profiles folder | 15 min |
| **A6** | Mac, jorah-build | `xcrun devicectl list devices` (section 4) | Your iPhone `available (paired)`. If not: USB, unlock, `xcrun devicectl manage pair --device <UDID>`, Trust on the phone | 2 min |
| **A7** | Mac, jorah-build, then Mac, adam | Read-only deploy keys and the two clones (section 6) | `git -C ~/work/mizyun log -1 --oneline` and the same for threadfolio print a commit | 10 min |
| **A8** | Mac, adam | Fill in and install the runner allowlist (section 5.1) | Preflight: `done allowlist filled in` | 10 min |
| **A9** | Mac, adam | `sudo scripts/mac/setup-jorah-build.sh --install-runner`, `yes` (section 5.2) | `Result:` lists the LaunchAgent plist and wrapper as `root:wheel` | 2 min |
| **A10** | Mac, jorah-build (no agent), then Mac, adam (no agent) | Make the shared runner key and send it to the PC (section 5.3). Needs `scripts/pc/receive-ios-key.sh` in `/opt/jorah` on the PC (step A14a) | The SHA-256 the PC prints equals the Mac's | 5 min |
| **A11** | Mac, jorah-build | Log `jorah-build` out and back in, run `curl -s http://127.0.0.1:47820/v1/health`, then switch back to your account and leave `jorah-build` logged in (section 5.4). From `adam`: `scripts/mac/ios-preflight.sh` | `{"contract": "jorah-ios/1", …}`; preflight shows the runner `done` | 3 min |
| **A12** | Tailscale admin console | Add the grant from ADR 0002 step 2: `{ "src": ["tag:jorah-pc"], "dst": ["adam-mac"], "ip": ["tcp:47820"] }` (or the PC's device name if it isn't tagged) | Policy saves, its `tests` pass | 5 min |
| **A13** | Mac, adam | `tailscale serve --bg --tcp=47820 tcp://127.0.0.1:47820`, then `scripts/mac/ios-preflight.sh` | Preflight: `done Tailscale Serve forwards…` | 1 min |
| **A14** | PC (from a Mac Terminal, no agent) | a. Your yes for a build session to copy `main` into `/opt/jorah`. b. Install the plugin as issue 9 says (`plugins install --link /opt/jorah/plugins/jorah-ios`). c. In `config/pc/ios.patch.json5` set `runnerUrl` to the Mac's MagicDNS name, then dry run and apply, then the same for `ios-tools.patch.json5` (section 5.5). d. If `jorah-guard` is on by then: the matrix entries from `docs/evidence/issue-9/README.md` | Each dry run: "Dry run successful", updates only where the patch header says, nothing under `gateway.*` | 15 min |
| **A15** | Telegram or Talk | Ask Jorah to build Threadfolio for the simulator, approve the card, then install it on a simulator and take a screenshot. Then a device build of Mizyun and an install to the iPhone (approve both cards). Section 8 lists what to record | Build `tier: build`; simulator install `tier: launch`; a screenshot; device install `tier: install` or `launch` | 30 min, mostly waiting |
| **A16** | Mac, docked | TOPO-B5, the 24-hour dock test (section 7) | Every check from the PC answered; no `Sleep` line | 10 min over 24 h |

After every Mac restart: FileVault waits for you (as now), then log in to `jorah-build` once
with Fast User Switching and switch back. That is the only recurring step (section 3.4).

## 0. Decisions

ADR 0002 is accepted (route 2, waiver, paid team with a Development certificate only, device
install on the iPhone, all simulator use, no cards for simulator actions). Still yours:

| # | Decision | Options | Recommendation |
|---|---|---|---|
| A1 / ADR D3 | Which of the two teams in your keychain | Personal team ("Adam Hikl"), or company team ("itinn s.r.o.") | **Company team.** Both apps' own device scripts sign with it, and Mizyun's bundle IDs, capabilities and existing profiles all sit there [verified: issue 11's `docs/runbooks/ios-recipes.md`; profile `TeamName` on this Mac]. The personal team would need new App IDs and capabilities. One certificate, one team. The template in step A8 is filled for the company team |
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
`/Library/Application Support/Jorah`, install the read-only preflight, set up
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
[verified: `docs/runbooks/ios-recipes.md`]. Use exactly these names: the allowlist template
refers to them.

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

## 5. The runner service (A8 to A11, A14)

### 5.1 The allowlist (A8)

`/Library/Application Support/Jorah/ios-projects.json`, owned by root, `0644`. The runner refuses
it if group or others can write it, if it isn't owned by root or its own user, or if any key is
unknown [verified: `services/ios-runner/ios_runner/config.py`]. The agent's wrapper points the
runner at it with `JORAH_IOS_RUNNER_CONFIG`.

`scripts/mac/ios-projects.template.json` is ready except for `<placeholders>` [verified: a test
fills them and loads the file with the runner's own checker]. In your account:

```bash
cp ~/Documents/jorah/scripts/mac/ios-projects.template.json /Users/Shared/ios-projects.json && open -e /Users/Shared/ios-projects.json
```

Replace:

- `SCAN_API_ORIGIN`: the dev scan host from Threadfolio's `scripts/ios-device-install.sh`.
- The four `<EXPO_PUBLIC_ …>` lines: names and values from Mizyun's `apps/mobile/.env.dev`. These
  end up in the app anyway; the runner refuses names containing `TOKEN`, `SECRET`, `PASSWORD`,
  `PRIVATE`, `CREDENTIAL` or `API_KEY` [verified: runner source].
- The iPhone's UDID, from `xcrun devicectl list devices`.
- `"team"` only if A1 chose the personal team.

Then:

```bash
sudo install -o root -g wheel -m 0644 /Users/Shared/ios-projects.json "/Library/Application Support/Jorah/ios-projects.json" && rm /Users/Shared/ios-projects.json && ~/Documents/jorah/scripts/mac/ios-preflight.sh
```

**Expect** `done allowlist filled in (projects: mizyun, threadfolio; …)`.

### 5.2 Install the runner and its agent (A9)

```bash
cd ~/Documents/jorah && scripts/mac/setup-jorah-build.sh --dry-run --install-runner
```

**Expect** the plan to add: copy the runner to `/usr/local/libexec/jorah/ios-runner`, install
`ios-runner-agent`, install `/Library/LaunchAgents/com.jorah.ios-runner.plist`. Then the same with
`sudo`, without `--dry-run`, and `yes`. The agent runs
`/usr/bin/python3 -I /usr/local/libexec/jorah/ios-runner/bin/jorah-ios-runner serve`, which
listens on the allowlist's loopback address, `127.0.0.1:47820` [verified: runner README and
`cli.py`]. For any user but `jorah-build` the wrapper exits at once [verified: source; a test
checks the plist and wrapper agree].

### 5.3 The shared key (A10)

One random 32-byte key, the same on both machines, never in a chat, the repo, config or an
environment variable (contract, "Key"). The runner and the plugin read it per request, so a new
key needs no restart [verified: runner README].

1. **Mac, jorah-build**, a Terminal attached to no agent:

```bash
umask 077 && mkdir -p ~/.config/jorah-ios && openssl rand -out ~/.config/jorah-ios/runner.key 32 && shasum -a 256 ~/.config/jorah-ios/runner.key
```

   Note the hash. It is not secret.

2. **Mac, adam**, a Terminal attached to no agent. This needs `scripts/pc/receive-ios-key.sh` in
   `/opt/jorah` on the PC (A14a):

```bash
sudo base64 -i /Users/jorah-build/.config/jorah-ios/runner.key | ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash /opt/jorah/scripts/pc/receive-ios-key.sh
```

   **Expect** `Written /home/jorah/.config/jorah-ios/runner.key (600)` and the same hash as step 1.
   The key travels as base64 text inside SSH, from your Terminal to the PC: no agent, chat, file
   or repo sees it. The script writes only if it decodes to exactly 32 bytes [verified: source;
   not run, it runs on the PC]. If the hashes differ, run step 2 again; nothing else changes.

### 5.4 Start it (A11)

Fast User Switching → Jorah build. Apple menu → **Log Out Jorah build**, log in as it again, then
in its Terminal:

```bash
curl -s http://127.0.0.1:47820/v1/health
```

**Expect** `{"contract": "jorah-ios/1", …, "busy": false}`. Switch back to your account without
logging `jorah-build` out. From your account, `scripts/mac/ios-preflight.sh` should show the
runner and its health `done`.

Off switch, quickest first: `tailscale serve --tcp=47820 off`; log out `jorah-build`;
`sudo rm /Library/LaunchAgents/com.jorah.ios-runner.plist`.

Note for issue 8: build scripts run third-party code as `jorah-build`, which can read its own
copy of the key. Such code could sign requests to the runner, which only does what the allowlist
already lets `jorah-build` do; the PC accepts no requests [inference].

### 5.5 The PC side (A14)

a. **Files.** A build session copies `main` into `/opt/jorah` on your yes, as for earlier PC
   changes (`docs/runbooks/jorah-on-pc.md`). It brings `plugins/jorah-ios`, the two patches and
   `scripts/pc/receive-ios-key.sh`.

b. **Plugin.** As issue 9 lays out: `openclaw --profile jorah plugins install --link
   /opt/jorah/plugins/jorah-ios`, run as `jorah` (the way `scripts/pc/install-github.sh` installs
   `jorah-github`). Follow issue 9's own install step if it has one by then.

c. **Config.** Each patch replaces whole arrays, so first compare with what is applied:
   `config get plugins.allow` and `config get agents.entries.main.tools.sandbox.tools.alsoAllow`,
   as each patch's header says. Fill `runnerUrl` with the Mac's MagicDNS name. Then, as `jorah`:

```bash
openclaw --profile jorah config patch --file /opt/jorah/config/pc/ios.patch.json5 --dry-run
```

   **Expect** "Dry run successful", updates only under `plugins.allow` and
   `plugins.entries.jorah-ios`, nothing under `gateway.*` or `agents.*`. Then without
   `--dry-run`. Then the same two commands with `ios-tools.patch.json5`: one update,
   `agents.entries.main.tools.sandbox.tools.alsoAllow`. Neither needs a Gateway restart [ADR:
   plugin config reloads].

d. **jorah-guard**, only if it is enabled on the PC by then: it blocks tools not in
   `config/permission-matrix.json`. The proposed entries (`ios_build`, `ios_install`, `ios_status`
   under `taintRead`) are in `docs/evidence/issue-9/README.md`. They are the matrix owner's (P5)
   commit, on your yes.

## 6. Source access for the runner's clones (A7)

Clones live under `jorah-build`'s home, `~/work/<repo>`, as the template's `path` says.

| | Read-only deploy key, one per repo | GitHub App token, one per run |
|---|---|---|
| Scope | One repo per key, read-only by default [docs-only: GitHub, "Managing deploy keys"] | One repo, `contents: read` [verified: `plugins/jorah-github/github.js` `repoToken`] |
| Lifetime | Never expires [docs-only] | One hour [verified: same file] |
| Secret lives | `jorah-build`'s `~/.ssh`, on a laptop that travels | On the PC; a 1-hour token crosses to the Mac |
| If the Mac is lost | Read access to both repos until you delete the keys | Nothing to revoke |
| Works today | **Yes**: the runner fetches with `jorah-build`'s own git credentials [verified: issue 8 evidence] | **No**: needs a token field in the runner and plugin |

**Now: deploy keys.** Switch to a token when issues 8 and 9 support it, then delete the keys.

1. **Mac, jorah-build:**

```bash
mkdir -p ~/.ssh ~/work && chmod 700 ~/.ssh && for r in threadfolio mizyun; do ssh-keygen -q -t ed25519 -N '' -C "jorah-build $r read-only" -f ~/.ssh/jorah_${r}_ro && cp ~/.ssh/jorah_${r}_ro.pub /Users/Shared/; printf 'Host github-%s\n  HostName github.com\n  User git\n  IdentityFile ~/.ssh/jorah_%s_ro\n  IdentitiesOnly yes\n' "$r" "$r" >> ~/.ssh/config; done; ssh-keyscan -t ed25519 github.com >> ~/.ssh/known_hosts 2>/dev/null; ssh-keygen -lf ~/.ssh/known_hosts
```

   **Expect** the fingerprint `SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU`, GitHub's
   published Ed25519 key [docs-only: GitHub, "GitHub's SSH key fingerprints"]. If it differs,
   stop and delete `~/.ssh/known_hosts`.

2. **Mac, adam** (gh is signed in as you):

```bash
for r in threadfolio mizyun; do gh repo deploy-key add /Users/Shared/jorah_${r}_ro.pub --repo AdamHikl/$r --title "jorah-build read-only"; rm /Users/Shared/jorah_${r}_ro.pub; done
```

   No `--allow-write`, so read-only [docs-only: `gh repo deploy-key add --help`]. Keys added by gh
   are removed if you ever de-authorize gh's token [docs-only, same help].

3. **Mac, jorah-build:**

```bash
git clone git@github-threadfolio:AdamHikl/threadfolio.git ~/work/threadfolio && git clone git@github-mizyun:AdamHikl/mizyun.git ~/work/mizyun
```

   **Expect** both clones. The runner's `sync` fetches from that `origin` [verified: runner
   source].

## 7. Power: a MacBook that travels daily (A16)

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

## 8. First checks (A15; turns the inferences into results)

Record pass or fail in `docs/evidence/10/setup-checks.md`, private parts removed.

1. `/usr/local/libexec/jorah/ios-preflight` as `jorah-build`: nothing `missing` or `unknown` except what depends on the PC.
2. A simulator build of Threadfolio through Jorah, card approved → `tier: build`.
3. A device build of Mizyun → `tier: build`, `codesign` shows `Apple Development` (the runner
   checks), no keychain dialog appeared in `jorah-build`.
4. Same as 3 with `jorah-build` **logged out** → fails cleanly, not hang (3.4).
5. With `jorah-build` in the **background** session: simulator boot, install and launch, and a
   screenshot through Jorah → `tier: launch` and a PNG (4b).
6. Device install of the build from 3, phone **unlocked**, then **locked** → `install` or
   `launch` the first time; `LAUNCH_FAILED` but `tier: install` the second.
7. From your account: `ls -le /Users/Shared/jorah-handoff/<run-id>` → readable, ACL inherited;
   delete it → works.

## 9. Evidence to record

In `docs/evidence/10/`, private content removed: preflight output, the setup script's `Result:`
blocks, the section 8 results with run IDs, and TOPO-B5's log. Never a CSR, `.cer`,
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
   Support/Jorah`, the hand-off folder and the group; `yes`; then `ok … is gone` five times.
   `--keep-handoff` keeps built apps.
3. developer.apple.com: revoke the certificate with the expiry date from 3.2; delete the four
   `Jorah …` profiles.
4. GitHub: `gh repo deploy-key list --repo AdamHikl/<repo>`, then `gh repo deploy-key delete <id>
   --repo AdamHikl/<repo>`, for both repos.
5. Tailnet: `tailscale serve --tcp=47820 off`, and remove the grant in the admin console.
6. PC, as `jorah`: `rm ~/.config/jorah-ios/runner.key`, then undo the patches as their headers say.

## Open

- A1's answer (team), and A2 to A16.
- Token per run instead of deploy keys: runner and plugin (issues 8, 9).
- Threadfolio Release needs the build setting `EXTRA_PACKAGER_ARGS=--skip-server`, which the
  allowlist has no field for (`docs/runbooks/ios-recipes.md`): issue 8 or 11.
- Every [inference] above: section 8 and TOPO-B5.
