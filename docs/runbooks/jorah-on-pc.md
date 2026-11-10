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
| 7 | Pair the iPhone and the Mac as clients | **Mac voice:** `mac-ear` built [measured, stand-in tests pass]. Windows Tailscale Serve route `https://rocket.tail1574a5.ts.net:43211` → `http://127.0.0.1:43210` **not up yet**: Serve isn't enabled on the tailnet, which needs Adam's admin consent. Steps in "Voice from the Mac". iPhone and Gateway route: not run |

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
- **Applied 2026-11-07:** Adam ran the script. Main and `background` both list `anthropic:jorah [anthropic/api_key]`, `auth.order.anthropic` is `["anthropic:jorah"]`, no model is left on `claude-cli`, and the Gateway hot-reloaded without a restart. Open: the audit reports `PLAINTEXT_FOUND` for `profiles.anthropic:jorah.key` in `state/openclaw.sqlite`, because `paste-api-key` stores the key itself, in the auth store all agents share. `secrets configure` can't migrate that shared store in 2026.10.9 (it says so). Adam stored the key as `ANTHROPIC_API_KEY_JORAH` (kind secret) on 2026-11-07. The fix, prepared and dry-run (2 stores, 1 config update), applied by Claude on Adam's yes: `secrets apply --from config/pc/api-key-ref.plan.json` gives main and `background` a local profile `anthropic:jorah-store` that only references the stored key, `config/pc/api-key-ref.patch.json5` puts it first in `auth.order`, both agents' order overrides move to it, then `models auth logout anthropic:jorah` removes the plain copy. Expected after: `secrets audit --check` is clean. `scripts/pc/use-api-key.sh` now takes this path from the start. **Applied 2026-11-07 on Adam's yes:** plan applied (2 stores), patch applied (hot reload), both order overrides on `anthropic:jorah-store`. A Telegram reply worked at 20:32 with the order naming only that profile, then `models auth logout anthropic:jorah` removed the plain copy and the Gateway was restarted to apply it. `secrets audit --check`: clean, plaintext=0, unresolved=0. `models auth list` shows only `anthropic:jorah-store` for main and `background`. Adam confirmed a Telegram reply after the restart.
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

**Jorah's voice, 2026-11-08:** Daniel at 1.2, Adam's pick from samples (`jorah_voice/models.py` `DEFAULT_VOICE`, `DEFAULT_SPEED`, used by live voice and Telegram replies). Sentences that are already waiting are spoken as one piece of up to 300 characters (`join_waiting`, `speak.pieces`), the first sentence alone, because Kokoro carries tone only within one piece. Tests: 73 pass. Deployed and `jorah-voice` restarted. A better TTS model is being researched (`docs/plan/research/`, when done).

**Jorah's voice is Qwen3-TTS, 2026-11-08** (Adam: "do Qwen for everything"). Picked after five rounds of samples: `l3-london-warm`, a VoiceDesign voice (mid-sixties, crisp and articulate, warm London accent, non-rhotic, wry), kept as `~/.config/jorah-voice/voice/jorah-ref.wav` and `.txt` (mode 600) and cloned with `Qwen3-TTS-12Hz-1.7B-Base`, so it's the same voice every time. `jorah_voice/qwen_server.py` holds the model loaded and answers on a Unix socket (`~/.cache/jorah-voice/qwen.sock`, no network port; protocol and client in `qwen_protocol.py`). `jorah-voice` uses it with `--tts-engine qwen` (default), sentence by sentence (`chunk_chars` 140), and falls back to Kokoro if the service is down. Telegram replies (`speak.py`) use it for replies up to 900 characters and fall back to Kokoro on failure or for longer ones. Measured by hand on 2026-11-08: the service starts, and a 6-second reply took 8 seconds through it (13-14 s when loading the model per reply). Upstream speed was RTF about 1.3 (python3.12-dev installed, no change); see the fast path below. Tests: 76 pass. **Fast path, 2026-11-08** [measured]: on Adam's yes, `faster-qwen3-tts==0.5.4` (MIT, static cache and CUDA graphs) in its own environment `/home/jorah/apps/fast-qwen/.venv` (transformers 5.15.1, PyTorch cu128, `--exclude-newer 2026-11-01`; it can't share an environment with upstream `qwen-tts`). `services/jorah-voice/tools/fast_qwen_bench.py`, Jorah's voice streaming: 1.7B 0.35 s of compute per second of speech, first audio 291 ms; 0.6B 0.31 s, 274 ms; both 5.1 GB. The service now runs from that environment with the 1.7B model, speaks waiting sentences together again (`chunk_chars` 300), and Telegram replies use it up to 2,500 characters. By hand through `jorah-speak`: 11.1 s of speech in 3.5 s. **Not running yet:** the guard refused to install the service unit, and the first install command broke on Windows' quoting. Adam's step, a Terminal attached to no agent:

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-qwen-voice.sh
```

Expected: `Qwen3-TTS ready on /home/jorah/.cache/jorah-voice/qwen.sock`, then `Speaking with Qwen3-TTS (Jorah's voice)`.

**Running since 2026-11-08 18:21** [measured]: Adam ran the script; `Qwen3-TTS ready on ...qwen.sock`, then `jorah-voice` logged `Speaking with Qwen3-TTS (Jorah's voice)`. `jorah-voice-qwen` enabled and active. Not yet heard by Adam live or in Telegram; not yet seen across a reboot.

**Qwen3-TTS trial, 2026-11-08** [measured], on Adam's yes, for samples only (not wired into `jorah-voice`): `qwen-tts==0.1.1` with PyTorch 2.15 cu132 in `/home/jorah/apps/qwen-tts/.venv` (uv, `--exclude-newer 2026-11-01`, 6 GB), models `Qwen3-TTS-12Hz-1.7B-CustomVoice` and `-Base` from Hugging Face. Nine preset voices and a Daniel clone of a 245-character reply: 1.23 to 1.53 seconds per second of audio, slower than real time, without FlashAttention and with a kernel compile failing; peak 4.8 GB of GPU memory. Not usable for live voice as is; fine quality-wise for Telegram replies if Adam prefers it. Next, only if Adam picks it: FlashAttention or a faster runtime, then a streaming test. Script: `~/apps/qwen-tts/samples.py`.

**Voice route moved to 43211, 2026-11-08** [measured]: with mirrored networking a Windows listener on a port blocks the same port in the distro, so Serve's `:43210` stopped `jorah-voice` from binding 127.0.0.1:43210 after a restart (`Errno 98`). Serve now listens on `https://rocket.tail1574a5.ts.net:43211` and forwards to `http://127.0.0.1:43210`; `jorah-voice` is back (Daniel at 1.2), and from the Mac `:43211` answers 426 (WebSocket only). Rule: a Serve port must never equal a port a distro service binds. The Gateway's 443 → 43181 is fine.

**Serve is on, 2026-11-08** [measured]: Adam enabled HTTPS certificates on the tailnet with Funnel unticked. Claude added both routes from the Mac: `https://rocket.tail1574a5.ts.net` → `http://127.0.0.1:43181` and `https://rocket.tail1574a5.ts.net:43211` → `http://127.0.0.1:43210`, both "tailnet only" in `tailscale serve status` and `funnel status`. From the Mac: the Gateway answers 200 with a valid certificate, voice answers 426 (WebSocket only, as expected). So Windows' proxy does reach the distro over loopback. Steps 1 below and "Voice from the Mac" steps 1 and 2 are done. The lost-phone runbook (`docs/runbooks/lost-phone.md`) exists, so pairing may go ahead.

**Adam's steps**, after "Voice from the Mac" step 1 enabled Serve on the tailnet:

1. **Route, from the Mac** (no secret):

   ```bash
   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "tailscale serve --bg --yes --https=443 http://127.0.0.1:43181"
   ```

   Expected: `Available within your tailnet: https://rocket.tail1574a5.ts.net/` proxying to `http://127.0.0.1:43181`, and `tailscale funnel status` showing nothing public. Undo: the same command with `off` at the end.
2. **iPhone:** install the OpenClaw app. In a Terminal attached to no agent, make a setup code (it holds a pairing secret):

   ```bash
   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- /usr/local/bin/openclaw --profile jorah qr --public-url https://rocket.tail1574a5.ts.net
   ```

   No inner quotes: Windows' shell drops them, and on 2026-11-08 the quoted form started OpenClaw's setup wizard on the default profile instead (cancelled, Jorah's config untouched).

   In the app: **Settings → Gateway**, scan the QR, connect. Expected: Jorah's chat with the Telegram history, because it's the same `agent:main:main` session. If the app shows **Pending approval**, approve it in the same Terminal with `openclaw --profile jorah devices list` and `devices approve <requestId>`, after checking it's your phone. Device commands (camera, location, screen and the rest) stay denied by `gateway.nodes.commands.deny`.
3. **Mac browser:** open `https://rocket.tail1574a5.ts.net/` and connect with the Gateway token. Get it in the same Terminal with `openclaw --profile jorah gateway auth-token --show`, paste it into the page, and don't save it anywhere else. Expected: the Control UI, with Chat, Dreams and Skill workshop.

## Learning skills: off while every session is sandboxed

OpenClaw's own self-learning replaces the planned daily review (`scripts/setup-learning.sh` stays unscheduled). With `skills.workshop.autonomous.mode` at its default `auto`, a review runs 30 s after substantial work (10 model iterations) and may save or update a skill with `skill_workshop`, announcing it in chat; "undo" reverts it. It only runs in a session that isn't sandboxed (`docs/tools/self-learning.md`, "Nothing is learned", item 4). Since the API switch every session is sandboxed, Adam's included, so Jorah learns nothing [read in the docs, 2026-11-08].

`config/pc/learning.patch.json5` takes only Adam's conversation (`agent:main:main`) out of the sandbox with `agents.entries.main.sandbox.mode: "non-main"`. Dry run: 2 updates validated, not applied. Heartbeat, cron and `background` stay sandboxed. Adam's conversation then has no shell (`exec.host: "sandbox"` fails closed outside a sandbox, so shell stays with `background`), files on the host limited to the workspace, and the browser as before. It changes the waived gate of 2026-11-06, so it waited for Adam's yes. **Applied 2026-11-08 on Adam's yes ("so allow it"), as a written exception to that gate:** `sandbox explain` shows `agent:main:main` as `runtime: direct`, a main cron session and `background` as `sandboxed`; `skills.workshop.autonomous.mode` is `auto`. The security audit then listed main with `exec` and `process` outside a sandbox, and ACP sessions (Claude Code through `acpx`) run on the host and were blocked only because main was sandboxed. `config/pc/learning-guard.patch.json5` therefore denies `exec` and `process` to main and sets `acp.enabled: false`, which restores the effective state from before. Audit after: 0 critical, 4 warnings. Backups of the config: `openclaw.json.pre-learning`. The daily backup timer was installed the same day. Test at the end: correct Jorah on how to do something during a longer task. Expected: a message that a skill was saved, and "undo" removes it.

## Haiku in front, Opus behind, 2026-11-08

On Adam's request, applied the same day [measured]: `openclaw agents add deep` (workspace `/home/jorah/workspace-deep`, rules from `workspace-deep/`, OpenClaw's seed files in `.seed-templates/`), a store-backed key profile for `deep` (`anthropic:jorah-store`, audit still clean), then `config/pc/front.patch.json5` (9 updates, hot reload): `main` on `anthropic/claude-haiku-5-5`, `subagents.allowAgents` `[background, deep]`, `deep` on Opus 5.5, sandboxed (`sandbox explain`: sandboxed, `all`), web allowed, `message` denied. `workspace/AGENTS.md` has "Hard Questions: the `deep` Agent": when to hand off, to say so first, to brief fully, and to say an answer came from Opus. Voice uses `main`, so it's on Haiku too. Backups: `openclaw.json.pre-front`, `AGENTS.md.pre-front`. Audit: 0 critical.

- **Not checked yet:** `agent:main:main` last ran on Opus with no override, so the next turn should run on Haiku. `openclaw --profile jorah sessions list --agent main` shows the model after a message.
- **Test at the end:** a greeting (Haiku answers directly, fast); "think hard: should I..." (Jorah says it's asking Opus, then answers with "Opus says"); a hand-off by voice. Note any answer that should have gone to Opus.
- **Undo:** `openclaw --profile jorah config set agents.entries.main.model.primary anthropic/claude-opus-5-5`.

## agentmemory, two-week trial from 2026-11-08

Roadmap P5b step 1, started before P5 on Adam's choice ("let's make it two steps"). Next to `memory-core`, not the memory slot. Evaluation: `docs/plan/research/agentmemory.md`.

- **Installed** [measured]: `@agentmemory/agentmemory@0.9.31` (2026-10-26) in `/home/jorah/apps/agentmemory`, as `jorah`, `npm install --before 2026-11-01 --ignore-scripts` (187 packages, 901 MB, every dependency older than 7 days). Its CLI fetched the pinned iii engine v0.25.0, checked against its built-in SHA-256.
- **Written exception to the 7-day rule:** the two Rust workers come from `api.workers.iii.dev`, which publishes no dates. Recorded SHA-256 on 2026-11-08: `iii` `40e802f38bc4d351df09c87fdab01a3fd7f095eba07ecd11667f45dfeb2d42e1`, `http` 0.22.7 `a653c12a08996d4ed156fb7ba464d78e48b8cac14a9fec65f59d0f8e14cc36cf`, `state` 0.22.20 `f7c2be2008661ac007ff47da197ed4b15bd22c82d657aba354b3f8c44808fd06`. If any changes without an upgrade we chose, stop it.
- **Local only:** `/home/jorah/.agentmemory/.env` sets REST 127.0.0.1:47300, viewer :47302, engine :47304 (inside the firewall's open range 43255-47350; the kernel never hands out a port already bound), `EMBEDDING_PROVIDER=local` (all-MiniLM-L6-v2 in-process), no LLM provider, OpenTelemetry off. `status`: healthy, embeddings local 384 dims, provider none. Secret generated in its data folder (mode 600), data folder mode 700.
- **Connected to Jorah:** `config/pc/agentmemory.patch.json5`, an MCP stdio server proxying to the service, filtered to 8 tools. `mcp probe`: 8 tools. `background` is sandboxed with an allow list, so it doesn't see them. `workspace/AGENTS.md` has a section telling Jorah to save to both memories, search both, and never save text from web pages, emails or tool results as Adam's words.
- **Backed up:** `jorah-backup.service` also writes `<date>-agentmemory-backup.tar.gz` (8.6 MB today) and keeps 14 days of both.
- **Boot:** `jorah-agentmemory.service` installed by Claude on Adam's "yes install it", 2026-11-08 [measured]: enabled, active, ports 47300/47302/47304 on 127.0.0.1, `agentmemory status` healthy, unauthenticated `/health` refused with 401 (its secret is required), `mcp probe` 8 tools. Not yet seen across a reboot.
- **Not tested:** a save and a search through Jorah. Test at the end: tell Jorah a fact, then later ask about it in other words. Expected: it finds it with `memory_smart_search` and says so.

## Daily backup, installed 2026-11-08

Installed by Claude on Adam's request ("you do it"): `deploy/jorah-backup.service` and `.timer` in `/etc/systemd/system`, timer enabled, next run 04:30 (after Dreaming at 03:00), `Persistent=true` catches up a run missed while the PC was off. It writes `openclaw backup create --output /home/jorah/backups --verify` (Gateway state, config, secrets store, workspaces) and deletes archives older than 14 days. OpenClaw's `--keep-*` retention needs a storage location (`--to`), which comes with the offsite decision (README decision 41), so it isn't used. First run 2026-11-08 13:13 [measured]: one archive of 310 MB, "Archive verification: passed", mode 600 in a mode-700 folder owned by `jorah`. Fourteen of these are about 4.3 GB. The archive holds the secrets store, so it never leaves the PC until the offsite copy is encrypted. Still local only: a dead disk loses Jorah and its backups together. The offsite copy and the Pi rescue bot are deferred by Adam (2026-11-08) until nothing else is left to do (roadmap 2a, P2 items 6 and 7).

Restore check, not done yet: `openclaw --profile jorah backup verify <archive>`, then `backup restore <archive> --target <scratch folder>` on a scratch profile.

## Talk from the iPhone, and the build of 2026-11-08

Built and pushed on Adam's yes ("build everything first and then test at once"), roadmap 2a items 3 to 6 of that day's list. **Source and unit tests only** (88 Python, 10 Node); nothing below has run against the real Gateway yet.

- **iPhone Talk (M20.3).** `plugins/jorah-voice-provider` registers `jorah-local`, a realtime Talk provider on the Gateway relay. It only moves 24 kHz audio between Talk and `jorah-voice` on 127.0.0.1:43210; `jorah-voice` does the turn as it does for `mac-ear` (Parakeet, then main through Chat Completions, then the Qwen voice, streaming). No audio leaves the PC. Transcripts go to Talk as non-final only, because the relay appends final ones to the session `jorah-voice` already writes to. `config/pc/talk.patch.json5` points `talk.realtime` at it (dry run: 9 updates validated). One voice session at a time: with `mac-ear` open, Talk is refused with "another voice session is open".
- **Short windows (2.31, `04` 5.3), for Talk only:** closes after 5 s with nothing said, 8 s after a reply (12 s if Jorah asked a question), at once on "thanks" or "that's all". "Stay with me" keeps it open through 2 minutes of quiet, up to 10 minutes, with a spoken warning 30 s before. "Stop", "quiet" or "enough" cut the speech without reaching the model. `mac-ear` keeps its 60 s. Not built, client-side only: earcons, the RAM ring and echo gating (the iPhone cancels echo itself).
- **Hook probe (2.1).** `plugins/jorah-hook-probe` logs each tool call's name and agent, never its arguments, and blocks any call whose arguments hold `JORAH-HOOK-PROBE-7Q`. Test only.
- **Web-only egress.** `deploy/jorah-firewall.nft` now lets `jorah` reach the public internet on tcp 80 and 443 and udp 443 only; every other port is refused and counted. Only 443 was in use when measured. A list of domains isn't possible, because web search and the browser need any site.
- **Setup SSH (P1.2).** `scripts/pc/close-setup-access.ps1`: password login off, and with `-EndSetup` the setup key removed and `sshd` stopped. Adam runs it on the PC, last, because it ends Claude's access.

**Applied** [measured 2026-11-08]: the new code is in `/opt/jorah` and `jorah-voice` restarted on it (Qwen voice, listening on 127.0.0.1:43210). **Not applied:** the firewall and the plugins, because the build session's safety check refused root firewall changes and accepting a plugin's capabilities without Adam. Both are Adam's step 1 below.

**Adam ran `apply-talk.sh` at 19:08** [measured]: both plugins loaded (Gateway lists 13 plugins), `talk.catalog` reports realtime ready with `jorah-local` active, audit 0 critical. `talk.session.create` from the PC returned a relay session at PCM16 24 kHz with brain `agent-consult` (the only brain the Gateway accepts for realtime relay; `none` is refused), and `jorah-voice` logged `session open`, so the Gateway, the plugin, the token and the 24 kHz hello work together. It closed at once because the CLI disconnects after the call. **The firewall step loaded the old file:** Claude's copy to `/opt/jorah` had left out `deploy/`. Fixed file copied at 19:15; it loads with `apply-talk.sh --firewall`.

**Test pass, 2026-11-08 and 09** [measured]:

- **Firewall:** Adam ran `--firewall`: rule loaded, Telegram reached (302), port 587 refused. It survived the distro restart of 2026-11-09 18:33, and its reject counter stayed at 0 through normal use and the turns below.
- **Hook probe (2.1): passes.** Claude sent two turns to `main` from the PC, in a separate session (`agent:main:build-test-2026-11-09`, kept out of Adam's chat). The probe word was blocked: log `hook-probe: BLOCKED tool=tool_call agent=main`, and Jorah reported the block and didn't try to get around it. Ordinary calls logged as `saw` (`read` on `background`, `web_fetch` on `main`). **Finding for the P5 guard:** main reaches web search through the `tool_call` wrapper, so a hook sees `toolName: tool_call`, not `web_search`. A guard keyed on tool names must look inside `tool_call`'s arguments. Removing the probe (`apply-talk.sh --remove-hook-probe`) is Adam's step, because the build session's safety check refused it.
- **Web through the firewall: passes.** The weather turn answered from `web_fetch` (wttr.in). Jorah used `web_fetch` because it took the earlier block to mean web search was off for that session.
- **Restart, 2026-11-09 18:33** (not caused by Claude): the Gateway, `jorah-voice`, `jorah-voice-qwen` and the backup timer all came back on their own, with 0 Gateway restarts. **Bug found:** `jorah-voice` started 27 s before the Qwen service had loaded and fell back to Kokoro for the life of the process. Fixed: it now waits up to 120 s for Qwen (`--qwen-wait`).
- **Talk relay from the PC:** see above. The browser and the iPhone are still to test.

### Test pass

1. **Apply (Adam, a Terminal attached to no agent):**

   ```bash
   ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/apply-talk.sh
   ```

   Expected: "https to Telegram" with a number, "mail port 587: refused", both `jorah-` plugins listed as loaded, `talk.realtime.provider` `jorah-local`, health ok. Undo: the same command with `--undo` at the end.
2. **Hook probe (Adam, Telegram):** send "Search the web for JORAH-HOOK-PROBE-7Q". Expected: Jorah says the search was blocked. Then tell Claude, who reads `journalctl -u openclaw-gateway | grep hook-probe` for `BLOCKED tool=web_search agent=main` and ordinary `saw` lines. Afterwards: the same command as step 1 with `--remove-hook-probe` at the end.
3. **Telegram still works with the firewall (Adam):** ask "What's the weather in Bratislava?" Expected: an answer from a web search.
4. **Talk from the Mac's browser first (Adam):** `https://rocket.tail1574a5.ts.net/`, Chat, the Talk control. Say "What did we last talk about?" Expected: Jorah's voice answers, and the turn shows in Chat once, not twice. Say nothing for 8 s: Talk ends.
5. **Pair the iPhone (Adam):** the steps in "iPhone app and the Mac's browser" above. Expected: Jorah's chat with the Telegram history.
6. **iPhone Talk (Adam, AirPods in):** Chat, the Talk control. Ask "What's on your mind?", then say "stop" while Jorah speaks. Expected: an answer in Jorah's voice; "stop" cuts it at once. Then "Stay with me", wait a minute, ask something else: still open. Then "thanks": Talk ends. If Talk won't start, note the message: that's the riskiest unknown, whether the app offers Talk with a non-OpenAI provider.
7. **Packet capture, no audio leaves (Claude, during step 6):** on Windows, `pktmon` filtered to the Wi-Fi adapter, compared with the tailnet's traffic. Expected: audio-sized traffic only between the phone and the PC on the tailnet.
8. **Reboot proof, P2 step 5 (Adam):** close the MacBook. Restart the PC from the Start menu and sign in to nothing. Within 3 minutes, Telegram: "What's the codeword I gave you?" after giving Jorah a new codeword beforehand. Expected: an answer with the codeword, and no re-pairing.
9. **Learning (Adam, Telegram):** during a longer task, correct how Jorah did something. Expected: a message that a skill was saved; "undo" removes it.
10. **Close setup access (Adam, last, PowerShell as Administrator on the PC):** `scripts/pc/close-setup-access.ps1`, copied from the repo. Expected: from the Mac, a password login is refused. Add `-EndSetup` only when no more setup sessions are planned.

Then the two-week logs start: answers that should have gone to Opus (P5a.4), and the same recall questions to agentmemory and `memory-core` (P5b.4).

## Claude Code sessions for coding, 2026-11-09

Adam chose Claude Code sessions (ACP through the `acpx` plugin) over `background` for coding, on the **Max login**. Jorah's Claude Code (2.1.300, `~/.local/bin/claude`, `CLAUDE_CONFIG_DIR=~/.claude-jorah`) is still signed in from the cutover: `claude auth status` says `loggedIn: true`, `subscriptionType: max` [measured].

**Who can start one:** only Adam's own conversation, `agent:main:main`, which runs outside the sandbox. OpenClaw refuses ACP from sandboxed sessions (`docs/tools/acp-agents/delivery.md`), and those are cron, heartbeat, `background` and `deep`. So "background only" isn't possible, and a coding job starts only when Adam asks, by text or voice. `workspace/AGENTS.md` ("Coding: Claude Code Sessions") tells Jorah when and how.

**Sandbox check** [measured, Claude Code 2.1.300 run directly as `jorah` with the Gateway's environment, in `~/work/sandbox-check`]: `python3`, file writes, `git add` and `git commit` run without approval; `curl https://example.com` refused by the sandbox ("host is not on the allow list"); `~/.openclaw-jorah`, `~/.ssh` and `~/workspace` unreachable; `git push` denied. A commit through `git -c user.name=...` needed approval, which a background job can't give, so `scripts/pc/setup-permissions.sh` now sets Jorah's git identity through the environment (applied: only those 4 lines changed; backup `settings.json.pre-git-identity`). Claude Code never tried to get around a block.

**Pinned adapter:** without a set command, acpx fetches `@agentclientprotocol/claude-agent-acp` with `npx`, unpinned. `scripts/pc/install-claude-acp.sh` installs `0.76.0` (what acpx 2026.10.9 asks for, released 2026-09-09, Apache-2.0) root-owned in `/opt/jorah-tools`, with dependencies as of 2026-11-02, then applies `config/pc/acp.patch.json5` (dry run: 5 updates validated). The adapter bundles Claude Code through the Agent SDK 0.3.257 (Anthropic's terms). **Adam's step**, a Terminal attached to no agent:

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-claude-acp.sh
```

Expected: adapter `0.76.0`, agent sdk `0.3.257`, the linux-x64 binary present, `acp.enabled: true`, the claude command under `/opt/jorah-tools`, and an audit summary with 0 critical. Undo: the same command with `--undo`. Then Claude copies the new `AGENTS.md` into the live workspace and runs one job through Jorah.

**GitHub:** Jorah has no GitHub credential before M3. Adam puts a clone in `~/work/<project>`; Jorah's Claude Code commits on `jorah/<task>`; Adam pulls the branch over the tailnet and pushes it himself.


**Install applied by Adam, 2026-11-09** [measured]: adapter 0.76.0, Agent SDK 0.3.257 with the linux-x64 binary, `acp.enabled: true`, claude command under `/opt/jorah-tools`, audit 0 critical. Claude copied the new `AGENTS.md` into the live workspace (backup `AGENTS.md.pre-acp`).

- **Sandboxed session refused** [measured]: in `agent:main:build-test-acp` the spawn tool offers only `runtime: "subagent"`, and nothing was created.
- **Adam's conversation refused too** [measured]: OpenClaw 2026.10.9 refuses `runtime: "acp"` when the requester denies any of exec, process, read, write, edit or apply_patch, because the harness would get around those denies (`ACP_UNSUPPORTED_INHERITED_TOOL_DENY`). `learning-guard.patch.json5` denies exec and process to main. `config/pc/acp-main.patch.json5` takes those two off again (dry run: 1 update), relying on `tools.exec.host: "sandbox"` failing closed for `agent:main:main`, which runs direct. **Applied 2026-11-09 on Adam's yes ("Yes, allow it")** [measured], backup `openclaw.json.pre-acp-main`; main's deny list is now the three media tools.
- **Main's own exec refused** [measured]: asked in `agent:main:main` to write a probe file with its own exec, it got `exec host=sandbox requires a sandbox runtime for this session`, tried `host=auto` and got the same; no file was written.
- **First coding job through Jorah** [measured]: in `agent:main:main`, "get Claude Code on this" in `~/work/acp-check`. The embedded acpx backend started, and Claude Code made branch `jorah/acp-check` with commit `d6a42ea` by `Jorah <jorah@localhost>` adding `hello.py`. Jorah's reply didn't come back to the CLI call, as the job finishes after the turn. Test folders `~/work/acp-check` and `~/work/sandbox-check` can be deleted.

**Model, 2026-11-10 (Adam: "Opus 5.5 medium")** [measured]: `setup-permissions.sh` now sets `"model": "claude-opus-5-5"` and `"effortLevel": "medium"` (applied; backup `settings.json.pre-opus-medium`). The Claude Code bundled in the adapter, 2.1.257, refused it (`[claude-code:unrecognized_model]`), while Jorah's 2.1.300 runs it. So a root-owned copy of 2.1.300 sits in `/opt/jorah-tools/claude-code/2.1.300/claude` (SHA-256 matched the original; never auto-updates), and `config/pc/acp-claude-code.patch.json5` starts the adapter with `CLAUDE_CODE_EXECUTABLE` pointing at it (applied; backup `openclaw.json.pre-acp-claude-code`). A job through Jorah then committed `c05e917`, and its session record shows `"model":"claude-opus-5-5"`, `"effort":"medium"` and version 2.1.300. Upgrading Claude Code later means a new pinned copy and this patch.

**OpenClaw's own effort, 2026-11-10** [measured]: no thinking level is set anywhere, so every agent and job runs at OpenClaw's fallback, `medium` (Gateway log: `agent model: anthropic/claude-haiku-5-5 (thinking=medium, fast=off)`): main on Haiku 5.5, `background` on Sonnet 5.5, `deep` on Opus 5.5, the hourly heartbeats of all three on Haiku 5.5 (only Haiku calls in 6 hours), and Memory Dreaming on the default model, Opus 5.5.

**Repo work, 2026-11-10 (Adam: "fix both")** [measured]:

- **Package registries:** `setup-permissions.sh` now opens npm and PyPI (`registry.npmjs.org`, `pypi.org`, `files.pythonhosted.org`) to sandboxed commands by default (`JORAH_PACKAGE_NETWORK=0` closes them), with caches in `~/sandbox/.cache`, and lets them read `~/.jorah-github/mirrors`. Applied (backup `settings.json.pre-registries`).
- **Fresh code:** tool `github_sync({ project })` fetches every GitHub branch into the plugin's mirror under `refs/remotes/github/*` with a read-only 1-hour token, no approval; work repos have a remote `github` pointing at the mirror (`scripts/pc/prepare-work-repo.sh <project>`), so Claude Code runs `git fetch github` inside its sandbox. Allowed for main by `github-tools.patch.json5` (applied); plugin consent re-given by Adam. Tested: Jorah synced `threadfolio` (2 branches), Claude Code fetched and branched `jorah/checks-baseline` from `github/main`.
- **`npm ci` failed** in that job (`Proxy connection ended before receiving CONNECT response`). Cause: after the reboot of 2026-11-10 WSL moved `net.ipv4.ip_local_port_range` from 43255-47350 to 55540-59635, and the firewall still allowed only the old range, so Claude Code's sandbox proxy on 127.0.0.1:56929 was refused (loopback rejects 15,287 by then; +6 in a single sandboxed `npm pack`). No Windows listener or reservation is in the new range. Fix, waiting for Adam: `deploy/jorah-firewall.nft` takes the range from a set, and `jorah-firewall-ports.service` fills it from the live sysctl after every firewall load (`scripts/pc/install-firewall-ports.sh`). agentmemory's 47300-47304 stay allowed explicitly. **Installed by Adam, 2026-11-10** [measured]: live range 55540-59635, set filled with it, service enabled for boot and every firewall reload. The re-run through Jorah then passed end to end in about 90 s: `npm ci` (1,273 packages), `tsc --noEmit`, `expo lint` and `jest` (5 suites, 35 tests) all exit 0, committed as `940401a` on `jorah/checks-baseline` (not pushed), with every firewall reject counter still at 0. `npm ci` reported 29 audit findings (1 low, 28 moderate), left as they are.
- Claude Code may not write a work repo's `.git/config` from its sandbox (`could not lock config file` on `git checkout -b`), so branches have no upstream; that also stops it changing remotes.

## Jorah on GitHub: the `jorah-bot` App, from 2026-11-09

**Adam's decisions, 2026-11-09:** bring Jorah's GitHub access forward from M3 ("I want to do this now"), as a GitHub App rather than a machine account (no email, set up once for all repos), starting with `AdamHikl/threadfolio` and adding repos with time. Recorded as a waived gate: M3's checks haven't run, so the limits below carry the weight. Unchanged: Jorah never gets write access to `AdamHikl/jorah`, and Mizyun's repos stay out unless Adam decides otherwise.

- **The App:** `jorah-bot`, App ID 5686503, owned by AdamHikl, permissions Contents and Pull requests (read and write), no webhook, installed only on repos Adam ticks. Its private key lives only on the PC: `/home/jorah/.config/jorah-github/app.pem`, mode 600. Claude Code's sandbox can't read the home folder, `background` and `deep` are in Podman, and main's file tools stop at its workspace. **Open:** the App's page showed no "Private keys" section on 2026-11-09, most likely because of the account's billing lock.
- **Server side, per repo** (`scripts/github/protect-repo.sh owner/repo`, with Adam's `gh` login): ruleset "jorah: only jorah/**" refuses creating, updating, deleting or force-pushing every branch except `jorah/**`, with repository admins bypassing (Adam's own pushes are unaffected: `current_user_can_bypass: always`); ruleset "jorah/**: no force, no delete". Refuses `AdamHikl/jorah`. Private repos need GitHub Pro for rulesets. **Applied to `AdamHikl/threadfolio` on 2026-11-09** [measured]: both active (ids 26889266, 26889267); the repo had no rules before.
- **On the PC** (`plugins/jorah-github`, 12 tests): tools `github_push_branch` and `github_open_pr`. Only projects in its config, only `jorah/<task>` branches, never forced; pull requests open as drafts. For each call it signs a 9-minute JWT with the App's key and gets a 1-hour token for that one repo with only contents and pull requests. **Every call waits for Adam's approval** (a `before_tool_call` hook, which also looks inside the `tool_call` wrapper). The work repo is untrusted, because sandboxed Claude Code wrote it: the branch is fetched into a plugin-owned mirror and pushed from there with hooks off, global config ignored, no credential helper, and the token only in that process's environment through `GIT_ASKPASS`. Tested: hooks, `core.fsmonitor` and a redirecting `insteadOf` planted in the work repo have no effect.
- **Config:** `config/pc/github.patch.json5`, App ID and `threadfolio`.

**Adam's steps:**

1. On the App's page, **Generate a private key** (it downloads to Downloads).
2. **Install App** → AdamHikl → **Only select repositories** → `threadfolio`.
3. A Terminal attached to no agent: `~/Documents/jorah/scripts/github/move-app-key.sh`. Expected: `saved: /home/jorah/.config/jorah-github/app.pem (mode 600)`, a fingerprint matching the one on the App's page, and the Mac copy deleted.
4. Same Terminal: `ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-github.sh`. Expected: `jorah-github` listed as enabled, health ok, 0 critical.

**First tries, 2026-11-09 and 10** [measured]: Adam ran the steps (key on the PC mode 600, Mac copy gone, plugin enabled). A push started from the PC's command line asked for approval in Telegram at 21:55 and timed out unanswered, so nothing was pushed (fail closed). From Telegram on 2026-11-10, Haiku couldn't find the tool: `catalogMode: "direct-only"` kept it out of tool search, and that turn didn't list it directly. And the hook matched any call whose arguments contained a tool name, so it asked Adam to approve a *search* ("Push branch undefined ... to a repo not on the list"); approving it pushed nothing. Fixed: the tools are in the search catalog, and the hook matches only an exact call (OpenClaw runs it again on the inner tool when called through `tool_call`, `wrapToolWithBeforeToolCallHook`), refusing without a prompt when project or branch is missing.

**Still missing after that fix** [measured]: the plugin registered both tools with no diagnostics, but OpenClaw offers a plugin's tools only when the agent's tool allow list permits them (`resolvePluginToolPluginIds`), and main has an explicit list from `tools.patch.json5`. `config/pc/github-tools.patch.json5` adds just the two tool names; **applied 2026-11-10 on Adam's yes** ("Yes, add them"), backup `openclaw.json.pre-github-tools`. After it, the search catalog went from 23 to 25 tools and Jorah finds `github_push_branch` under `jorah-github`. Any future plugin tool for main needs the same step.

**Tested 2026-11-10** [measured]:

- **Push through Jorah: works.** Adam asked in Telegram; the approval read "Push branch jorah/test from ~/work/threadfolio to AdamHikl/threadfolio"; Adam allowed it once; Jorah reported the push. GitHub shows `jorah/test` at `68ad9fd` (author `Jorah <jorah@localhost>`), branch created by `jorah-bot[bot]`; `main` unchanged at `ba67d31`.
- **GitHub refuses the App outside `jorah/**`.** With a real installation token, a push creating `not-jorah-test` got `GH013: Repository rule violations`, and no such branch exists. `main` wasn't tried, because a broken rule would have put a test commit there; it falls under the same ruleset.
- **Fail closed:** an unanswered approval (2026-11-09, 21:55) timed out and nothing was pushed.
- `jorah/test` on GitHub is safe to delete; only Adam can, as the ruleset stops the App deleting branches.
- **Approvals forwarded to Telegram, 2026-11-10, on Adam's yes** [measured]: `config/pc/approvals.patch.json5` (`approvals.plugin`, mode `targets`, agent `main`, Adam's Telegram chat), applied by `scripts/pc/apply-approvals.sh --apply`, which fills the chat ID in from `channels.telegram.allowFrom` so it stays out of the repo (backup `openclaw.json.pre-approvals`). Test: a push asked from the PC's command line, the same position as a voice request, sent its approval card to Telegram at 14:20:01 and the (no-op) push ran at 14:20:26 after Adam allowed it (Adam confirmed: "Yes, I allowed it").
- **Not tested yet:** opening a draft pull request, and whether a request that starts in Telegram now shows two cards (native and forwarded).

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
   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "tailscale serve --bg --yes --https=43211 http://127.0.0.1:43210"
   ```
   The first time it prints `Serve is not enabled on your tailnet` and a `login.tailscale.com/f/serve?node=...` link, then waits. Open the link, sign in as the tailnet admin, and enable Serve. Turn on HTTPS certificates too if the page asks. The waiting command then finishes and prints `Available within your tailnet: https://rocket.tail1574a5.ts.net:43211/` with `|-- proxy http://127.0.0.1:43210`. If it doesn't, press Ctrl-C and run the same command again.
2. **Check the route** (no secret):
   ```bash
   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "tailscale serve status & tailscale funnel status"
   ```
   Expected: one entry, `https://rocket.tail1574a5.ts.net:43211 (tailnet only)` proxying to `http://127.0.0.1:43210`, and nothing that says Funnel is on.
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
   build/mac-ear --url wss://rocket.tail1574a5.ts.net:43211
   ```
   macOS asks whether Terminal may use the microphone the first time: allow it. The first connection can take up to half a minute while Tailscale gets the certificate. Expected: `● MIC OPEN`. Say "Hello Jorah, what did we last talk about on Telegram?": `You:` shows your words, `Jorah:` the reply as it is spoken. Say "goodbye": `○ MIC CLOSED` and the session's timings. On the PC, `journalctl -u jorah-voice` shows `session open` and `session closed` with timings, never the words.
5. **Same session as Telegram:** send Jorah a message on Telegram that mentions what you just said by voice. Jorah should know it, since both use `agent:main:main`. This is the unverified part of step 6.
6. **Always on, with a wake word** (2026-11-08, written by Antigravity on Argon, reviewed by Claude): `build/mac-ear --url wss://rocket.tail1574a5.ts.net:43211 --wake`. It listens on the Mac with Apple's on-device speech recognition (`requiresOnDeviceRecognition`; it refuses to start if the Mac can't recognise on-device) and opens nothing over the network until it hears "Jorah" or "hey Jorah". Then a Tink, `● Jorah is listening`, and a normal session; when that closes ("goodbye", a minute of quiet, the time limit) it goes back to `○ waiting for "Jorah"`. What it hears while waiting is never printed or kept. Ctrl-C quits. macOS asks once for Speech Recognition permission. Checked: `--self-test-wake` (20 cases) and the stand-in server tests pass. Not checked: the real wake behaviour and false triggers, which need Adam's mic. Roadmap 2.33's sherpa-onnx wake word on the Pi (P4) is a separate, later piece.

If `mac-ear` says `the PC refused the token`, step 3 copied the wrong thing. `connection lost` at once means the Serve route is down (step 2) or `jorah-voice` isn't running (`systemctl status jorah-voice` in the distro). "I can't reach my brain right now" means the Gateway refused or is down.

**Undo:** `tailscale serve --https=43211 off` on Windows removes only this route (`tailscale serve reset` removes all Serve config, which is only this route today). `systemctl disable --now jorah-voice` as root in the distro stops the service. `security delete-generic-password -s jorah-voice -a adam` on the Mac removes the token.

## Still open

- Boot with nobody signed in: `openclaw-gateway.service` is enabled and the Windows task "Jorah WSL" keeps the distro up. A BIOS restart on 2026-11-07 brought the Gateway and voice back on their own [measured]; the full reboot test with the Mac closed is still owed.
- Semantic memory search: keyword-only until NAT networking with Tailscale inside the distro lets llama.cpp use its random loopback ports.
- Linger gives `jorah` a systemd user manager, so it could create user services. Shell runs in the sandbox, which can't reach it, but step 2 should check `systemctl --user list-units` as part of the soak.
- `/run/WSL/2_interop` stays world-writable, but the Gateway, voice and backup units all set `InaccessiblePaths=/run/WSL`. The installed Gateway unit matches `deploy/openclaw-gateway.service` [measured 2026-11-08].
- Delegated coding's sandbox, 2026-11-08: `socat` installed from Ubuntu's archive (`bubblewrap` was already there), and `scripts/pc/setup-permissions.sh`, the Linux version, wrote `/home/jorah/.claude-jorah/settings.json` (mode 600): sandbox on and failing closed, no unsandboxed commands, no network, home unreadable except `~/sandbox` and `~/work` (both mode 700). ACP stays off until a coding job is shown to run inside that sandbox [not tested: needs a real Claude Code run].
- Remote clients need a Serve route owned by Windows, with `gateway.trustedProxies`. Not tried for the Gateway. Voice has its own route on port 43210, waiting on Adam's Serve consent.
- `/usr/lib/wsl/drivers` is a read-only mount from Windows, kept for the GPU. It also puts Windows `.exe` files inside the distro.
- Public internet is open to the agent on web ports only, once `apply-talk.sh` has run (see "Talk from the iPhone").
- SEC-T17, the packet capture from P3's gate, the GPU spike (P1.3) and the 7-day soak.
- Windows SSH still allows password login, and the setup key gets removed when setup ends: `scripts/pc/close-setup-access.ps1`, test pass step 10.
