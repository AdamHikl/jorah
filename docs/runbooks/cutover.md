# Cutover: Jorah moves from the Mac to the PC

Steps 3 and 4 of `docs/runbooks/jorah-on-pc.md`. Jorah's state leaves the Mac in one verified archive and starts once on the PC. **Never two Gateways:** the Mac's Gateway is stopped and checked before the backup, and the Telegram token is rotated, so a Mac that starts by mistake can't answer.

Marked [rehearsed] means it ran on the PC on 2026-11-06 with a backup of the scratch profile `jorah-dev`, not the real one. Everything else is unverified, so stop and report if a step behaves differently. Steps marked **Adam** go in a Terminal attached to no agent, because they handle a secret or a sign-in.

The Mac's state isn't changed by any step here. That's what makes rollback simple.

On the PC, Jorah gets shell and web inside the sandbox, by Adam's waived gate of 2026-11-06 (`docs/runbooks/jorah-on-pc.md`). The Mac's stage 0 is unchanged.

## Progress, 2026-11-06

Done by Claude, without a secret or a sign-in:

- **Step 1:** no OpenClaw process, listener or launchd job on the Mac, at 13:05.
- **B5, B6:** nothing listens on 43180-43199 on the PC, `jorah-dev` stopped. Both sides run `OpenClaw 2026.10.9 (8b18b55)`.
- **Record:** `commands.ownerAllowFrom` holds one `telegram:` id (10 digits), kept outside the repo. `gateway.port` and `session.dmScope` are unset on the Mac, so it ran the defaults, 18789 and `main`. The cron list couldn't be read, because it needs a running Gateway. The backup dry run listed the expected `state` and `workspace` assets only.
- **Step 3:** `~/Backups/jorah-cutover/2026-11-06T13-06-26.124+01-00-openclaw-backup.tar.gz`, 310 MB, `Archive verification: passed`, sha256 `5978eed4e51d7df1697556847dad855735958866759acfb4ecbe9f6352494e32`.
- **Step 4:** the same hash on the PC, 38 s.
- **Step 5:** 2 assets and 206 entries verified, no symlinks, nothing owned by anyone but `jorah`. The rehearsal's leftover folders were moved to `/home/jorah/rehearsal-2026-11-06`, not deleted.
- **Step 6:** state and workspace in place, all owned by `jorah`. Seven Mac paths left in the config, in `agents.defaults.workspace`, `agents.entries.main.workspace`, `agents.entries.main.agentDir`, `plugins.entries.acpx.config.cwd`, `env.vars.CLAUDE_CONFIG_DIR` and two in `models.providers.llama-cpp`. A copy of the restored config is at `openclaw.json.restored`.
- **Step 7:** warnings only, and `doctor --non-interactive` left the config unchanged (same hash). The acpx and llama.cpp plugins miss their `node_modules`, as expected, and the old Telegram token is still plaintext in the config until step 9.
- **Step 9 rehearsed on a copy of the real state** (`~/.openclaw-jorah-cutrehearse`, placeholder secrets, no Gateway started). Two findings the `jorah-dev` rehearsal couldn't show:
  - The patch missed `agents.entries.main.agentDir`. Moving it is refused while `main`'s auth inheritance is implicit, so the patch now sets `agentDir` and `agents.defaults.authInheritance: { agentId: "main" }`.
  - `plugins.entries.acpx.config` can't be edited until acpx is reinstalled, so **step 8's plugin installs must come before step 9**. The rest of the patch, without the acpx line, gave `Dry run successful: 69 update(s)`, applied, `Config valid` with plugin warnings only, a clean secrets audit, and one Mac path left, acpx's `cwd`.

**The Mac's state is frozen at the 13:06 backup.** Don't start the Mac Gateway or edit the Mac workspace before the window. If either changes, redo steps 3-7 after moving the PC copies aside.

The old Telegram token sits in plaintext in `/home/jorah/.openclaw-jorah/openclaw.json` and the rehearsal copy until step 2 kills it. Both are mode 700 under `jorah`, out of the sandbox's reach.

## Adam's steps, in order

Everything else is prepared, and B4, B7, B8, B9 and B10 are done. These need Adam, in this order. Steps 3, 4 and 6 go in a Terminal attached to no agent.

1. **Before the window: say yes to B1 and B2.** B1 is step 2's boot service, which is still open. B2 is pushing this branch to `main` and copying `config/pc` and `deploy` to the PC. Expected: `ls /opt/jorah/config/pc/stage0.patch.json5` works on the PC.
2. **Before the window: say yes to the two plugin installs in step 8,** `acpx` and `duckduckgo`, both pinned to 2026.10.9.
3. **Window, step 2: rotate the Telegram token** at BotFather (`/revoke`, then pick Jorah's bot). Expected: BotFather replies with a new token. Keep it in the password manager, never in a chat or file.
4. **Window, step 8: store the two secrets** in the `jorah` shell. Expected: `Stored OPENCLAW_GATEWAY_TOKEN (secret).` and `Stored TELEGRAM_BOT_TOKEN (secret).`, then `secrets store list` shows both as `[secret] (write-only)`, with no token on screen.
5. **Window, step 9: say yes to the patch** after its dry run. Expected: `Dry run successful: N update(s) validated`, N around 68, then `Config valid` and `0` Mac paths.
6. **Window, step 10: sign in to Claude** in the same shell. Expected: both logins finish without an error. If any setup prompt offers a llama.cpp chat model, answer **No**.
7. **Window, step 11, after the start: write the voice token file,** `/home/jorah/.config/jorah-voice/gateway-token`, mode 600. Expected: `ls -l` shows `-rw-------` owned by `jorah`, and the file isn't empty.
8. **Window, step 11: in Telegram, send `Hello`,** then ask for a fact saved on the Mac. Expected: a reply within a minute, and the fact. Recall is keyword-only on the PC, so ask with words the fact contains.

## Before the window

Each needs Adam's yes. The window doesn't start until all are done.

| # | What | Why |
|---|---|---|
| B1 | Step 2 works: the Gateway service starts at boot with nobody signed in | Without it Jorah stops when the PC's last session ends. The unit is `deploy/openclaw-gateway.service`, which passes `systemd-analyze verify` on the PC [measured, 2026-11-06]. On the yes it's copied to `/etc/systemd/system` and loaded, not enabled. Step 11 starts it and enables it once the checks pass. The reboot with nobody signed in stays untested |
| B2 | `config/pc/` is on `main` and copied to `/opt/jorah` (command below) | The patch is read from there, root-owned |
| B3 | `acpx` and `duckduckgo` installed in step 8, pinned to 2026.10.9 | External plugins, not in the PC's install [measured]. The Mac's `extensions` folder (648 MB) holds macOS-native parts, and plugin `node_modules` aren't in backups. `duckduckgo` 2026.10.9 was published 2026-10-29, so it meets the 7-day rule. `llama-cpp` isn't used on the PC (B7) |
| B4 | Service hardening and linger | **Done 2026-11-06, on Adam's yes.** Step 11's unit blocks `/run/WSL` and vsock [measured], and step 2's service must carry the same two lines. `loginctl enable-linger jorah` is on, so rootless Podman uses systemd cgroups under a unit [measured] |
| B5 | Nothing listens on 43181 on the PC, and `jorah-dev` is stopped | One Gateway at a time on this distro too |
| B6 | The Mac and PC run the same OpenClaw version | Restore onto another version needs `database preflight` first |
| B7 | Memory search | **Adam chose keyword-only, 2026-11-06.** The patch sets `memory.search.provider: "none"` and removes the Mac's llama.cpp entry. Why: llama.cpp starts each model's server on a random loopback port, which the firewall refuses [measured]. Keyword search found the rehearsal fact [measured]. The later fix is NAT networking with Tailscale inside the distro, so loopback is the distro's own. Not now |
| B8 | Web search | **Adam chose DuckDuckGo, no account, 2026-11-06.** It returned 5 results on `jorah-dev`, wrapped as untrusted content [measured]. Unofficial, it scrapes HTML, so it can break |
| B9 | Browser private network | **Adam chose relaxed, 2026-11-06,** firewall unchanged. Hostnames open and the LAN is still refused [measured]. Web pages can reach Jorah's own loopback ports, 43181-43199 and 43210, which are token-protected, except the Gateway's `/health` [measured]. The security audit warns about this flag on purpose |
| B10 | Podman, the sandbox image and Chrome are on the PC | Done 2026-11-06 [measured]. `deploy/openclaw-sandbox.Containerfile` rebuilds the image with the same ID |

Helper on the Mac, in zsh:

```bash
pc() { ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes -o BatchMode=yes adamh@100.115.240.14 "$@"; }
```

B2, after `config/pc/` is on `main`:

```bash
git -C ~/Documents/jorah archive HEAD config/pc | pc "wsl -d jorah -u root -- tar -x -C /opt/jorah"
```

B5 and B6:

```bash
openclaw --version; pc "wsl -d jorah -u jorah -- openclaw --version"
```

Expected: both `OpenClaw 2026.10.9 (8b18b55)`, or the same newer version.

```bash
echo 'ss -ltnH | grep -E ":4318[0-9]|:4319[0-9]" || echo "nothing listening"' | pc "wsl -d jorah -u root -- bash -s"
```

Expected: `nothing listening`.

**Record on the Mac, read only.** These read config and change nothing. Keep the output, because step 11 compares against it:

```bash
openclaw --profile jorah config get commands.ownerAllowFrom
openclaw --profile jorah config get gateway.port
openclaw --profile jorah plugins list | grep -E "acpx|llama"
openclaw --profile jorah cron list --all
openclaw --profile jorah backup create --dry-run --json
```

The dry run lists the assets the archive will hold. Expected: a `state` asset at `/Users/adam/.openclaw-jorah` and a `workspace` asset at `/Users/adam/Documents/jorah/workspace`. If there are others, stop: each needs its own mapping in step 6.

## The window

### 1. Confirm the Mac Gateway is down

It has been down since its last log line, 2026-11-05 21:56: PID 46941 is gone and nothing listens on 43181 (another session's read-only check, 2026-11-06). Nobody starts it again before the cutover. If it's running after all, press Ctrl-C in its Terminal. Then check:

```bash
pgrep -fl openclaw || echo "no openclaw process"
lsof -nP -iTCP -sTCP:LISTEN | grep -E ":43181|:18789|openclaw" || echo "no listener"
launchctl list | grep -i openclaw || echo "no launchd job"
```

Expected: all three print their `no` line. Don't use a PID from earlier notes: PID 46941 wasn't running on 2026-11-06.

### 2. Adam: rotate the Telegram token

At BotFather, `/revoke` for Jorah's bot, then copy the new token into the password manager. Not into a chat, file or agent terminal. From now on the Mac's copy is dead, so a Mac Gateway started by mistake can't reach Telegram.

### 3. Back up on the Mac

```bash
mkdir -p ~/Backups/jorah-cutover && chmod 700 ~/Backups/jorah-cutover
openclaw --profile jorah backup create --output ~/Backups/jorah-cutover --verify
A="$(ls -t ~/Backups/jorah-cutover/*.tar.gz | head -1)"; echo "$A"; shasum -a 256 "$A"
```

Expected: `Archive verification: passed`. Note the hash. The archive holds credentials and the old token, so it stays in that folder for the two-week rollback period.

### 4. Copy it to the PC without opening it [rehearsed]

```bash
pc 'wsl -d jorah -u jorah -- bash -c "umask 077; mkdir -p /home/jorah/incoming && cat > /home/jorah/incoming/cutover.tar.gz && sha256sum /home/jorah/incoming/cutover.tar.gz"' < "$A"
```

Expected: the same hash as step 3. Rehearsed with a 64 MB random file: the bytes arrived unchanged in 8 seconds over SSH to Windows and `wsl` stdin.

### 5. Restore to staging [rehearsed]

It runs under `jorah-dev`, so that verify and restore record their attempts there and nothing creates `~/.openclaw-jorah` early.

```bash
pc "wsl -d jorah -u jorah -- bash -s" <<'EOF'
set -eu
oc() { openclaw --profile jorah-dev "$@"; }
for d in /home/jorah/.openclaw-jorah /home/jorah/workspace /home/jorah/restore-staging; do
  if [ -e "$d" ]; then echo "$d exists, stopping"; exit 3; fi
done
oc backup verify /home/jorah/incoming/cutover.tar.gz
oc backup restore /home/jorah/incoming/cutover.tar.gz --target /home/jorah/restore-staging
M=$(find /home/jorah/restore-staging -maxdepth 2 -name manifest.json)
python3 -I -c 'import json,sys; m=json.load(open(sys.argv[1])); print(m["paths"]); [print(a["kind"], a["sourcePath"]) for a in m["assets"]]' "$M"
find /home/jorah/restore-staging -type l -printf '%p -> %l\n'
find /home/jorah/restore-staging ! -user jorah | head -3
EOF
```

Expected: `Archive verification` passes, the assets match the dry run, and both `find`s print nothing. A symlink must be checked by hand before going on, because absolute links keep their Mac targets.

### 6. Move state and workspace to the PC paths [rehearsed]

| Mac | PC |
|---|---|
| `/Users/adam/.openclaw-jorah` | `/home/jorah/.openclaw-jorah` |
| `/Users/adam/Documents/jorah/workspace` | `/home/jorah/workspace` |
| `/Users/adam/Documents/jorah/sandbox` (acpx `cwd`, not in the archive) | `/home/jorah/work`, new and empty |
| `/Users/adam/.claude-jorah` (not in the archive) | `/home/jorah/.claude-jorah`, already made by the setup script |

```bash
pc "wsl -d jorah -u jorah -- bash -s" <<'EOF'
set -eu
P=$(find /home/jorah/restore-staging -mindepth 3 -maxdepth 3 -type d -path '*/payload/posix')/Users/adam
for d in /home/jorah/.openclaw-jorah /home/jorah/workspace; do
  if [ -e "$d" ]; then echo "$d exists, stopping"; exit 3; fi
done
mv "$P/.openclaw-jorah" /home/jorah/.openclaw-jorah
mv "$P/Documents/jorah/workspace" /home/jorah/workspace
mkdir -p /home/jorah/work
chmod 700 /home/jorah/.openclaw-jorah /home/jorah/workspace /home/jorah/work
find /home/jorah/.openclaw-jorah /home/jorah/workspace ! -user jorah | head -3
grep -o -E '"/Users/[^"]*"' /home/jorah/.openclaw-jorah/openclaw.json | sort | uniq -c
EOF
```

Expected: no file owned by anyone but `jorah`, which held in the rehearsal because `jorah` ran the restore. If one shows up, fix it as root with `chown -R jorah:jorah` on that folder. The `grep` lists the Mac paths still in the config: paths only, no values. Step 9's patch replaces every one it knows. Any path it doesn't know needs its own line in the patch copy.

### 7. Doctor [rehearsed]

```bash
pc "wsl -d jorah -u jorah -- openclaw --profile jorah doctor --lint"
pc "wsl -d jorah -u jorah -- openclaw --profile jorah doctor --non-interactive"
```

Expected: `Doctor complete.` and warnings, no errors. Rehearsal warnings were the default model's Codex route, the heartbeat monitor, and loopback-only node hosting. A warning about an unreadable Keychain resolver means the Mac had stage 0. Step 9 removes it.

### 8. Adam: secrets into the store, and plugins

Open an interactive shell as `jorah`, in a Terminal attached to no agent:

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah
```

Inside it:

```bash
head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n' | openclaw --profile jorah secrets store set OPENCLAW_GATEWAY_TOKEN --kind secret --value-file -
read -rs -p 'New Telegram token: ' T; echo; printf '%s' "$T" | openclaw --profile jorah secrets store set TELEGRAM_BOT_TOKEN --kind secret --value-file -; unset T
openclaw --profile jorah secrets store list
```

Expected: `Stored OPENCLAW_GATEWAY_TOKEN (secret).`, then the same for `TELEGRAM_BOT_TOKEN`, and the list shows both as `[secret] (write-only)`. Nothing echoes the token. The Gateway token is new on purpose: the Mac's one doesn't move.

Then, on the yes from B3, the two plugins, pinned. `--force` replaces the restored macOS copy of `acpx`:

```bash
openclaw --profile jorah plugins install @openclaw/acpx@2026.10.9 --pin --force
openclaw --profile jorah plugins install @openclaw/duckduckgo-plugin@2026.10.9 --pin
```

Expected: `Installed plugin: acpx` and `Installed plugin: duckduckgo` [the second rehearsed on `jorah-dev`]. The install lands in `jorah`'s own state, which `jorah` can write.

**llama.cpp isn't used on the PC** (B7). The patch removes `models.providers.llama-cpp`, the Mac's entry for a `darwin-arm64` build on port 58378. The restored `~/.openclaw-jorah/tools/llama.cpp` and `models` folders stay on disk, unused, for the later fix.

### 9. Stage 0 for the PC [rehearsed on `jorah-dev`]

Fill Adam's id from the record before the window, in a copy outside the repo. Then dry run:

```bash
pc "wsl -d jorah -u jorah -- bash -s" <<'EOF'
set -eu
T=$(mktemp -d); chmod 700 "$T"
sed 's/<Adam.s numeric id>/REPLACE_WITH_ID/' /opt/jorah/config/pc/stage0.patch.json5 > "$T/pc.json5"
grep -c REPLACE_WITH_ID "$T/pc.json5" && { echo "fill the id first"; exit 3; }
openclaw --profile jorah config patch --file "$T/pc.json5" --dry-run
echo "$T"
EOF
```

Replace `REPLACE_WITH_ID` in the command with the number, so the `grep` check passes. Expected: `Dry run successful: N update(s) validated`. N was 68 in the rehearsal with the final patch. If a store entry is missing, the dry run says `Secret store entry "..." was not found` and step 8 is redone [rehearsed]. Show Adam the dry run. On Adam's yes, apply the same file:

```bash
pc "wsl -d jorah -u jorah -- openclaw --profile jorah config patch --file <folder from above>/pc.json5"
pc "wsl -d jorah -u jorah -- openclaw --profile jorah config validate"
pc "wsl -d jorah -u jorah -- bash -c 'grep -c /Users/ /home/jorah/.openclaw-jorah/openclaw.json'"
```

Expected: `Config valid`, with warnings only for plugins not yet installed, and `0` Mac paths. A count above 0 means a Mac path the patch doesn't know: stop and add it to the patch copy. Delete the temp folder afterwards.

### 10. Adam: sign in to Claude

In the same `jorah` shell as step 8:

```bash
CLAUDE_CONFIG_DIR=/home/jorah/.claude-jorah claude auth login
CLAUDE_CONFIG_DIR=/home/jorah/.claude-jorah openclaw --profile jorah models auth login --provider anthropic --method cli --set-default
```

The restored auth profile points at the Mac's Claude login, which didn't move. This replaces it.

### 11. Start, once

Only after step 1's checks still hold on the Mac. If B1 installed `deploy/openclaw-gateway.service`, start that instead of the transient unit below. It has the same settings, plus `Requires=nftables.service` so Jorah doesn't start without the firewall: `systemctl start openclaw-gateway`, and `systemctl enable openclaw-gateway` only after the checks below pass. Otherwise a transient unit, gone at reboot. The two hardening lines are B4's: they stop Jorah reaching the WSL interop socket and opening vsock connections. The Gateway ran healthy with them [measured, without channels or a model turn].

```bash
pc "wsl -d jorah -u root -- bash -s" <<'EOF'
ss -ltnH | grep -E ":4318[0-9]|:4319[0-9]" && { echo "something is listening, stopping"; exit 3; }
systemd-run --unit=jorah-gateway --uid=jorah --gid=jorah -p WorkingDirectory=/home/jorah \
  -p InaccessiblePaths=/run/WSL -p "RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6 AF_NETLINK" \
  -E HOME=/home/jorah -E XDG_RUNTIME_DIR=/run/user/1000 -E PATH=/home/jorah/.local/bin:/usr/local/bin:/usr/bin:/bin \
  -E CLAUDE_CONFIG_DIR=/home/jorah/.claude-jorah -E ACPX_CLAUDE_INCLUDE_USER_SETTINGS=1 \
  /usr/local/bin/openclaw --profile jorah gateway run
sleep 30; systemctl is-active jorah-gateway; ss -ltnH | grep 43181
EOF
```

Expected: `active`, and listeners on `127.0.0.1:43181` and `[::1]:43181` only [rehearsed on 43190 and 43186]. `XDG_RUNTIME_DIR` is for rootless Podman. Without a user session for `jorah` it falls back to plain cgroups and still works [measured]; `loginctl enable-linger jorah` would fix that, on a yes.

Then check:

```bash
pc "wsl -d jorah -u jorah -- openclaw --profile jorah gateway status --require-rpc"
pc "wsl -d jorah -u jorah -- openclaw --profile jorah health --json"
pc "wsl -d jorah -u jorah -- openclaw --profile jorah secrets audit --check"
pc "wsl -d jorah -u jorah -- openclaw --profile jorah security audit"
pc "wsl -d jorah -u jorah -- openclaw --profile jorah cron list --all"
echo 'nft list chain inet jorah_out output | grep counter' | pc "wsl -d jorah -u root -- bash -s"
```

Expected [rehearsed]: `Read check: ok`, `"ok": true` with `telegram` among the channels, `Secrets audit: clean. plaintext=0`, `0 critical` with one warning, `gateway.trusted_proxies_missing`. The cron list has a new `Heartbeat (main)` and `Memory Dreaming`. The Mac's heartbeat ran hourly on Haiku, so check the new one shows `every 1h` and the same model. **Jobs don't carry over:** they're keyed by the old cron path, so the new Gateway makes fresh managed jobs and leaves the old ones unused [rehearsed]. Compare with the Mac's list and recreate any other job by hand, each on Adam's yes. Reject counters may rise only for traffic Jorah shouldn't send, so note any rise.

Then the sandbox and browser:

```bash
pc "wsl -d jorah -u jorah -- openclaw --profile jorah sandbox explain"
pc "wsl -d jorah -u jorah -- openclaw --profile jorah browser start"
```

Expected [rehearsed]: `runtime: sandboxed`, `mode: all`, `backend: podman`, and `running: true (headless)`. The first shell command through OpenClaw itself is untested: ask Jorah in Telegram to run `id; ls /home`. Expected: `uid=1000(sandbox)` and only `sandbox` in `/home`. If Jorah runs it as `jorah`, or sees `/home/jorah`, stop the Gateway: the sandbox isn't in force.

**Voice.** `jorah-voice` reaches the Gateway's `/v1/chat/completions` on loopback with the Gateway token [rehearsed: 401 without it]. That token is a full operator credential for this Gateway, not a narrow key. Adam puts it in place, in the `jorah` shell from step 8:

```bash
umask 077; openclaw --profile jorah gateway auth-token --show > /home/jorah/.config/jorah-voice/gateway-token
chmod 600 /home/jorah/.config/jorah-voice/gateway-token
```

`--show` prints only to an interactive terminal, so this is Adam's step. Unverified: whether it writes to a redirect. If the file ends up empty, put the token in with an editor instead. The sandbox can't see `/home/jorah`, so Jorah's shell can't read it [measured with a container on the same settings].

In Telegram, Adam sends `Hello`. Expected: a reply. Then ask for a fact saved on the Mac. Expected: Jorah recalls it. `session.dmScope: "main"` puts Telegram DMs and voice in one conversation, `agent:main:main`. Check it:

```bash
pc "wsl -d jorah -u jorah -- openclaw --profile jorah sessions --json"
```

Expected: the Telegram DM shows up as `agent:main:main`, with no `telegram:direct` session for Adam. After voice is on (step 11), say something, then ask in Telegram what you just said. Expected: Jorah knows.

### 12. Clean up

- Remove `/home/jorah/restore-staging` once Jorah answers. It's emptied by step 6 except for the manifest.
- Keep the archive on the Mac and in `/home/jorah/incoming` for two weeks, then Adam deletes both.
- `openclaw.json.bak*` and `openclaw.json.last-good` on the PC hold the old config, including the revoked token if it was plaintext. Adam deletes them after the two weeks.

## Rollback

The Mac's state never changed, so going back means stopping the PC and starting the Mac. Anything Jorah learned on the PC is lost unless it's copied by hand.

1. **Stop the PC Gateway:**

   ```bash
   echo 'systemctl stop jorah-gateway; sleep 3; systemctl is-active jorah-gateway; ss -ltnH | grep 43181 || echo "no listener"' | pc "wsl -d jorah -u root -- bash -s"
   ```

   Expected: `inactive` or `failed`, then `no listener`. Telegram allows one poller per token, so the PC must be stopped first.
2. **Telegram token.** If step 2 ran, the Mac holds a dead token. Enter the new one at the masked prompt on the Mac, as in `docs/runbooks/stage0-rollback.md` step 5:

   ```bash
   openclaw --profile jorah configure
   ```

3. **Start the Mac Gateway in the foreground** with the command in `README.md`.
4. **Check:** Telegram replies to `Hello`.
5. **Leave the PC's state stopped** for diagnosis, and record what failed in `docs/evidence/`, without secrets.

## Rehearsal, 2026-11-06

On the PC as `jorah`, with the firewall loaded. Profile `jorah-dev`, port 43190, channels skipped, test tokens made on the PC and never printed. The real profile, the Mac and Windows weren't touched.

| Check | Result |
|---|---|
| Trial Gateway, minimal config | Listens on `127.0.0.1:43190` and `[::1]:43190` only. No derived ports, no firewall rejects |
| CLI through the firewall | `gateway status --require-rpc` ok, `health` ok, `security audit` 0 critical, unauthenticated `POST /tools/invoke` returns 401 |
| `tailscale.mode: "serve"` | The Gateway refuses to start: `spawn tailscale ENOENT`. Fails closed |
| PC stage 0 patch | Dry run refuses while a store entry is missing. With both present: 42 updates. The real file dry-runs without creating `~/.openclaw-jorah` |
| Booted with PC stage 0 | 5 plugins load, per the allowlist. `secrets audit` clean, plaintext 0. Tokens resolve from the store. Log in the profile's own folder |
| Backup | `--verify` passes. 2 assets, state and workspace, 23 entries |
| Restore | To a fresh folder, all owned by `jorah`, no symlinks. Then moved to other paths as profile `jorah-rehearse` |
| After the move | Path patch applies, doctor completes, store entries survive, canary and saved fact present, Gateway boots and opens no file at the old paths. Cron jobs don't carry over |
| Transfer | 64 MB, same SHA-256, 8 s |
| Shell and web patch | Dry run 65 updates. Boots under the hardened unit. `sandbox explain`: sandboxed, all, podman. With the sandbox off, `exec` doesn't run on the host |
| Sandbox container, patch settings | uid 1000, no host home, no `/run/WSL`, read-only root, workspace writable. Internet yes; LAN, router, tailnet, host loopback, WSL DNS on port 80 no, and the firewall counts them |
| Browser | Headless Chrome, its own sandbox on, CDP on 43191. Strict policy refuses hostnames; private-network mode reaches loopback 43181-43199 and 43210 |
| Chat Completions | 401 without the token, reaches the agent with it |
| llama.cpp | Plugin installs, Linux build fetched, router port pins. Per-model ports are random and refused by the firewall, so embeddings fail. The chat model downloaded by mistake was deleted |
| Final patch | Dry run 68 updates. 7 plugins load. Sandbox `podman`, systemd cgroups. DuckDuckGo 5 results. Browser opens hostnames, LAN refused. Keyword memory search finds the fact. Audit 0 critical, 3 expected warnings: trusted proxies, the browser flag, exec `full` inside the sandbox |

The backup skips the managed `tmp` folder as regenerable [measured], so the Mac's 295 MB there doesn't travel.

**Not rehearsed:** Telegram, a model turn, a shell command, browser action or `web_fetch` started by OpenClaw itself, a Claude sign-in, the `acpx` install, working local embeddings, an archive from macOS, the hardened unit with a signed-in Claude, rollback on the Mac.

## Afterwards

- **Remote clients (step 7).** OpenClaw's own Serve can't run in this distro. A Serve route owned by Windows Tailscale to `http://127.0.0.1:43181` should work, with `gateway.trustedProxies: ["127.0.0.1"]` and token auth kept, per OpenClaw's "Externally managed Serve" docs. That's a Windows change, so it needs its own yes. Unverified: the source address Windows' proxy shows inside the distro.
- **Delegated coding.** Claude Code in the distro refuses to start with `failIfUnavailable`, because `socat` is missing [measured]. Installing `socat`, and adapting `scripts/setup-permissions.sh` for Linux paths, needs a yes.
- **Semantic memory search, later:** NAT networking with Tailscale inside the distro, so loopback belongs to the distro and llama.cpp's random ports work. Not now (B7).
- **Ports in use:** Gateway 43181, derived 43182-43183, Chrome's CDP 43190, speech 43210. `jorah-dev` tests used 43186-43188 and 43191. Chrome's default CDP port, 18800, is refused by the firewall, so the patch sets 43190.
