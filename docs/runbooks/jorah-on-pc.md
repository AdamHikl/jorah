# Jorah on the PC

One agent, one sandbox, one system: Jorah runs in the `jorah` WSL distro on the PC and keeps working with the Mac closed. Telegram, the iPhone and the Mac's mic are only ways to talk to it.

Steps marked [measured] ran on the PC on 2026-11-05 or 2026-11-06. The rest haven't run yet, so stop and report if one behaves differently. Commands with a secret or a sign-in go in a terminal attached to no agent.

## Where it stands

| Step | What | State |
|---|---|---|
| 1 | Distro, user, Node, OpenClaw, firewall, speech models | Done [measured]. No Gateway started |
| 2 | Starts at boot with nobody signed in | Set up [measured]: Tailscale unattended on, Windows task "Jorah WSL" (`adamh`, S4U, `wsl.exe -d jorah --exec /bin/sleep infinity`) keeps the distro up. `openclaw-gateway.service` is **enabled** since 2026-11-06 15:09, so a distro restart brings Jorah back. **Found 2026-11-06:** the task's keep-alive ended at 08:51 (result 1) when the distro was restarted, and a startup trigger never reruns, so the distro stopped whenever no SSH session held it (5 restarts that afternoon, the Gateway with it). Fixed on Adam's yes: a second trigger repeats every 5 minutes, indefinitely, with `IgnoreNew`, so a dead keep-alive returns within 5 minutes [measured: task `Running`, boot and 5-minute triggers]. Undo: `Set-ScheduledTask -TaskName "Jorah WSL" -Trigger $t.Triggers[0]`. Reboot with nobody signed in not tested |
| 3 | Stage 0 settings for the PC, secrets store, new Telegram token | **Applied to Jorah 2026-11-06** [measured]: token rotated, both tokens in the store, `config/pc/stage0.patch.json5` applied with Dreaming back on, 0 Mac paths, secrets audit clean. Memory search is keyword-only, by Adam's choice |
| 4 | Move: stop the Mac Gateway, back up, restore here, sign in. **Never two Gateways** | **Done 2026-11-06** [measured]: Mac Gateway down, Claude signed in as Jorah (Max), Gateway on 127.0.0.1/[::1]:43181, health ok, 0 critical, `Heartbeat (main)` hourly on Haiku and `Memory Dreaming` at 03:00. Telegram answered `Hello` at 15:10 on Opus in `agent:main:main`. Recall of a Mac fact and the sandboxed shell through Telegram: see `docs/evidence/p2-cutover/` |
| 5 | Proof: Mac closed, PC rebooted, Telegram answers and recalls a saved fact | Not run |
| 6 | Speech feeds Jorah's main session through the Gateway's Chat Completions endpoint | **Running since 2026-11-06 15:56** [measured]: files in `/opt/jorah` match `main` (lockfile unchanged, so no `uv sync`), `jorah-voice.service` **enabled** and active, models loaded in 13 s, listening on `127.0.0.1:43210` only, and Windows reaches that port. Earlier, end to end with a stand-in Gateway and the service's sandbox settings [measured]: heard correctly, reply streamed and spoken, recognition on the CPU (Parakeet v3), speech on the GPU (Kokoro fp32). End of turn: 0.65 s after a finished sentence, 1.2 s after an open word, synthetic speech only (`docs/evidence/voice-endpointing/`). Not run against the real Gateway: Adam's test, see "Voice from the Mac". Undo: `systemctl disable --now jorah-voice` as root |
| 7 | Pair the iPhone and the Mac as clients | **Mac voice:** `mac-ear` built [measured, stand-in tests pass]. Windows Tailscale Serve route `https://rocket.tail1574a5.ts.net:43210` → `http://127.0.0.1:43210` **not up yet**: Serve isn't enabled on the tailnet, which needs Adam's admin consent. Steps in "Voice from the Mac". iPhone and Gateway route: not run |

## Waived gate, 2026-11-06

**Measured at the cutover:** with the `claude-cli` runtime (Jorah's Max login), OpenClaw's Podman sandbox doesn't apply, so `exec` refuses and Jorah has no shell. Files, memory and web work. Shell needs the embedded runtime or a paired node (`docs/evidence/p2-cutover/`).

Adam waived decision 3 (stage 0: no shell, web, browser or cron until M3) for Jorah on the PC, recorded in `~/.jorah-private/answers.md`. Shell runs only in OpenClaw's rootless Podman sandbox, `tools.exec.host: "sandbox"`, which fails closed. Web, a headless browser and cron are on. Private connectors, device nodes, account credentials, binding beyond loopback and media generation stay off, and nothing private connects before M3's gate.

**Chrome and the 7-day rule:** Google Chrome stable comes from Google's signed apt repository with no waiting period, a written exception to the 7-day rule, because a browser takes security fixes as they ship. Its package keeps its own `google-chrome.sources` and `/etc/cron.daily/google-chrome`, so it updates with `apt upgrade`. Installed 2026-11-06: 157.0.8103.38, signing key `EB4C 1BFD 4F04 2F6D DDCC EC91 7721 F63B D38B 4796`.

## Persona and shell, 2026-11-06

Built on Adam's go-ahead to build first and test at the end. Nothing here is tested yet.

- **Persona (P2.4):** `workspace/SOUL.md` and `IDENTITY.md`, copied to `/home/jorah/workspace`: witty and warm day to day, dry and brief for work and anything serious, pronoun "he". The old files are `*.pre-persona` next to them.
- **Shell:** agent `background`, added with `openclaw agents add`, then `config/pc/background.patch.json5` (dry run 7 updates, applied, no restart). It runs on the embedded runtime, so `agents.defaults.sandbox` applies (`sandbox explain --agent background`: sandboxed, `all`, `podman`). Its workspace is `/home/jorah/workspace-background`, rules from `workspace-background/`, OpenClaw's seed files moved to `.seed-templates/`. Main may spawn it (`subagents.allowAgents`), and main's `AGENTS.md` says when. The restored llama.cpp plugin was disabled (`plugins disable llama-cpp`), because its failed load made `agents add` refuse.
- **Tools under the sandbox:** OpenClaw's default sandbox allow list (exec, files, sessions) blocks every other tool once a session is sandboxed, so Jorah had no memory search, web, browser, reminders, skills or `heartbeat_respond` (the garbled 15:05 heartbeat). `config/pc/tools.patch.json5` adds them for `main`, and web for `background`, per the waived gate (applied, no restart, audit still 0 critical). `sandbox explain --agent main` lists them.
- **Heartbeat rules:** main's `AGENTS.md` now says what's connected (no email, calendar or social yet), to reply `NO_REPLY` unless something needs Adam, and to use the `automations` tool for reminders.
- **Telegram voice notes:** `services/jorah-voice/bin/jorah-transcribe` runs `jorah_voice.transcribe` (ffmpeg to 16 kHz, Parakeet on the CPU, 60 s pieces, 15 min cap) from the root-owned `/opt/jorah` copy. `config/pc/audio.patch.json5` makes it OpenClaw's audio transcriber (applied, no restart). Audio never leaves the PC. Test at the end: send Jorah a voice note in Telegram. Expected: a reply to what you said.
- **Voice replies in Telegram:** `services/jorah-voice/bin/jorah-speak` runs `jorah_voice.speak` (markup removed, sentences, Kokoro on the CPU, the live service's `michael` voice, 4,000 characters at most) into a WAV. `config/pc/tts.patch.json5` sets `tts.auto: "inbound"` with it as the `tts-local-cli` provider (applied, no restart), so a voice note gets a voice note back and typed messages stay text. Test at the end: send a voice note, expect a voice reply.
- **Adam's step, a Terminal attached to no agent:** Jorah's Console key (the `jorah` workspace, $80 a month cap) for `background` only:

  ```bash
  ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash -l
  openclaw --profile jorah models auth paste-api-key --provider anthropic --agent background --profile-id anthropic:background
  openclaw --profile jorah models auth order set --provider anthropic --agent background anthropic:background
  openclaw --profile jorah secrets audit --check
  ```

  Expected: the key prompt doesn't echo, the order is set, and the audit stays `clean`. If the audit reports the key as plaintext, tell Claude. The order matters because `auth.order.anthropic` is `[]` globally, which would exclude the key.
- **Test at the end:** ask Jorah in Telegram to run `id; ls /home`. Expected: it hands the job to `background`, and the answer shows `uid=1000` and no `/home/jorah`.

## On the API key, not the Max plan, 2026-11-06

Adam asked for every agent on the API key "until I tell you to switch back to the Max plan". `config/pc/api-lane.patch.json5` moves every Claude model to the embedded runtime and sets `auth.order.anthropic` to `anthropic:jorah`, the key's profile in main's store (dry run: 12 updates validated, nothing applied by Claude). That covers chat, heartbeat, Dreaming, the utility model and `background`, so the separate `background` key step above isn't needed while this holds. Main is then inside the Podman sandbox too, so its own exec works. The key's Console workspace has an $80 a month cap: Opus for every message spends it faster than Sonnet would.

- **Adam's step, a Terminal attached to no agent:**

  ```bash
  ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash -l /opt/jorah/scripts/pc/use-api-key.sh
  ```

  Expected: a key prompt that doesn't echo, two order lines, `Dry run successful: 12 update(s)`, then `y` applies it, `validate` passes, and the audit stays clean.
- **Test at the end:** send a Telegram message. Expected: a reply, Console usage for the `jorah` workspace goes up and Claude's Max usage doesn't. If the old session keeps the Max route, tell Claude.
- **Applied 2026-11-07:** Adam ran the script. Main and `background` both list `anthropic:jorah [anthropic/api_key]`, `auth.order.anthropic` is `["anthropic:jorah"]`, no model is left on `claude-cli`, and the Gateway hot-reloaded without a restart. Open: the audit reports `PLAINTEXT_FOUND` for `profiles.anthropic:jorah.key` in `state/openclaw.sqlite`, because `paste-api-key` stores the key itself. Fix, by Adam: put the key in the store as `ANTHROPIC_API_KEY_JORAH` (kind secret), then `secrets configure --skip-provider-setup --agent main` maps the profile to that store ref and scrubs the plain copy. Expected after: `secrets audit --check` is clean.
- **Switching back:** on Adam's word, `config patch --file /opt/jorah/config/pc/max-lane.patch.json5`, dry run first.

## Case fans

The PC is an ASRock B760M Steel Legend WiFi with an i7-14700K, which idles at about 3% load under Jorah (measured 2026-11-06), so the fans spin from the board's default curve, not from work. The fix is a fan curve in the BIOS. It works with nobody signed in to Windows and needs no driver or app, unlike Windows fan tools. The PC needs a monitor and keyboard for it, and Jorah is offline until Windows is back.

1. Restart the PC and press **Del** at the ASRock logo. Press **F6** for Advanced Mode if it opens in Easy Mode.
2. Open **H/W Monitor**. Each header has its own setting: `CPU Fan 1`, `Chassis Fan 1`, `Chassis Fan 2` and so on. The current RPM shows above them, so you can see which headers have fans.
3. For each **Chassis Fan**, set the mode to **Customize** (or **Silent** if you'd rather not set points), with the CPU as the temperature source. Suggested points: up to 50 °C at the lowest speed it allows (0% stops the fan, if the board offers it), 60 °C at 40%, 70 °C at 70%, 80 °C at 100%.
4. For **CPU Fan 1**, choose **Silent**. Don't let it stop: the CPU cooler is what keeps the 14700K safe under a sudden load.
5. **F10** saves and restarts.

Expected: quiet or stopped case fans at idle, and they speed up during a heavy job. The GPU's own fans already stop at idle on most RTX cards. Menu names can differ slightly by BIOS version (this PC has 6.07); if one isn't there, tell Claude what you see.

## iPhone app and the Mac's browser

`config/pc/remote.patch.json5` is applied (no restart): `gateway.publicOrigin` is `https://rocket.tail1574a5.ts.net` and `gateway.trustedProxies` holds `127.0.0.1` and `::1`, so traffic from Windows' Serve proxy is attributed to the real tailnet client and still needs the token. The audit's `trusted_proxies_missing` warning is gone. Port 443 for the Gateway, 43210 for voice. Unverified: that Windows' proxy reaches the distro from loopback.

**Adam's steps**, after "Voice from the Mac" step 1 enabled Serve on the tailnet:

1. **Route, from the Mac** (no secret):

   ```bash
   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "tailscale serve --bg --yes --https=443 http://127.0.0.1:43181"
   ```

   Expected: `Available within your tailnet: https://rocket.tail1574a5.ts.net/` proxying to `http://127.0.0.1:43181`, and `tailscale funnel status` showing nothing public. Undo: the same command with `off` at the end.
2. **iPhone:** install the OpenClaw app. In a Terminal attached to no agent, make a setup code (it holds a pairing secret):

   ```bash
   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash -l -c "openclaw --profile jorah qr --public-url https://rocket.tail1574a5.ts.net"
   ```

   In the app: **Settings → Gateway**, scan the QR, connect. Expected: Jorah's chat with the Telegram history, because it's the same `agent:main:main` session. If the app shows **Pending approval**, approve it in the same Terminal with `openclaw --profile jorah devices list` and `devices approve <requestId>`, after checking it's your phone. Device commands (camera, location, screen and the rest) stay denied by `gateway.nodes.commands.deny`.
3. **Mac browser:** open `https://rocket.tail1574a5.ts.net/` and connect with the Gateway token. Get it in the same Terminal with `openclaw --profile jorah gateway auth-token --show`, paste it into the page, and don't save it anywhere else. Expected: the Control UI, with Chat, Dreams and Skill workshop.

## Daily learning review: blocked by the sandbox

`scripts/setup-learning.sh` and its prompt are in `/opt/jorah`, but don't schedule it yet. `openclaw doctor` warns that with `agents.defaults.sandbox.mode: "all"`, `skill_workshop` is unavailable in a sandboxed run without library-authoring authority, so a cron review could read sessions but never save a skill. Adam's own turns may still save skills in the moment, if they carry the host's authority (unverified, test at the end: correct Jorah on how to do something, expect `💾 Learned: ...`). Fixing the review means a non-sandboxed run for it, which weakens the sandbox, so it's a decision for later.

## Daily backup, written, not installed

`deploy/jorah-backup.service` and `.timer`: `openclaw backup create --verify` at 04:30 into `/home/jorah/backups` (mode 700), keeping 14 daily, 8 weekly and 6 monthly archives with OpenClaw's own retention. Local only: it protects against a broken state, not a dead disk. Offsite is README decision 41 (restic to Hetzner, passphrase offline), Adam's choice. Installing a schedule needs Adam's yes. On that yes:

```bash
git -C ~/Documents/jorah archive HEAD deploy/jorah-backup.service deploy/jorah-backup.timer | pc "wsl -d jorah -u root -- tar -x -C /opt/jorah"
echo 'install -d -o jorah -g jorah -m 700 /home/jorah/backups && install -m 644 /opt/jorah/deploy/jorah-backup.service /opt/jorah/deploy/jorah-backup.timer /etc/systemd/system/ && systemctl daemon-reload && systemctl enable --now jorah-backup.timer && systemctl list-timers jorah-backup.timer --no-pager' | pc "wsl -d jorah -u root -- bash -s"
```

Expected: the timer listed with its next run at 04:30. Undo: `systemctl disable --now jorah-backup.timer`.

## The distro

Ubuntu 24.04, and the WSL default. Commands still name it with `-d jorah`. The old `Ubuntu` and `docker-desktop` distros are separate, and Adam removes them when ready.

```powershell
wsl --install -d Ubuntu-24.04 --name jorah --no-launch
```

From the Mac, with `<pc>` as the setup SSH target:

```bash
ssh <pc> "wsl -d jorah -u root -- bash -s" < scripts/pc/wsl-jorah-setup.sh
ssh <pc> "wsl --terminate jorah"
git archive HEAD services/jorah-voice deploy | ssh <pc> "wsl -d jorah -u root -- tar -x -C /opt/jorah"
ssh <pc> "wsl -d jorah -u root -- bash -c 'cp /opt/jorah/deploy/jorah-firewall.nft /etc/nftables.conf && nft -f /etc/nftables.conf && systemctl enable nftables'"
ssh <pc> "wsl -d jorah -u jorah --cd /opt/jorah/services/jorah-voice -- env UV_PROJECT_ENVIRONMENT=/home/jorah/.venv /home/jorah/.local/bin/uv sync --frozen --no-build --no-install-project"
ssh <pc> "wsl -d jorah -u jorah --cd /home/jorah -- podman build -t openclaw-sandbox:bookworm-slim -f /opt/jorah/deploy/openclaw-sandbox.Containerfile /opt/jorah/deploy"
```

[measured] on the distro as it was built: these pieces ran one at a time, and the whole script hasn't run from a clean distro. That build started under the name `jorah-voice`, and WSL has no rename command, so its `DistributionName` under `HKCU\Software\Microsoft\Windows\CurrentVersion\Lxss` was edited.

## What the sandbox blocks

[measured] as user `jorah`, with `deploy/jorah-firewall.nft` loaded and after a distro restart:

- **Blocked:** Windows' loopback services (Ollama, sshd, Sunshine), the LAN and router, the PC's own LAN and tailnet addresses, other tailnet machines, link-local.
- **Allowed:** public internet, including Anthropic, Telegram, GitHub and npm. Narrowing this is still open.
- **Own ports:** 43181-43199 for the Gateway, 43210 for speech. Windows can reach a listener on them, which is what Tailscale Serve needs.
- **Linux's ephemeral range, 43255-47350,** opened 2026-11-06 on Adam's yes. OpenClaw's tool bridge for Claude (`claude-cli` with bundle MCP) listens on a random loopback port there, and nothing pins it: without this, Jorah chats but has no tools. WSL sets the range under mirrored networking. Nothing on Windows listened in it, and Windows' dynamic range starts at 49152. After a reboot, check `sysctl net.ipv4.ip_local_port_range` still says `43255 47350`.
- **Can't change it:** `nft` refuses as `jorah`, and the OpenClaw and Node folders are read-only to it.

Mirrored networking in `.wslconfig` sends all loopback TCP through `loopback0`, so an interface rule can't tell local from Windows. That's why own ports are listed. Any other loopback port is refused.

## What a scratch Gateway showed

[measured] on 2026-11-06, profile `jorah-dev` on port 43190, as `jorah` with the firewall loaded, channels skipped:

- **Ports:** the Gateway listens on its own port only, on `127.0.0.1` and `[::1]`. No firewall rule fired. OpenClaw needs no other loopback port for the Gateway, CLI, `health` or `status`, so the firewall stays as it is. **One exception, from the Mac's config:** the managed llama.cpp server for local memory search is on port 58378, which the firewall refuses for `jorah` [measured]. Pinning it doesn't help, see below.
- **Serve:** `tailscale.mode: "serve"` stops the Gateway at start, because the distro has no `tailscale` command. OpenClaw's Serve would also use an ephemeral loopback port outside 43181-43199. The PC patch sets it `off`.
- **Bubblewrap works** as `jorah`: all namespaces, no network inside, home hidden, root read-only.
- **Claude Code refuses to start** with `sandbox.failIfUnavailable`, which is the fail-closed result the gate wants. Today the reason is that `socat` is missing, and with `bwrap` hidden too it names both. Until `socat` is installed, delegated coding can't run here.
- **Interop socket:** `jorah` can connect to `/run/WSL/2_interop`. A launch request sent through it reaches the socket, but Windows never connects back (vsock accept times out after 9 s) and no Windows process appears. Interop being off holds for this path, though a hand-written client wasn't tried. A unit with `InaccessiblePaths=/run/WSL` and no `AF_VSOCK` blocks it outright, and the Gateway runs normally under it.
- **External plugins:** `acpx` and `llama-cpp` aren't part of the PC's OpenClaw install and need installing at the cutover.
- On a failed start, OpenClaw tries to run `claude` for a triage. Unsigned, it fails harmlessly.

## Shell, web and browser on `jorah-dev`

[measured] on 2026-11-06 with the new patch, Gateway on 43186, Chrome's CDP on 43191, channels skipped, under the hardened unit:

- **Installs:** apt tools, Podman 4.9.3 with `catatonit`, `uidmap`, `passt` and `slirp4netns`, Chrome 157. `jorah`'s subordinate IDs were under the old name `jorah-voice`, so they were renamed. Backups: `/etc/subuid.pre-podman`, `/etc/subgid.pre-podman`.
- **Sandbox, run with the patch's settings:** user 1000, no host home, no `/run/WSL`, root read-only, workspace writable. The public internet works. The LAN, the router, the PC's tailnet address, the host's loopback and WSL's DNS address on port 80 are refused, and the firewall's counter rises, so it applies to sandbox traffic. Rechecked under `slirp4netns` with and without host loopback, and under `pasta`: public HTTPS 200; 192.168.0.1, the Mac's tailnet address and Windows' `127.0.0.1:11434` refused by every route. The private-address counter rose by 36 and the loopback counter by 2, the latter from the run that forwards to the host's loopback, so the firewall still counts container traffic as `jorah`'s.
- **Through OpenClaw:** `sandbox explain` shows `runtime: sandboxed`, `mode: all`, `backend: podman`. A shell command through OpenClaw itself wasn't run: `/tools/invoke` doesn't offer file or shell tools even with the sandbox off, and a model turn needs the Claude sign-in. With the sandbox off, `exec` didn't run on the host.
- **Browser:** headless Chrome starts with its own sandbox on (no `--no-sandbox`), CDP on loopback. Strict SSRF policy refuses every hostname, because OpenClaw can't guard against DNS rebinding here, so only IP addresses open. With `dangerouslyAllowPrivateNetwork: true`, hostnames open and the firewall still refuses the LAN and tailnet, but pages reach Jorah's own loopback ports, 43181-43199 and 43210. Adam chose private-network mode: the firewall stays as it is, and those loopback ports need a token, except the Gateway's `/health`.
- **Chat Completions:** `/v1/chat/completions` returns 401 without a token and reaches the agent with one.
- **Local memory search is blocked.** The llama-cpp plugin installs and fetches a Linux build. Its router's own port pins to 43185, but the router starts each model's server on a random port and has no option to fix it. The firewall refuses that port, so embeddings fail and memory search falls back to keywords. Setup also downloaded a 2.7 GB chat model (Qwen3.5 4B) by mistake, which was deleted. Adam chose keyword-only search (`provider: "none"`), which found the rehearsal fact. The later fix is NAT networking with Tailscale inside the distro.
- **Web search:** DuckDuckGo 2026.10.9, no account, returned 5 results, wrapped as untrusted content.
- **Linger:** `loginctl enable-linger jorah` is on, so rootless Podman under a system unit uses systemd cgroups.

## Voice from the Mac

```
Mac: build/mac-ear ──wss, tailnet only──> Windows tailscale serve :43210 ──> WSL jorah 127.0.0.1:43210
```

Windows' own Tailscale serves it, because the distro has no `tailscale`. Under mirrored networking Windows reaches the distro's loopback listener [measured: `Test-NetConnection 127.0.0.1 -Port 43210` true]. Serve terminates HTTPS on the tailnet, so `mac-ear` connects with `wss://`, and nothing is exposed past the tailnet: Funnel stays off. Port 43210 rather than 443, so 443 stays free for the Gateway's own route for remote clients. The token travels inside the WebSocket and is checked by `jorah-voice`, and the Gateway token never leaves the PC.

**Adam's steps,** in order. Steps 1 and 3 involve a sign-in and a secret, so run them in a Terminal attached to no agent.

1. **Enable Serve on the tailnet** (one time). From the Mac:
   ```bash
   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "tailscale serve --bg --yes --https=43210 http://127.0.0.1:43210"
   ```
   The first time it prints `Serve is not enabled on your tailnet` and a `login.tailscale.com/f/serve?node=...` link, then waits. Open the link, sign in as the tailnet admin, and enable Serve. Turn on HTTPS certificates too if the page asks. The waiting command then finishes and prints `Available within your tailnet: https://rocket.tail1574a5.ts.net:43210/` with `|-- proxy http://127.0.0.1:43210`. If it doesn't, press Ctrl-C and run the same command again.
2. **Check the route** (no secret):
   ```bash
   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "tailscale serve status & tailscale funnel status"
   ```
   Expected: one entry, `https://rocket.tail1574a5.ts.net:43210 (tailnet only)` proxying to `http://127.0.0.1:43210`, and nothing that says Funnel is on.
3. **Put the client token in the Mac's Keychain.** `mac-ear` reads Keychain service `jorah-voice`, account `adam`. This copies it from the PC without showing it:
   ```bash
   security add-generic-password -U -s jorah-voice -a adam -w "$(ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u jorah -- cat /home/jorah/.config/jorah-voice/token")"
   ```
   Expected: no output. `security find-generic-password -s jorah-voice -a adam` then shows the item without the password. The token sits briefly in that `security` command's arguments on the Mac.
4. **Talk to Jorah.** From the repo (`~/Documents/jorah` after the push and `git pull --ff-only`, or the worktree):
   ```bash
   just mac-ear
   ```
   ```bash
   build/mac-ear --url wss://rocket.tail1574a5.ts.net:43210
   ```
   macOS asks whether Terminal may use the microphone the first time: allow it. The first connection can take up to half a minute while Tailscale gets the certificate. Expected: `● MIC OPEN`. Say "Hello Jorah, what did we last talk about on Telegram?": `You:` shows your words, `Jorah:` the reply as it is spoken. Say "goodbye": `○ MIC CLOSED` and the session's timings. On the PC, `journalctl -u jorah-voice` shows `session open` and `session closed` with timings, never the words.
5. **Same session as Telegram:** send Jorah a message on Telegram that mentions what you just said by voice. Jorah should know it, since both use `agent:main:main`. This is the unverified part of step 6.

If `mac-ear` says `the PC refused the token`, step 3 copied the wrong thing. `connection lost` at once means the Serve route is down (step 2) or `jorah-voice` isn't running (`systemctl status jorah-voice` in the distro). "I can't reach my brain right now" means the Gateway refused or is down.

**Undo:** `tailscale serve --https=43210 off` on Windows removes only this route (`tailscale serve reset` removes all Serve config, which is only this route today). `systemctl disable --now jorah-voice` as root in the distro stops the service. `security delete-generic-password -s jorah-voice -a adam` on the Mac removes the token.

## Still open

- Boot with nobody signed in is untested on Windows Home. The Windows task "Jorah WSL" keeps the distro running (step 2), but the Gateway has no boot service yet, and a reboot test is still owed.
- Semantic memory search: keyword-only until NAT networking with Tailscale inside the distro lets llama.cpp use its random loopback ports.
- Linger gives `jorah` a systemd user manager, so it could create user services. Shell runs in the sandbox, which can't reach it, but step 2 should check `systemctl --user list-units` as part of the soak.
- `/run/WSL/2_interop` stays world-writable. Adam approved the hardening: step 11's unit has it, and step 2's service must carry it too.
- `socat` isn't installed, so Claude Code's sandbox can't start. `scripts/pc/wsl-jorah-setup.sh` doesn't install it.
- `scripts/setup-permissions.sh` writes macOS paths, so it needs a Linux version before delegated coding.
- Remote clients need a Serve route owned by Windows, with `gateway.trustedProxies`. Not tried for the Gateway. Voice has its own route on port 43210, waiting on Adam's Serve consent.
- `/usr/lib/wsl/drivers` is a read-only mount from Windows, kept for the GPU. It also puts Windows `.exe` files inside the distro.
- Public internet is open to the agent.
- SEC-T17, the packet capture from P3's gate, the GPU spike (P1.3) and the 7-day soak.
- Windows SSH still allows password login, and the setup key gets removed when setup ends.
