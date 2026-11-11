# iOS builds on the Mac: one-time setup

Issue 10. What Adam runs once on the MacBook so Jorah's iOS runner (issue 8) can build
Threadfolio and Mizyun and install them on the iPhone without Adam's own login session. Written
2026-11-11 on this Mac: macOS 27.0.1, Xcode 27.2 (27B52), devicectl 651.32, MacBookPro18,4.
Nothing here was run by an agent. **Tier reached: source.**

Labels on each claim:

- **[verified]** checked read-only on this Mac on 2026-11-11, or in this repo.
- **[docs-only]** from Apple's, GitHub's or a man page's text, not tried here.
- **[inference]** reasoned, not documented or tried. Each one has a check in step 8.

Do every step in a Terminal attached to no agent. Passwords, keychain passwords and the phone
passcode are typed only into the prompt that asks for them.

## 0. Decisions before you start

ADR 0002 (issue 7, on `main`) proposes route 2: a Gateway plugin on the PC calls a runner on
this Mac over the tailnet, with no OpenClaw node. Its decisions D1 to D4 are yours and come
first; this runbook follows route 2. Two more are this runbook's:

| # | Decision | Options | Recommendation |
|---|---|---|---|
| ADR D3 | Which Apple team `jorah-build` signs with | Your personal team ("Adam Hikl"), or the company team ("itinn s.r.o.") | **The company team.** Both apps' own device scripts sign with it, and Mizyun's bundle IDs, capabilities and existing profiles all sit there [verified: issue 11's `docs/runbooks/ios-recipes.md`; profile `TeamName` on this Mac]. Using the personal team would mean new App IDs and capabilities there. One certificate, one team |
| S1 | Source access for the runner's clones | Read-only deploy key per repo, or a GitHub App token per run | **Token per run** (section 6) |
| S2 | When the runner may sign | Only while `jorah-build` is logged in (no stored secret), or a stored keychain password | **Logged in** (section 3.4) |

Both teams already have an Apple Development identity in your own keychain [verified:
`security find-identity -v -p codesigning` lists three valid identities, two on the personal
team, one on the company team]. Those stay yours. `jorah-build` gets its own (section 3).

## 1. Create the account and folders

```bash
cd ~/Documents/jorah && git pull --ff-only
```

```bash
scripts/mac/setup-jorah-build.sh --dry-run
```

**Expect** a list starting "This will:" with: create standard user `jorah-build`, add it to
`_developer`, create group `jorah-handoff`, add you to it, create `/usr/local/libexec/jorah`, set
up `/Users/Shared/jorah-handoff`. Two `note` lines: the transport unit is a placeholder, and
DevToolsSecurity is disabled. "Dry run: nothing changed." [verified: dry run on this Mac]

If it looks right:

```bash
sudo scripts/mac/setup-jorah-build.sh
```

1. sudo asks for **your** password.
2. Type `yes` at "Type yes to apply exactly this".
3. sysadminctl asks for the **new password for `jorah-build`**. Pick a new one and keep it in
   your password manager. It is that user's login and login-keychain password.

**Expect** "Result:" with `uid=…(jorah-build)` showing `_developer` among its groups,
`ok jorah-build is not an admin`, `/usr/local/libexec/jorah` as `root:wheel drwxr-xr-x`, and
`/Users/Shared/jorah-handoff` as `jorah-build jorah-handoff` with an ACL line
`group:jorah-handoff allow list,search,…`. Log out and back in once so Finder sees your new group.

The runner and its LaunchAgent come later, in section 5, once issue 8's `serve` is on `main`.
Until then the script refuses `--install-runner`.

What the script does not do: no autologin (it turns it off if it was set to `jorah-build`), no
admin rights, no keychain, certificate, pairing, power or security setting [verified: source].
`jorah-build` gets no Secure Token, so it cannot unlock FileVault [docs-only: `sysadminctl`
usage]. FileVault is on [verified: `fdesetup status`], so **after every restart the Mac waits
for you** at the FileVault screen before anything of Jorah's can run [inference].

The ACL was tried on a scratch folder with group `staff`: a run folder and file created inside
inherit read and delete for the group [verified]. On the real folder: [inference] until step 8.

## 2. First login as jorah-build

`jorah-build` needs one interactive login to get a home folder, a login keychain and Xcode's
first-run state.

1. Control Center → **Fast User Switching** (or the login window) → **Jorah build**, and type
   its password.
2. Skip Apple Account sign-in, Siri, Screen Time and every other setup offer. **Never sign in
   to an Apple Account or to Xcode → Settings → Accounts in this user.**
3. Open Terminal (as `jorah-build`) and run:

```bash
xcodebuild -version && xcrun devicectl list devices
```

**Expect** `Xcode 27.2` and a device table. The license and first-launch packages are
system-wide and already done in your account [inference]. If xcodebuild asks for the license,
quit and run `sudo xcodebuild -license accept` from **your** account (sudo is yours only).

## 3. Signing: a Development certificate only `jorah-build` holds

### 3.1 Why manual signing

`xcodebuild -allowProvisioningUpdates` (the switch automatic signing uses to create or renew
profiles and certificates) "Requires a developer account to have been added in Xcode's
Accounts preference pane", or an App Store Connect key via `-authenticationKeyPath`
[docs-only: `man xcodebuild`]. `jorah-build` has neither, by rule: no Apple Account and no App
Store Connect keys (`03-security-and-privacy.md` row for `jorah-build`). So:

- Automatic signing **cannot** create, renew or register anything in `jorah-build`
  [docs-only, same page].
- It may still sign when a matching profile and identity already sit in that user
  [inference, unproven].
- **Use manual signing:** you make the profiles in the developer website, and the recipe
  (issue 11) passes `CODE_SIGN_STYLE=Manual`, the team, `CODE_SIGN_IDENTITY="Apple Development"`
  and each target's profile name [inference]. A target with an extension (Mizyun's widget) needs
  one profile per bundle ID, so issue 11 sets them per target, not one global override.

### 3.2 Make the key inside jorah-build, so it never leaves

The private key is generated in `jorah-build`'s login keychain and is never exported. You and
any agent see only the certificate request (public) and the certificate (public).

In the **jorah-build** session:

1. Keychain Access → menu **Keychain Access → Certificate Assistant → Request a Certificate
   From a Certificate Authority…** [docs-only: Apple Developer help, "Create a certificate
   signing request"].
2. User email: any address of yours. Common name: `Jorah build`. CA email: empty.
   **Saved to disk.** Continue.
3. Save as `/Users/Shared/jorah-handoff/jorah-build.certSigningRequest`.

**Expect** a new private key named `Jorah build` under **login → Keys**.

In **your** session, in a browser:

4. developer.apple.com → Account → choose the company team (ADR D3) → Certificates → **+** →
   **Apple Development** → upload the `.certSigningRequest` → Download.
   **Never** choose Apple Distribution [rule: Development certificate only].
5. Copy the downloaded `.cer` to `/Users/Shared/` (the hand-off folder is read-only for you).
   A certificate is public; it is fine there for a minute.

Back in **jorah-build**:

6. Double-click the `.cer` in `/Users/Shared/`. Keychain: **login**. Then delete it from
   `/Users/Shared/`, and the request from the hand-off folder.
7. Terminal:

```bash
security find-identity -v -p codesigning
```

**Expect** exactly `1 valid identities found`. Apple names the certificate after the account
holder, so it reads `"Apple Development: <your name> (…)"`, not "Jorah build" [inference: your own identities are named that way]. It is
the right one because it is the only identity in this user, and Keychain Access shows the key
`Jorah build` under it. Note the certificate's expiry date: it is how you tell it apart from
yours in the developer website.

Repeat 1 to 7 for the personal team only if you chose it as well.

### 3.3 Let codesign use the key without a dialog

Still in **jorah-build**'s Terminal:

```bash
security set-key-partition-list -S apple-tool:,apple:,codesign: -s ~/Library/Keychains/login.keychain-db
```

It asks for the keychain password (the `jorah-build` password). **Expect** the key's attributes
printed, no error. "If you'd like to run /usr/bin/codesign with the key, 'apple:' must be an
element of the partition list" [docs-only: `man security`].

```bash
security set-keychain-settings ~/Library/Keychains/login.keychain-db && security show-keychain-info ~/Library/Keychains/login.keychain-db
```

**Expect** `no-timeout`. With no `-l` and no `-t` the keychain does not lock on sleep or on a
timer [docs-only: `man security`].

### 3.4 When is the key usable? (decision S2)

A login keychain is unlocked by logging in to that user. A build started outside
`jorah-build`'s login session (a LaunchDaemon, or SSH) would most likely find it locked, and
codesign would fail with an interaction-not-allowed error [inference]. Unlocking it there needs
its password at each run, which means a stored secret: a gate this runbook does not cross.

So the setup that needs no stored secret is: **you log in to `jorah-build` once after each
restart** (step 2's Fast User Switching), switch back to your account, and the runner runs as a
LaunchAgent inside that background login session [inference]. That is how
`scripts/mac/com.jorah.ios-runner.plist` is built: a root-owned agent that starts only for
`jorah-build`. A MacBook that sleeps but does not restart keeps the session. FileVault already
makes every restart wait for you (section 1). This is the first thing step 8 tests.

### 3.5 Profiles

In the developer website, company team, one profile per bundle ID the recipes sign
[verified: `docs/runbooks/ios-recipes.md`]:

| App | Bundle ID | Notes |
|---|---|---|
| Threadfolio dev | `com.threadfolio.dev` | |
| Mizyun dev | `com.mizyun.development` | HealthKit, Sign in with Apple, push, App Group |
| Mizyun dev widget | `com.mizyun.development.ExpoWidgetsTarget` | App Group |
| Mizyun dev watch | `com.mizyun.development.watchkitapp` | Pick the watchOS development type if the portal offers one for this App ID [inference] |

The App IDs and their capabilities already exist on that team [verified: Xcode-managed profiles
for the first two Mizyun IDs on this Mac; the others: inference]. A manual profile carries the
App ID's capabilities, so nothing changes there.

1. Profiles → **+** → **iOS App Development** → the App ID → only the certificate from 3.2 (the
   newest, by expiry date) →
   devices: your iPhone (and iPad if wanted) → name it `Jorah <bundle id>` → Generate → Download
   [docs-only: Apple Developer help, "Create a development provisioning profile"].
2. Copy the `.mobileprovision` files to `/Users/Shared/`, then in **jorah-build**:

```bash
mkdir -p ~/Library/Developer/Xcode/UserData/"Provisioning Profiles" && mv /Users/Shared/*.mobileprovision ~/Library/Developer/Xcode/UserData/"Provisioning Profiles"/
```

Xcode 27 reads profiles from that folder [verified: your seven current profiles live there and
`~/Library/MobileDevice/Provisioning Profiles` is empty]. A profile holds no private key.
Development profiles expire, about yearly, and must include every device you install to: a new
phone means regenerating them [docs-only].

## 4. The iPhone

Current state [verified, `xcrun devicectl list devices` in your account]: your iPhone is
`available (paired)`, transport `localNetwork`, Developer Mode `enabled`, iOS 27.0.1.

1. **Developer Mode** is set on the phone, not per Mac user, and stays on until you turn it off
   [docs-only: Apple, "Enabling Developer Mode on a device"]. Nothing to do.
2. **Pairing for jorah-build.** USB trust records live system-wide under `/var/db/lockdown`,
   owned by `_usbmuxd` [verified: listing], so `jorah-build` may already see the phone as
   paired [inference]. In **jorah-build**'s Terminal:

```bash
xcrun devicectl list devices
```

**Expect** your iPhone with `available (paired)`. If it says unpaired or is missing: unlock the
phone, plug it in by USB, then

```bash
xcrun devicectl manage pair --device <UDID from the list>
```

and tap **Trust** on the phone, then type the passcode **on the phone** [docs-only:
`devicectl manage pair --help`].

3. **USB versus network.** devicectl reaches the phone over the local network once paired
   [verified: transport `localNetwork` today]. That needs the Mac and phone on the same LAN.
   Over Tailscale it is not expected to work, because discovery is local [inference]. USB is the
   fallback and is what to use for pairing.
4. **Phone locked.** Install is expected to work on a locked but trusted phone; launching an app
   is expected to fail until you unlock it [inference, tested in step 8]. The runner should
   report that, not retry in a loop.
5. **Phone away.** The device shows unavailable. The runner leaves the IPA in
   `/Users/Shared/jorah-handoff/<run-id>` and reports "built, not installed" [inference about
   issue 8's behaviour].

`DevToolsSecurity` is disabled [verified]. Builds and installs are not expected to need it,
attaching a debugger is [inference]. The runner has no debug verb, so leave it off.

## 5. The runner service (ADR 0002, route 2)

Only after you answer the ADR's D1 to D4 with route 2 and the waiver accepted, and after issue
8's runner with its `serve` verb is on `main`.

1. **Install the runner and its agent.** In your account:

```bash
cd ~/Documents/jorah && git pull --ff-only && scripts/mac/setup-jorah-build.sh --dry-run --install-runner
```

   **Expect** the plan to add: copy the runner to `/usr/local/libexec/jorah/ios-runner`, install
   `ios-runner-agent`, install `/Library/LaunchAgents/com.jorah.ios-runner.plist`. Then the same
   with `sudo` and without `--dry-run`, and `yes`. The script refuses if the runner has no
   `serve` verb, rather than install an agent that would crash-loop [verified: source].
2. **The allowlist.** Issue 11's project entries, in the shape of the contract's section 6, go to
   `/Library/Application Support/Jorah/ios-projects.json`, owned by root, readable by all, which
   `jorah-build` cannot change. From your account, with the file prepared in the repo:
   `sudo install -o root -g wheel -m 0644 <file> "/Library/Application Support/Jorah/ios-projects.json"`.
   The wrapper points the runner at it with `JORAH_IOS_RUNNER_CONFIG` [verified: source of
   `scripts/mac/ios-runner-agent.sh` and the runner draft's `config_path()`].
3. **The shared key** (contract, "Key"). In a Terminal attached to no agent, logged in as
   `jorah-build`:

```bash
umask 077 && mkdir -p ~/.config/jorah-ios && openssl rand -out ~/.config/jorah-ios/runner.key 32 && shasum -a 256 ~/.config/jorah-ios/runner.key
```

   Note the hash (not secret). Then in **your** account, copy it to the PC without displaying it:

```bash
sudo cat /Users/jorah-build/.config/jorah-ios/runner.key | ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- sh -c "'umask 077 && mkdir -p ~/.config/jorah-ios && cat > ~/.config/jorah-ios/runner.key && sha256sum ~/.config/jorah-ios/runner.key'"
```

   **Expect** the same hash printed back [inference: the quoting through Windows OpenSSH and `wsl` is untested]. If it differs, the Windows hop changed the bytes
   [inference: possible on binary data]: delete the PC copy and ask a build session for another
   route. Never paste the key.
4. **Start it.** Log out of `jorah-build` and back in (Fast User Switching), then switch back.
   In `jorah-build`'s Terminal before switching: `curl -s http://127.0.0.1:47820/v1/health`.
   **Expect** `{"contract": "jorah-ios/1", …}` [contract; inference until issue 8 ships].
5. **Tailnet.** The ADR's steps 2 and 3: the grant, then
   `tailscale serve --bg --tcp=47820 tcp://127.0.0.1:47820` in your account.

Off switch, quickest first: `tailscale serve --tcp=47820 off`; log out of `jorah-build`;
`sudo rm /Library/LaunchAgents/com.jorah.ios-runner.plist`.

A note for issue 8: build scripts run third-party code as `jorah-build`, and that user can read
its own copy of the key. Such code could sign requests to the runner, which only does what the
allowlist already lets `jorah-build` do; the PC accepts no requests [inference]. Worth a line in
the runner's threat notes.

## 6. Source access for the runner's clones

Clones live under `jorah-build`'s home only (`03-security-and-privacy.md`).

| | Read-only deploy key, one per repo | GitHub App token, one per run |
|---|---|---|
| Scope | One repo per key, read-only by default [docs-only: GitHub, "Managing deploy keys"] | One repo, `contents: read`, chosen per request [verified: `plugins/jorah-github/github.js` `repoToken` takes a repo and a permission set] |
| Lifetime | Never expires [docs-only, same page] | One hour [verified: same file; docs-only: GitHub] |
| Where the secret lives | Private key file in `jorah-build`'s `~/.ssh`, on a laptop that travels daily | On the PC, where the App key already is; only a 1-hour token crosses to the Mac |
| If the Mac is lost | Read access to Mizyun and Threadfolio until you remove both keys | Nothing to revoke after an hour |
| Work needed | You make keys and add them in each repo's settings. Nothing in code | Issues 8 and 9: the plugin mints the token and sends it in the signed request body, git reads it from a helper, never the command line or a file. The `jorah-bot` App already covers all your repos [verified: issue 11's runbook, from `docs/evidence/github-rulesets/2026-11-10.md`] |
| GitHub's view | Keys usually lack a passphrase and never expire; GitHub suggests an App instead [docs-only] | The recommended route [docs-only] |

**Recommendation: token per run.** The laptop travels daily, and a never-expiring key on it is
the bigger risk. If issue 9 is late and you want a build sooner, deploy keys are the fallback:
make them in **jorah-build** (`ssh-keygen -t ed25519 -f ~/.ssh/mizyun_ro -N ''`, the same for
threadfolio), add each `.pub` in the repo's **Settings → Deploy keys** with **Allow write
access unticked**, and add removing them to the lost-laptop list.

## 7. Power: a MacBook that travels daily

Current settings [verified: `pmset -g custom`]:

| | On charger (AC) | On battery |
|---|---|---|
| `sleep` (system) | 0, never | 1 minute |
| `womp` (wake on Ethernet magic packet) | 1 | 0 |
| `tcpkeepalive` | 1 | 1 |
| `powernap` | 1 | 1 |

So on the charger with the lid **open**, the Mac does not sleep by itself today. **No `pmset`
change is proposed.** Battery settings stay as they are, so travel is unchanged.

- **Lid closed** sleeps the Mac unless it runs in closed-display mode: charger, external
  display, external keyboard or mouse [docs-only, from secondary sources quoting Apple's
  closed-display page; not rechecked]. A dummy display plug may stand in for the display
  [inference]. TOPO-B5 tests exactly this.
- **Waking from the PC.** `womp` wakes on an Ethernet magic packet [docs-only: `man pmset`], so
  only when docked on wired Ethernet [inference]. A sleeping Mac is not reachable over Tailscale
  [inference]. Jorah says "waiting for the Mac" when it is away or asleep
  (`10-roadmap.md` M19 row) [verified: roadmap].
- If you later want a wake test, `sudo pmset -c womp 1` is already in effect; nothing to run.

### TOPO-B5, the 24-hour dock test (your step)

From `research/topology.md`: "Dock test: closed lid, power, display or dummy. Node stays
connected 24 hours." Run it after step 5 exists, so there is a node to stay connected.

1. Dock: charger, display or dummy plug, keyboard or mouse, Ethernet if the dock has it.
2. Log in to `jorah-build` once (section 3.4), switch back to your account, close the lid.
3. Note the time. From the PC, every few hours, ask Jorah for the runner's device list (issue 9's
   tool), or use the reachability check that section 5 will name for the chosen transport.
4. After 24 hours, open the lid and run, in your account:

```bash
pmset -g log | grep -E " (Sleep|Wake|DarkWake) " | tail -50
```

**Pass:** every check from the PC answered, and no `Sleep` line in the 24 hours. Save the output
(it has no private data) to `docs/evidence/10/topo-b5.txt`.

## 8. First checks after setup (turns the inferences into results)

In order, in **jorah-build** unless noted. Record each as pass or fail in
`docs/evidence/10/setup-checks.md`.

1. `security find-identity -v -p codesigning` → one identity, the one from 3.2.
2. `xcrun devicectl list devices` → iPhone `available (paired)`.
3. A manual build with the recipe's manual signing settings into
   `/Users/Shared/jorah-handoff/test-1` → `** BUILD SUCCEEDED **`, no keychain dialog.
4. The same build through the runner's agent (section 5) while `jorah-build` is logged in →
   signs. Then log `jorah-build` out completely and try again → expected to be refused or fail
   cleanly, not hang [inference; this is what 3.4 predicts].
5. `xcrun devicectl device install app --device <UDID> <path>.app` with the phone **unlocked**,
   then **locked** → install result each time.
6. From **your** account: `ls -le /Users/Shared/jorah-handoff/test-1` → readable, ACL inherited;
   delete it → works.

## 9. Evidence to record

In `docs/evidence/10/`, private content removed: the setup script's "Result:" block, the
`find-identity` line for `jorah-build` (identity name only, no hashes needed), the device line
with the UDID cut, the step 8 results, and TOPO-B5's `pmset` log. Never the CSR, `.cer`,
`.mobileprovision` or any key.

## 10. Rollback

1. Pairing, only if you want it gone. A pairing made in step 4 as `jorah-build`: in that user,
   before step 2, `xcrun devicectl manage unpair --device <UDID>` ("Unpair a manually paired
   device") [docs-only: `devicectl manage --help`]. Your own pairing stays. To drop the phone's
   trust in every computer: iPhone **Settings → General → Transfer or Reset iPhone → Reset →
   Reset Location & Privacy**. Developer Mode can stay on.
2. Preview, then remove the account and folders:

```bash
scripts/mac/remove-jorah-build.sh --dry-run
```

```bash
sudo scripts/mac/remove-jorah-build.sh
```

   **Expect** "This will:" listing the runner agent (if installed), the user and its home,
   `/usr/local/libexec/jorah`, `/Library/Application Support/Jorah`, the hand-off folder (with
   its run count) and the group, then `yes`, then `ok … is gone` five times. Add `--keep-handoff` to keep built IPAs.
3. developer.apple.com, each team used: Certificates → the Apple Development certificate with
   the expiry date you noted in 3.2 → **Revoke**. Your own certificates stay. Profiles →
   delete the `Jorah …` profiles.
4. Each repo's **Settings → Deploy keys**: delete any `jorah-build` key (only if S1 chose keys).
5. Tailnet: `tailscale serve --tcp=47820 off` in your account, and remove the ADR's grant in the
   Tailscale admin console.
6. On the PC as `jorah`: `rm ~/.config/jorah-ios/runner.key`.

## Open, after this runbook

- Your answers to ADR 0002's D1 to D4, and to S1 and S2 here.
- Runner `serve` (HTTP and HMAC front end) and the allowlist path: issue 8, then section 5.
- Manual signing per target: issues 8 and 11. Both repos' own scripts pass
  `-allowProvisioningUpdates CODE_SIGN_STYLE=Automatic`, which cannot work in `jorah-build`
  (section 3.1); the runner must pass manual settings per target instead.
- Token handover for clones: issues 8 and 9, if S1 is "token".
- Every [inference] above: step 8 and TOPO-B5.
