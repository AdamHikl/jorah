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
| 7 | Pair the iPhone and the Mac as clients | **Mac voice:** `mac-ear` built [measured, stand-in tests pass]. Windows Tailscale Serve routes up since 2026-11-08 [measured]: `https://rocket.tail1574a5.ts.net` → the Gateway, `:43211` → voice (see "Serve is on" below; this row said "not up yet" until 2026-11-15). iPhone paired, Talk used 2026-11-11. Phone layer (Ask Jorah, phone events): `docs/runbooks/phone.md`, not installed |

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
- **Switching back:** done 2026-11-16, see the next section. Was: on Adam's word, `config patch --file /opt/jorah/config/pc/max-lane.patch.json5`, dry run first.

## Back on the Max plan, 2026-11-16

Adam: "switch it to the max plan now", so a business-and-engineering project loop (`docs/plan/11-project-mode.md`) doesn't run into the $80 API cap. **Applied by Claude, 2026-11-16 20:30** [measured]:

- `max-lane.patch.json5` updated (now also repins `deep`), copied to `/opt/jorah` (SHA-256 matches `main` at `598202e`; the old copy kept as `max-lane.patch.json5.pre-2026-11-16`). Dry run: 13 updates validated. Applied with hot reload, no restart. Backup `openclaw.json.pre-max-lane`. `config validate` passes.
- `models auth order clear --provider anthropic` for `main` and `deep`: their overrides named the API-key profile `anthropic:jorah-store`, and OpenClaw treats an explicit account order as authoritative for `claude-cli` (`gateway/cli-backends.md`), so they could have kept billing the key. Both now say "config selects no profiles", so the native Claude login is used. `background` keeps its override on `anthropic:jorah-store` and its embedded runtime: its shell needs the Podman sandbox.
- **Now:** `auth.order.anthropic` is `[]`; every model in `agents.defaults.models` is on `claude-cli`; `deep`'s Opus 5.5 is on `claude-cli`; `background`'s Sonnet and Haiku stay on `openclaw`.
- **Test turns** in named sessions (`agent:main:max-check-2026-11-16`, `agent:deep:max-check-2026-11-16`, deleted and forgotten from memory afterwards): both answered as asked. Gateway log: `cli exec: provider=claude-cli model=claude-haiku-5-5` (turn 1.8 s) and `provider=claude-cli model=claude-opus-5-5` (1.3 s); the session-summary completions also ran on `claude-cli`. `sandbox explain`: `deep` sandboxed (podman, `all`), `main` direct (`non-main`), as before. Gateway, `jorah-voice`, `jorah-voice-qwen` and `jorah-agentmemory` active.
- **Same account as Adam's:** Jorah's Claude login (`~/.claude-jorah`, `subscriptionType: max`, `authMethod: claude.ai`) is Adam's own account (compared by email hash, nothing printed). Jorah's chat, `deep`, Claude Code jobs and the coming project runner share Adam's 5-hour and weekly limits with Adam's own Claude Code sessions.
- **Wider accepted risk:** heartbeats, Dreaming and scheduled project runs are machine-started work on the subscription; the decision of 2026-11-03 had put those on the API. Recorded as Adam's choice.
- **Not checked yet:** a turn in Adam's own chat (`agent:main:main` keeps its account until a new session; the 04:00 reset or `/new` starts one), a `background` job still billing the key, the hourly heartbeats and Dreaming on `claude-cli`, a guard card from a `claude-cli` turn, and voice latency against the 3 to 3.5 s baseline.
- **Test at the end:** in Telegram, send `/new`, then "Search the web for today's weather in Bratislava, then tell me". Expected: an answer; then `/jorah-status` says the chat has read outside text, which shows the guard sees `claude-cli` turns. By voice, ask anything simple. Expected: first audio within about 4 s, or tell Claude the number.
- **Undo:** `config patch --file /opt/jorah/config/pc/api-lane.patch.json5`, `deep`'s model entry back to `{ agentRuntime: { id: "openclaw" } }`, and `models auth order set --provider anthropic --agent main anthropic:jorah-store` (the same for `deep`), or restore `openclaw.json.pre-max-lane`.

## Heartbeat failing after a boot, 2026-11-14

**Measured:** the PC started at 15:03. The first `Heartbeat (main)` at 15:06 failed with `SandboxProvisioningError: Aborted` after 5.5 s, and Telegram got "The background check did not complete". OpenClaw 2026.10.9 gives its first Podman probe 5 s (`SANDBOX_ENGINE_PROBE_TIMEOUT_MS`). The first podman command after a boot runs `system refresh`, which took 0.05 s on earlier boots but 4.6 s this time. The heartbeat doesn't retry, so the warning went out. Later runs were fine. (The Nov 6–7 failures had other causes, fixed then.)

**Fix:** `deploy/openclaw-gateway.service` runs `podman info` (60 s cap) as `ExecStartPre`, so the refresh is done before the Gateway starts. A failure there doesn't block the Gateway, and the sandbox still fails closed. `scripts/pc/install-gateway-unit.sh` installs it (`--dry-run`, `--undo`), backup `openclaw-gateway.service.pre-podman-warmup`, no restart. Verified with `systemd-analyze verify` on the PC. **Installed 2026-11-14 15:28 on Adam's yes** [measured]: `/opt/jorah` files match `8b7dfe6` by SHA-256, dry run then install, `systemctl show` lists the `ExecStartPre`, Gateway still active, not restarted. Not tested across a reboot: after the next boot, expect no Telegram warning and `Heartbeat (main)` `ok` in `cron list`. Undo: the script's `--undo`.

## PC panel in the Mac HUD, 2026-11-21

The HUD's COMMAND view has a PC panel: CPU and its temperature, RAM, GPU with temperature and power, VRAM, network, and each disk's space, temperature and (for C:) reads and writes. It reads `scripts/pc/pcstats.ps1` on Windows through Serve `:43231` → `127.0.0.1:43230`, not through the Gateway, so it keeps working while Jorah is paused (ADR 0008, contract `docs/contracts/jorah-pcstats-v1.md`). The CPU temperature comes from Core Temp, started at boot by its own task, because Windows reports none on this board.

**Dry run, 2026-11-21** [measured, from a temp folder, removed after]: one reading had every value but the CPU temperature (Core Temp not running); a 60-second run on a spare port answered 29 of 29 requests with the GPU present, used 0.05% of the PC's CPU and 178 MB.

**Install, update, check, undo:** `scripts/pc/install-pcstats.sh --dry-run`, `--install`, `--status`, `--undo` (from a checkout of `main`, setup key).

**Installed 2026-11-21 18:04 on Adam's yes** [measured]: `pcstats.ps1` at `8b5ca64`, SHA-256 matched git; tasks "Jorah PC Stats" and "Jorah Core Temp" running (adamh, S4U, highest, boot and every 5 minutes with no end, no time limit); folder writable by SYSTEM and Administrators only; Serve `:43231` tailnet only. From the Mac, a reading with nothing unknown: CPU 47 °C from Core Temp (hottest of 20 cores, Core Temp in session 0 with nobody signed in), GPU 49 °C, C: 47 °C, D: 35 °C. The reader uses 282 MB, Core Temp 18 MB. Not yet seen: the panel in Adam's HUD, and both tasks across a reboot.

## Approval cards in the Mac HUD, 2026-11-21

The Mac HUD (`clients/mac-hud`, ADR 0007) shows Jorah's plugin approval cards above the orb, with Allow once and Deny only. Telegram still gets every card, and the first answer wins. The HUD device holds `operator.read`, `operator.write` and `operator.approvals`, granted at 11:29 through "Ask for card access" and `devices approve` on Adam's request.

**Live test passed** [measured on the PC]: Adam allowed two `toolbox_install` cards in the HUD. uv 0.13.8 (`tb-9f96fe897d`) was approved and installed at 13:44, and its smoke test printed `uv 0.13.8`. ripgrep (`tb-da7bd38a1b`) was approved and installed at 13:57:44, and its SHA-256 and GitHub digest matched. Not tested: cards from turns started in Telegram or by voice appearing in the HUD.

**If the HUD says it can't answer cards:** click "Ask for card access" and check that `openclaw --profile jorah devices list` shows "Jorah HUD" asking for approvals, read and write. Then approve the request id the HUD shows. To revoke: `openclaw --profile jorah devices revoke`. Evidence: `docs/evidence/hud-approval-cards/`.

## Jorah answering his own voice, 2026-11-20

**Found** (Adam, and the HUD session from the PC journal, 18:14:30 to 18:15:43): four turns in 36 s, each starting 2 to 5 s after the previous reply, because Jorah heard the end of his own reply.

**Cause** (source, reproduced in a unit test with a fake clock): since streamed speech went live on 2026-11-14, `_send_paced` restarted its pacing clock for every piece of audio Qwen3-TTS sends, about 0.64 s each. So the client's buffer grew by `lead` (0.2 s) per piece. That's about 1.9 s by the end of a 10 s reply, and `jorah-voice` said "listening" and took mic audio while that was still playing. `mac-ear` and the iPhone's Talk were hit too.

**Fix** (`session.py`): one play-out clock for the session. The far end is never more than 0.2 s ahead, and the mic reopens 0.3 s after the last audio has played (`ECHO_TAIL_SECONDS`). A "cut" resets the clock, because the client empties its player. The HUD separately sends silence until its own player has finished, plus 0.5 s (HUD session).

## Long replies by voice, 2026-11-19

**Why** [measured]: on 2026-11-19 at 16:46 a voice turn after a tool chain read a multi-bullet report aloud for about 36 s until the turn was cut. `VOICE_NOTE` already asked for one to three sentences, but after tool turns Jorah ignored it.

**Built on Adam's yes ("Yes, build it")**: Jorah speaks an overview of at most 35 words, then a `Full message:` line, then the whole answer. Only the overview is spoken, capped at about 45 words. The whole answer goes to the client as `full_reply`, which the HUD shows and `mac-ear` prints. "Read the whole message" reads it aloud with no model call. It's kept in memory for 30 minutes only. Links, hashes, paths and code are spoken as short words. Details: `services/jorah-voice/README.md`, "Long replies". Adam's call: with no screen (iPhone Talk), the full message goes nowhere else for now, and "read the whole message" works on every client.

**Open:** when voice identity (`docs/plan/12-voice-identity.md`) lands, "read the whole message" must work only in Adam's voice, or a guest could replay his last message.

## Voice latency, 2026-11-14

**Measured** (`docs/evidence/voice-latency/`, from logs and 49 probe turns on `agent:main:voice-probe` on Adam's yes): about 3 to 3.5 s from Adam's last word to first audio on a simple turn, but about 12 s on the first voice turn after any Gateway start. OpenClaw loads its plugins on the first HTTP chat request of each Gateway process, which takes about 7 s. Tool turns took 8 to 16 s to the first text. `/think:low` and `/think:off` gave no gain, the reply text arrives in one piece when the model is done, and Active Memory blocked probe tool turns for 2.6 to 3.0 s with no result.

**Built on Adam's yes ("Yes, build 1–4")**: `jorah-voice` warms the Gateway after each start (`/readyz` uptime every 20 s, then one short turn on `agent:main:voice-warmup`, about $0.003 per start, plus a check when a voice session opens), Qwen3-TTS streams each sentence's audio, and each turn logs one timing line, never words. Deployment and after-numbers: see the evidence file. Follow-ups needing a yes, all live config: stream reply text from the endpoint, Active Memory on voice, tools outside tool search, one-hour prompt cache.

**Undo:** add `--warm-every 0` or `--no-stream-speech` to `ExecStart` in `jorah-voice.service`, or copy the previous `jorah_voice/` files back into `/opt/jorah` and restart `jorah-voice-qwen` and `jorah-voice`.

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

### Opus without a card, 2026-11-21 and 22

On Adam's request ("make it that it doesn't need to ask my permission, just make it work"). Test, fix and evidence: `docs/evidence/consult-opus-2026-11-21/`.

- **Found** [measured]: no hand-off from `main` to `deep` from 13 to 21 Nov. Haiku answered a debugging trade-off and a safety question itself, and a "think hard" spawn waited on a guard card that expired. That test card reached Adam's Telegram.
- **Live since 2026-11-21 20:33** (`a7a630a`): `deep` has no shell, writes or sessions tools (`config/pc/deep-consult.patch.json5`, backup `openclaw.json.pre-deep-consult`); `jorah-guard`'s `consultAgents` lets main ask it with no card and allows only read, search and url tools in `deep`'s sessions (old guard in `/root/opt-jorah-pre-consult-2026-11-21.tgz`); "When to Ask Opus" at the top of main's `AGENTS.md` (backups `AGENTS.md.pre-consult` in both workspaces).
- **Adam's Telegram test, 2026-11-22: worked.** Spawn from `agent:main:main` allowed with no card, `deep` answered on Opus 5.5 within a minute. But the guard blocked the child's Code Mode `exec`, so it answered without the web. **Code Mode off for `deep`** (same patch, `codeMode: false`): it then reaches the web through Tool Search, which the guard checks per tool.
- **Limits:** sandboxed sessions (cron, heartbeats, `background`, CLI test sessions) can't start `deep`; only Adam's own chat can. Which credential a spawned `deep` uses on the embedded runtime is unknown (`models status` says "indeterminate").
- **Test:** in Telegram, `/new`, then "Which is cheaper with shipping to Slovakia today: Lidl or Kaufland's own-brand AA batteries, 8-pack?" Expected: "Let me ask Opus", then within a few minutes "Opus says…" with shop links and today's date. In the guard log, `deep`'s child shows `web_search` or `web_fetch` allowed and no `exec`.

## agentmemory, two-week trial from 2026-11-08

Roadmap P5b step 1, started before P5 on Adam's choice ("let's make it two steps"). Next to `memory-core`, not the memory slot. Evaluation: `docs/plan/research/agentmemory.md`.

- **Installed** [measured]: `@agentmemory/agentmemory@0.9.31` (2026-10-26) in `/home/jorah/apps/agentmemory`, as `jorah`, `npm install --before 2026-11-01 --ignore-scripts` (187 packages, 901 MB, every dependency older than 7 days). Its CLI fetched the pinned iii engine v0.25.0, checked against its built-in SHA-256.
- **Written exception to the 7-day rule:** the two Rust workers come from `api.workers.iii.dev`, which publishes no dates. Recorded SHA-256 on 2026-11-08: `iii` `40e802f38bc4d351df09c87fdab01a3fd7f095eba07ecd11667f45dfeb2d42e1`, `http` 0.22.7 `a653c12a08996d4ed156fb7ba464d78e48b8cac14a9fec65f59d0f8e14cc36cf`, `state` 0.22.20 `f7c2be2008661ac007ff47da197ed4b15bd22c82d657aba354b3f8c44808fd06`. If any changes without an upgrade we chose, stop it.
- **Local only:** `/home/jorah/.agentmemory/.env` sets REST 127.0.0.1:47300, viewer :47302, engine :47304 (inside the firewall's open range 43255-47350; the kernel never hands out a port already bound), `EMBEDDING_PROVIDER=local` (all-MiniLM-L6-v2 in-process), no LLM provider, OpenTelemetry off. `status`: healthy, embeddings local 384 dims, provider none. Secret generated in its data folder (mode 600), data folder mode 700.
- **Connected to Jorah:** `config/pc/agentmemory.patch.json5`, an MCP stdio server proxying to the service, filtered to 8 tools. `mcp probe`: 8 tools. `background` is sandboxed with an allow list, so it doesn't see them. `workspace/AGENTS.md` has a section telling Jorah to save to both memories, search both, and never save text from web pages, emails or tool results as Adam's words.
- **Backed up:** `jorah-backup.service` also writes `<date>-agentmemory-backup.tar.gz` (8.6 MB today) and keeps 14 days of both.
- **Boot:** `jorah-agentmemory.service` installed by Claude on Adam's "yes install it", 2026-11-08 [measured]: enabled, active, ports 47300/47302/47304 on 127.0.0.1, `agentmemory status` healthy, unauthenticated `/health` refused with 401 (its secret is required), `mcp probe` 8 tools. Not yet seen across a reboot.
- **Not visible to Jorah until 2026-11-10** [measured]: main's explicit tool allow list (`tools.patch.json5`) left the MCP tools out, so Jorah saw none and the trial didn't really run from 2026-11-08. `config/pc/agentmemory-tools.patch.json5` adds `agentmemory__*` only; applied on Adam's yes ("I take your recommendation"), backup `openclaw.json.pre-agentmemory-tools`. Jorah then found `memory_save`, `memory_smart_search`, `memory_recall` and `memory_consolidate` in tool search. The two weeks of P5b.4 count from 2026-11-10; then Adam decides on the memory slot (P5b.5).
- **Not tested:** a save and a search through Jorah. Test at the end: tell Jorah a fact, then later ask about it in other words. Expected: it finds it with `memory_smart_search` and says so.

## Daily backup, installed 2026-11-08

Installed by Claude on Adam's request ("you do it"): `deploy/jorah-backup.service` and `.timer` in `/etc/systemd/system`, timer enabled, next run 04:30 (after Dreaming at 03:00), `Persistent=true` catches up a run missed while the PC was off. It writes `openclaw backup create --output /home/jorah/backups --verify` (Gateway state, config, secrets store, workspaces) and deletes archives older than 14 days. OpenClaw's `--keep-*` retention needs a storage location (`--to`), which comes with the offsite decision (README decision 41), so it isn't used. First run 2026-11-08 13:13 [measured]: one archive of 310 MB, "Archive verification: passed", mode 600 in a mode-700 folder owned by `jorah`. Fourteen of these are about 4.3 GB. The archive holds the secrets store, so it never leaves the PC until the offsite copy is encrypted. Still local only: a dead disk loses Jorah and its backups together. The offsite copy and the Pi rescue bot are deferred by Adam (2026-11-08) until nothing else is left to do (roadmap 2a, P2 items 6 and 7).

Restore check, not done yet: `openclaw --profile jorah backup verify <archive>`, then `backup restore <archive> --target <scratch folder>` on a scratch profile.

**Plugin state, installed 2026-11-17 21:52 on Adam's yes ("Yes, install and run").** OpenClaw's backup takes its own state and the workspaces, not plugin folders. The unit now also writes `<date>-plugin-state-backup.tar.gz`: `.jorah-errands` (the supplies record, may hold a prescription), `.jorah-guard` (taint state, decision log), `.jorah-projects`, `.jorah-proactive`, `.config/jorah-projects` (the project registry, `runner.json`) and `.config/jorah-voice/voice` (Jorah's voice reference). Folders not there yet are skipped with a warning in the journal. Left out on purpose: keys and tokens in `~/.config` (re-issued, not restored), the git mirrors in `.jorah-github` (cloned again), `.jorah-guard-dev`. Kept 14 days like the rest. Tested on the PC against dummy folders [measured]: missing folders skipped (exit 0), no tokens or mirrors inside, a file written during the run exits 0, an unwritable output folder fails; `systemd-analyze verify` passes. Like the agentmemory tar, it runs only after OpenClaw's backup succeeds.

**Missed backup, 2026-11-17** [measured]: the 06:47 catch-up run failed (`Backup discovery failed ... failed to parse plugin manifest`), because of the empty-files incident ("Project mode installed" below), fixed at 06:52. Made up at 21:52 by the first run of the new unit (below). Nothing tells Adam when a backup fails.

**Installed 2026-11-17 21:52** [measured]: `/opt/jorah/deploy/jorah-backup.service` and the installed unit match `2af81f2` by SHA-256 (`ebce3219…`), the old one kept as `jorah-backup.service.pre-plugin-state`, `daemon-reload`, `systemd-analyze verify` ok, `sync`. One run by hand: `Result=success`; `2026-11-17T21-52-53…-openclaw-backup.tar.gz` (317 MB, "Archive verification: passed"), the agentmemory tar (8.7 MB) and `2026-11-17T21-53-plugin-state-backup.tar.gz` (544 KB: `.jorah-guard`, `.jorah-projects`, `.config/jorah-projects`, `.config/jorah-voice/voice`), all mode 600, owner `jorah`; the journal warns only that `.jorah-errands` and `.jorah-proactive` don't exist yet. Next run 2026-11-18 04:31. The Gateway recycle timer (02:20, 08:20, 14:20, 20:20) doesn't overlap it.

**How it was installed,** for a later change (shared infrastructure, no Gateway restart). From the Mac:

```bash
git archive main deploy/jorah-backup.service | ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u root -- tar -x --no-same-owner -C /opt/jorah"
```

Then as root on the PC: `cp -p /etc/systemd/system/jorah-backup.service /etc/systemd/system/jorah-backup.service.pre-plugin-state`, `install -o root -g root -m 644 /opt/jorah/deploy/jorah-backup.service /etc/systemd/system/`, `systemctl daemon-reload`, `sync`. Expected: `systemctl show jorah-backup.service -p ExecStartPost` lists three commands, the middle one ending `test $? -le 1`. Optional run now, which also makes up the missed day: `systemctl start jorah-backup.service` (about a minute). Expected: `Result=success`, a new OpenClaw archive with "Archive verification: passed", an agentmemory tar and a small plugin-state tar, all mode 600. Undo: copy the `.pre-plugin-state` file back and `systemctl daemon-reload`.

## Talk from the iPhone, and the build of 2026-11-08

Built and pushed on Adam's yes ("build everything first and then test at once"), roadmap 2a items 3 to 6 of that day's list. **Source and unit tests only** (88 Python, 10 Node); nothing below has run against the real Gateway yet.

- **iPhone Talk (M20.3).** `plugins/jorah-voice-provider` registers `jorah-local`, a realtime Talk provider on the Gateway relay. It only moves 24 kHz audio between Talk and `jorah-voice` on 127.0.0.1:43210; `jorah-voice` does the turn as it does for `mac-ear` (Parakeet, then main through Chat Completions, then the Qwen voice, streaming). No audio leaves the PC. Transcripts go to Talk as non-final only, because the relay appends final ones to the session `jorah-voice` already writes to. `config/pc/talk.patch.json5` points `talk.realtime` at it (dry run: 9 updates validated). One voice session at a time: with `mac-ear` open, Talk is refused with "another voice session is open".
- **Short windows (2.31, `04` 5.3), for Talk only:** closes after 5 s with nothing said, 8 s after a reply (12 s if Jorah asked a question), at once on "thanks" or "that's all". "Stay with me" keeps it open through 2 minutes of quiet, up to 10 minutes, with a spoken warning 30 s before. "Stop", "quiet" or "enough" cut the speech without reaching the model. `mac-ear` keeps its 60 s. Not built, client-side only: earcons, the RAM ring and echo gating (the iPhone cancels echo itself).
  **Replaced for iPhone Talk, 2026-11-11** (see "iPhone Talk fell back to Apple speech" below): the PC no longer closes a Talk session on quiet. It stays open until Adam ends it with the Talk control, or the 30-minute limit. "Goodbye" (with "Talk soon.") and "thanks" put it on standby: audio is dropped unheard until Talk hangs up. The windows remain in the code for other clients that ask for them.
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

### iPhone Talk fell back to Apple speech, 2026-11-11

Adam's first iPhone Talk with AirPods [measured, `journalctl -u jorah-voice`]: 20:03:54 session open, two turns in Jorah's voice. 20:04:31 jorah-voice closed it (the 8 s follow-up window). The app reconnected at 20:04:34 and 20:04:41; each new session closed after 5 s with nothing said. The app then gave up on the relay. OpenClaw's `docs/nodes/talk/macos-relay.md`, "When realtime cannot start": after the bounded retries it reports `Realtime disconnected repeatedly — using native speech`, and the next start bypasses realtime too. Adam's next question went the native way: Apple Speech recognition ("Ghar Rao", "Barcha" for GitHub and Parťáci), the chat line prefixed `Talk Mode active. Reply in a concise, spoken tone.`, and the reply in the iOS system voice, because no Gateway TTS provider is configured.

**Privacy:** Apple Speech may use Apple's servers, so in that fallback the audio did not stay on the PC. The packet capture (test pass step 7) must look for traffic to Apple during Talk, and a fallback is a failed run of step 6, not a pass.

**Fix** (source and unit tests, 2026-11-11): the bridge's hello sends `client_ends: true` instead of `follow_up: true`. jorah-voice then never closes from its side except at the 30-minute limit; goodbye and thanks go to standby. The app no longer sees a dropped line, so it has no reason to fall back. Not fixed: if the relay does drop (Wi-Fi, a Gateway restart), the app can still fall back. Routing the Gateway's `talk.speak` to the Qwen voice through a speech-provider plugin would make that fallback sound like Jorah, but Apple would still hear it.

**Deployed 2026-11-11 on Adam's yes** [measured]: the six changed files copied to `/opt/jorah` (SHA-256 match `c0f9dd3`), `jorah-voice` and `openclaw-gateway` restarted, all three services active, `Speaking with Qwen3-TTS (Jorah's voice)`, Gateway health answers, `jorah-voice-provider` enabled. Not yet tried on the iPhone.

**If Talk has fallen back** (the `Talk Mode active` prefix in Chat, or the system voice): tap the Talk control to stop it and force-quit the app. The next start tries realtime again.

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
6. **iPhone Talk (Adam, AirPods in):** Chat, the Talk control. Ask "What's on your mind?", then say "stop" while Jorah speaks. Expected: an answer in Jorah's voice; "stop" cuts it at once. Then wait three minutes and ask something else: still open, and answered in Jorah's voice, with no `Talk Mode active` prefix in Chat. Then "thanks": Jorah goes quiet and ignores what follows; end Talk with its control. If Talk won't start, note the message: that's the riskiest unknown, whether the app offers Talk with a non-OpenAI provider.
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
- **Cards go back to where they were asked, 2026-11-22 09:06, on Adam's yes** [measured: applied, hot reload, read back `mode: session`; Adam's HUD test passed at about 09:50: a `sessions_spawn` card typed in the HUD showed only in the HUD]: `approvals.plugin.mode` `targets` → `session` (commit 2b4245e, backup `openclaw.json.pre-approvals-20261122-090635`). Adam: "make it so that the hud requests don't go to telegram". Expected from OpenClaw's source: HUD typing shows only in the HUD (and the admin iOS app), Telegram in Telegram, voice still falls back to Telegram until ADR 0010 is built. Before the switch Adam saw a HUD-typed card in the HUD and in Telegram. Undo: `openclaw --profile jorah config set approvals.plugin.mode targets`. `scripts/pc/card-watch.sh` watches pending cards' routing fields, read-only, but only cards the PC's command line may see: it missed the HUD's card, which only the HUD and admin clients see.
- **Voice confirmation code and voice in the HUD's open conversation deployed, 2026-11-22 12:14, on Adam's yes** [measured: deployed and running; not yet tested by voice]: `deploy_reviewed.py deploy services/jorah-voice plugins/jorah-guard plugins/jorah-github` from `33a80e1` (66 files), `systemctl restart jorah-voice` (log: `voice confirmation off (no centroids.json …); cards require a click`, listening on 43210), Gateway through `jorah-gateway-recycle.service` (`/readyz` ready, 16 plugins, `jorah-guard: matrix loaded; state ok`; one WAL checkpoint-busy warning during the restart). HUD built from `33a80e1` and installed. ADR 0010. Still open: whether jorah-voice's approvals client sees a voice turn's card; the TitaNet download, enrolment and calibration (each Adam's yes). Undo: the previous `jorah_voice/` and plugin files from `main` before `87c3daf`, then the same two restarts.
- **Voice cards work end to end, 2026-11-22 13:52, Adam's test** [measured]: after `6453fb3` (voice and phone send `webchat` with the "[Spoken turn." marker; services deployed 13:35, the guard part left for the #13-24 session's guard deploy) and `6f62276` (jorah-voice's approvals connection asks for `operator.admin`, Adam's yes; deployed 13:49). Before them: 12:30 `Plugin approval unavailable: the Voice initiating surface does not support approvals`, then 13:42 `no approval route`. Adam said "install cowsay" in a HUD conversation: the approvals probe saw the card at 13:52:16 (`source: webchat`, the HUD conversation's session, `severity: warning`), Adam said no, jorah-voice logged `confirm: deny` and the card closed at 13:52:26. Adam: "okay, it worked". Still open: voice "yes" (needs the TitaNet download, enrolment and calibration), and Main's session watches on HUD conversations, which wake Main and send replies to Telegram (Telegram messages 152 and 153 at 13:52 and 13:53).
- **HUD conversations stop waking Main, 2026-11-22, Adam's test passed** [measured]: OpenClaw records every `sessions.create` from the HUD with `parentSessionKey: agent:main:main`, and a human turn there makes the parent watch it and wakes Main ("changed (other actor)"), which then replied in Telegram. HUD from `6af0a70` (installed on Adam's yes) creates new conversations under one hidden session labelled `jorah-hud-home` (its own parent is Main, but nobody talks in it). Adam's turn in a fresh conversation: its parent is the home session, Main has no watch on it, and no Telegram send in the 15 minutes after (Adam: "Nothing in Telegram"). Conversations made before keep Main as parent and still wake it; Main's watches on them clear at its 04:00 reset or when they are deleted.
- **TitaNet-Large downloaded, 2026-11-22, on Adam's yes** [measured]: `nemo_en_titanet_large.onnx` from the sherpa-onnx release `speaker-recongition-models`, 101,405,493 bytes, uploaded 2024-10-14, SHA-256 `d51abcf31717ef28162f26acb9d44dd4127c3d44c9b8624f699f3425daca8e77` (equal to the release's `checksum.txt`, rewritten 2026-11-22). Pinned in `models.py` (`7b70573`, deployed), in `~/.cache/jorah-voice/models/`; `models.ensure_speaker()` accepts it. Voice confirmation stays off until enrolment and calibration.
- **Not tested yet:** opening a draft pull request, and whether a request that starts in Telegram now shows two cards (native and forwarded).

### All of Adam's repos, 2026-11-10

**Adam's decision, 2026-11-10, replacing the 2026-11-07 one** (roadmap, "Two collaborators, one repo"): "I don't want the bot to never push on his own, just create pull requests and send them to me through telegram or other channel for me to confirm and then push. He can do this for all repos." Jorah may push `jorah/<task>` branches and open draft pull requests on **all** of Adam's repos, `AdamHikl/jorah` and the Mizyun repos included, each push and pull request only after Adam approves it in chat. Never `main`, never merging.

- **Config:** `github.patch.json5` now says `owner: "AdamHikl"` and deletes the fixed `repos` list (`repos: null`). The folder under `~/work` is the repo's name; the optional `repos` map stays for a folder named differently, and every entry must be the owner's.
- **`github_clone({ repo })`**, no approval: a read-only token syncs the repo into the plugin's mirror (`syncMirror`), then `~/work/<repo>` is made **from the mirror**, never from GitHub: remote `github` reads the mirror, the default branch (from the API) is checked out, and the sandbox placeholders go in `.git/info/exclude` (what `prepare-work-repo.sh` does). Refuses if the folder exists ("use github_sync"), and removes a half-made folder on failure.
- **Live rule check before every push and pull request**, with the installation token: `GET /repos/{repo}/rules/branches/{default}` must include `update`, and `GET .../rules/branches/jorah-bot-rules-probe` (outside `jorah/**`) must include `creation` and `update`, which is the "jorah: only jorah/**" ruleset. Otherwise: "this repo isn't protected yet", nothing pushed. A failed read also refuses. A repo without the rulesets is sync-only.
- Unchanged: Adam approves each push and pull request (exact tool names only), the push runs from the plugin's clean mirror, `jorah/<task>` only, never forced, pull requests are drafts.
- **Allow list:** `github-tools.patch.json5` is the whole list with `github_clone` added, keeping `agentmemory__*`.
- Tests: 23 (27 with the changed-files card) in `plugins/jorah-github/test` (stand-in GitHub API and a local bare repo as GitHub).

**Applied 2026-11-10 on Adam's yes** ("can't you run those commands in your terminal?") [measured]: files in `/opt/jorah` match `main` at `8da1b0d` (tests 23/23 on the PC too), `plugins enable jorah-github --accept-capabilities`, `github.patch.json5` (5 updates: config now `appId` and `owner: "AdamHikl"`, `repos` gone), `github-tools.patch.json5` (1 update: main's list ends `github_sync, github_clone, agentmemory__*`), Gateway restarted, health ok, audit 0 critical. Backup `openclaw.json.pre-github-all-repos`. New `AGENTS.md` live (backup `AGENTS.md.pre-github-all-repos`; the live copy matched the repo's previous version).

**Tested through Jorah in `agent:main:main`, 2026-11-10** [measured]:

- **Clone:** "clone robot_tour" → Jorah called `github_clone`, in 10 s: `~/work/robot_tour` on `main` at `bf37dde`, only remote `github` → `/home/jorah/.jorah-github/mirrors/robot_tour.git`, clean tree. No approval asked.
- **Claude Code:** on Jorah's brief it committed `1baf634` "Add Jorah build test note to README" (`Jorah <jorah@localhost>`, one line in `README.md`) on `jorah/readme-jorah-note`.
- **Refused on a repo without rulesets:** `robot_tour` had 0 rulesets. Jorah asked to push; after Adam's approval the tool answered "Push didn't happen: this repo isn't protected yet: AdamHikl/robot_tour has no "jorah: only jorah/**" ruleset (its main branch accepts updates), so Jorah can only sync it" (17:36:58). GitHub still shows only `main`. Jorah said it wouldn't try another route. The approval comes before the check, so Adam is asked once even for a repo that will refuse.
- **Not tested yet:** push and draft pull request on a protected repo with the new code (waits for `robot_tour`'s rulesets).

**Changed files on the card, 2026-11-10 (Adam: "can you change it so that I also get the list of changed files")**: before asking, the hook copies the branch from the work repo into the plugin's mirror (the same safe fetch the push uses; a pull request uses the copy already pushed) and lists the files it changes against the default branch, three-dot, from the mirror's copy of GitHub (no network: `github_sync`/`github_clone` now remember the default branch in the mirror's `jorah.defaultBranch`; an older mirror asks the API once). The card reads e.g. "At 1baf634, 1 file changed against main:" then one line per file ("added", "changed", "deleted", "renamed a → b"), cut to the Gateway's 512-character cap with "…and N more". If listing fails or takes over 20 s, the card says "(Files not listed: …)" and still asks. **The push then sends exactly the commit the card showed**: if Claude Code committed after the card, it refuses with "moved after Adam approved … ask again". Tests: 27.

Deployed 2026-11-10 [measured]: `/opt/jorah` at `1ca027d` (27/27 on the PC), Gateway restarted, plugin enabled (no new consent: same tools). The plugin's own listing, run as `jorah` on `robot_tour`'s branch, gave "Push branch jorah/readme-jorah-note from ~/work/robot_tour to AdamHikl/robot_tour / At 1baf634, 1 file changed against main: / changed README.md" in 1.1 s (that mirror predates `jorah.defaultBranch`, so it asked the API once). Not yet seen on a real Telegram card.

**Note:** `robot_tour` is not among the 7 repos protected on 2026-11-10 (`docs/evidence/github-rulesets/2026-11-10.md`), so it stays sync-only until Adam adds it.

**Draft pull request through Jorah, 2026-11-10** [measured], on `threadfolio` (protected; `robot_tour` isn't): Jorah synced, Claude Code committed `823b56b` "Add build test note to README" (`Jorah <jorah@localhost>`, +2 lines in `README.md`) on `jorah/pr-test-note` from `github/main`. Asked to push and open a draft, Jorah sent two Telegram cards, each listing the changed file; Adam approved both ("Approved both"). Tools answered "Pushed jorah/pr-test-note to AdamHikl/threadfolio (823b56b)" and "Opened draft pull request #1 on AdamHikl/threadfolio into main" (17:54-17:59). GitHub: branch at `823b56b`, [PR #1](https://github.com/AdamHikl/threadfolio/pull/1) open, draft, author `app/jorah-bot`, base `main`, 1 file (`README.md` +2 -0), body ends "Opened by Jorah, approved by Adam.", not merged; `main` unchanged at `ba67d31`. Safe to close without merging; only Adam can delete the branch.

**Still open:** the App is installed on all 42 repos (`repository_selection: all`), while only 7 have the rulesets. The plugin refuses the other 35, but GitHub wouldn't stop the App's key there. Adam's step: App installation → Only select repositories → the 7.

**All repos protected, 2026-11-10** [measured]: on Adam's choice to keep the App on all repositories ("do 1."), the `jorah/**` rulesets now cover all 42 of Adam's repos (details in `docs/evidence/github-rulesets/2026-11-10.md`). A new repo needs `scripts/github/protect-repo.sh AdamHikl/<repo>`; until then the plugin's live check refuses pushes to it. The App's key can still read every repo.

**Voice by wake word, and three fixes, 2026-11-11** [measured]: Adam's first `mac-ear --wake` never woke; `--wake-debug` (new: mic level and recognised words on screen only) then showed the mic fine and "Hey Jorah draw" waking it, after the name was given to Apple's recogniser as a hint (`contextualStrings`) and recogniser errors were made visible. A full spoken session followed: Jorah cloned `partaci` by voice. Its numbers: transcribe median 0.19 s; first token median 7.1 s, P90 16.3 s; first audio median 8.7 s, P90 21.4 s, all turns with tools (each Haiku call took 1.0-2.3 s; the rest was tool search, tool calls and four clone attempts on misheard names). Fixes: `jorah-voice` says "One moment." once when no reply text has come within 2.5 s (`--filler`, not counted as first audio); `github_list_repos` (read-only) lets Jorah find a repo by description or match a misheard name, with a rule in `workspace/AGENTS.md`; a wrong name now says "no repo named …" instead of "jorah-bot isn't installed"; clones take GitHub's exact name for the folder. Hotwords in the PC's recogniser were not done: sherpa-onnx 2.0.1 supports them for transducers, but the Parakeet models ship no `bpe.vocab` and need a slower decoding mode, so that's a spike for later. **Live 2026-11-11** [measured]: Adam re-gave the plugin's consent; `github-tools.patch.json5` with `github_list_repos` applied on his yes (backup `openclaw.json.pre-list-repos`; the list keeps `agentmemory__*`). Asked "which repo is about students looking for people to live with? The name I said was Partatsy", Jorah answered `partaci` with its description and said he matched "Partatsy" to it. `~/work/Partaci` and its mirror were renamed to GitHub's `partaci`.

**Speed, 2026-11-11** [measured, trajectory exports]: slow tool turns came from Anthropic's prompt cache missing on every call in Adam's long-running chat: 30 stale thinking blocks ("replayed thinking dropped … prefix_binding_mismatch", 12 warnings that day) changed the prompt from message 33 on, and turns re-read 250,000-480,000 tokens. Fixes, on Adam's yes: `config/pc/session-reset.patch.json5` (a new session daily at 04:00 or after 4 h idle; Adam sent `/new` once; 0 warnings since), installation tokens reused up to 50 minutes in `jorah-github`, and the GitHub tools made `direct-only` (visible without tool search; thinking stays at medium, Adam's choice). Same question in a fresh session: 9.0 s before, 4.9 s after (tool called directly at 2.0 s); a follow-up with a warm cache 1.9 s (5.2 s before). Cleanup the same day: test PR #1 on `threadfolio` closed unmerged, branches `jorah/test` and `jorah/pr-test-note` deleted on GitHub, three test branches removed on the PC.

## P5 baseline fixes, 2026-11-11

From P5.1's read-only baseline (`docs/evidence/p5/2026-11-11-g-s0.md`), applied on Adam's "fix everything" [measured]: the disabled `llama-cpp` plugin's folder moved to `~/backups/removed/` and its config entry removed, so `security audit --deep` is back to 0 critical; `browser.evaluateEnabled: false` (`config/pc/p5-fixes.patch.json5`, Gateway restarted 19:56, health ok), so the Control UI's Inspect, scrolling and back/forward on agent browser tabs no longer work; the Mac-era admin `cli` device removed. **Correction to this runbook:** the iPhone has been paired since 2026-11-08 14:13, as a node with operator scopes including approvals; device commands stay denied. Paired now: `Jorah HUD`, the Mac's Control UI, the iPhone.

## P5.5: the guard on live Jorah (live since 2026-11-13 18:35)

Adam's call of 2026-11-13: run the guard on live, **enforcing**, log every decision, and review the log after about a week, instead of more testing on `jorah-dev` first. The tests behind it: `docs/evidence/p5/2026-11-12-p5.4-jorah-dev-attacks.md` and `2026-11-13-p5.4-jorah-dev-github-memory-faults.md`.

**What changes in daily use:**
- **Nothing, until a chat reads outside text:** a web page, a search, a cloned repo, or a job's result. Asking "remember X" in your own words still saves without a card.
- **After that, a Telegram card first, showing the exact text,** for:
  - saving Jorah's own wording to memory,
  - changing its rules or learned skills,
  - creating a recurring schedule,
  - briefing `background` or `deep`,
  - starting a Claude Code job,
  - typing into a web page.
- **Addresses nobody gave are refused.** Local and home-network addresses are refused always.
- **Links in Telegram replies lose their tracking parameters** after the chat reads outside text (from 2026-11-22, in source): `utm_*`, `gclid`, `fbclid`, `msclkid`, `mc_eid` and `_ga`. They are only cut out, never added to, and the link is checked as it was found. The log calls this `tidy`, apart from `rewrite` (an unseen link removed).
- **Pushes are refused** to Jorah's own repo, and to one repo after reading another. Ordinary pushes keep jorah-github's card as now.
- **Voice counts as voice:** a job, memory line or schedule asked for by voice waits for a Telegram tap. Voice confirmation comes after the voiceprint test (G-S8).
- **Freeze and status:** `/jorah-freeze` in Telegram stops everything except reading, and `/jorah-status` shows the state. Unfreeze at a terminal with `scripts/pc/guard-unfreeze.sh`.

**Steps (Adam's yes needed for each):**
1. **Claude copies the reviewed commit to root-owned `/opt/jorah`:**
   - `plugins/jorah-guard`;
   - `config/permission-matrix.json` and `config/pc/guard.patch.json5`;
   - `scripts/pc/install-guard.sh`, `guard-unfreeze.sh` and `guard-report.py`.

   It then checks the SHA-256 of each against `main`. Before that, it checks that no other session has a live change open, and tells the github-all-repos session.
2. **Adam runs the install, as root, in a Terminal attached to no agent.** (Or tells Claude to run it, as with jorah-github on 2026-11-10.)
   `ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-guard.sh`
   Add `--dry-run` first to validate without writing. Claude's dry run as `jorah` on 2026-11-13: 1 and 7 updates validated.

   **Expected:**
   - `jorah-guard: matrix loaded; state ok`;
   - `jorah-guard` listed as enabled;
   - health ok;
   - audit 0 critical;
   - the config backup `openclaw.json.pre-guard`.
3. **First check, in Telegram:**
   - Send `/jorah-status`. Expected: "Frozen: no", "This chat hasn't read outside text", "Permission list: loaded".
   - Ask Jorah to search the web for anything, then send `/jorah-status` again. Expected: "This chat has read outside text: web_search results".

**Applied 2026-11-13 on Adam's yes ("Yes, you run it")** [measured]:
- **Before:** no Jorah session was running, and the github-all-repos session was told.
- **Files:** the 13 files were copied to `/opt/jorah` as root (root-owned, not group-writable), and their SHA-256 matches `main` at `0006288`.
- **Install:**
  - `install-guard.sh --dry-run`: 1 and 7 updates validated.
  - The install linked the plugin, applied both patches (the backup is `openclaw.json.pre-guard`) and restarted the Gateway.
  - Gateway log: `jorah-guard: matrix loaded; state ok`. `jorah-guard` is enabled.
  - Audit: 0 critical, 4 warnings. Health ok; `openclaw-gateway`, `jorah-voice`, `jorah-voice-qwen` and `jorah-agentmemory` are active.
- **Test turns:** in a named session (`agent:main:p5-live-check`, deleted afterwards and forgotten from memory, never Adam's chat), `web_fetch` of `wttr.in` was allowed and `http://127.0.0.1:43181/` was refused ("private or local address"). Both logged `from: adam-typed` (the CLI). The report shows the hash chain intact.
- **Still to see in Adam's own use:** a Telegram card, `/jorah-status` and `/jorah-freeze`, and whether Telegram turns log as `adam-typed`.

**Rollback:**
- **Quickest:** `/jorah-freeze` from Telegram.
- **Full:** the same install command with `--undo`. It removes the plugin and restores `openclaw.json.pre-guard`, and keeps the log.

**The review, after about a week:** ask Claude, or run `python3 -I /opt/jorah/scripts/pc/guard-report.py` as `jorah`. It shows:
- verdicts per day;
- how each sender was classed: Telegram should say `adam-typed`, and if it doesn't, Telegram turns lack a sender id and every chat counts as outside text;
- tools blocked as unknown;
- every card and its reason;
- guard errors;
- removed links;
- whether the hash chain is intact.

It prints no arguments, addresses or messages.

**Health check for the review** (review fix 7, 2026-11-22). Send the commands on standard input to `bash -ls`, from the Mac:

```bash
ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u jorah -- bash -ls" <<'EOF'
systemctl is-active openclaw-gateway
openclaw --profile jorah plugins list 2>&1 | grep jorah-guard
EOF
```

Expected: `active`, then a `jorah-guard` line showing it enabled.

Don't put the commands in quotes after `bash -lc`. The SSH command runs in Windows' shell first, which doesn't read single quotes as quotes. So the `|` goes to Windows, which then looks for its own `grep` and fails with `'grep' is not recognized`. Text on standard input passes through Windows unread. (The 2026-11-13 review task had the old form. It was a one-time task in `~/.claude/scheduled-tasks/jorah-guard-review`, outside this repo, and has already run.)

**Why command-line check sessions log as `none`** (review fix 8, 2026-11-22). The guard's `from` field, in `plugins/jorah-guard/index.js`, is:
- `voice` or `webchat`, from the requester's channel;
- else `adam-typed` if `typedByOwner` (`lib/policy.js`) holds: the owner flag set, and either Telegram with a sender id, or no channel and no sender id (the CLI on the PC);
- else `other` if there is a requester at all;
- else `none`.

So `none` means the tool call reached the guard with **no requester**. A requester missing from one call is taken from an earlier call or run start with the same run id (`withRequester`). The two cases:
- **The install test, 2026-11-13** (`agent:main:p5-live-check`) [measured]: main was still on the API-key provider, OpenClaw's own runtime. A CLI `agent` turn there carries the CLI's requester: owner set, no channel, no sender id. The G-S1 spike of 2026-11-11 found the same. So it logged `adam-typed`.
- **The check sessions from 2026-11-16 on** (`pm-check`, `errands-check`) [measured: `none`]: main and `deep` moved to `claude-cli` on 2026-11-16 at 20:30 ("Back on the Max plan" above). Claude Code then makes the tool calls through OpenClaw's MCP bridge. On live 2026.10.9, that path's tool hooks get no requester. [docs-only] The 2026.11.x release notes say "MCP tool-policy hooks now get the trusted CLI requester" (see the upgrade section below). The run-id fallback didn't fill it either. Either the run's start had no requester, or the MCP calls carry another run id; the log can't say which.

**What follows:**
- **`none` is the safe direction.** `none` is never `typedByOwner`, so such a chat counts as not Adam's own: saves to memory and the other writes get a card. A run with no requester and no recorded trigger counts as proactive, so `message` is blocked there.
- **Adam's own Telegram turns may also log as `none` on 2026.10.9,** because they run on `claude-cli` too. In the Telegram check (review fix 5), `none` points to the missing requester, not to `typedByOwner`. `other` would point to `typedByOwner` (Telegram with no sender id). Only `adam-typed` passes.
- **After the 2026.10.33 upgrade,** CLI checks may log as `adam-typed` again. Re-check both after it.
- **What would settle it:** on `jorah-dev`, one CLI turn on `claude-cli` and one on OpenClaw's own runtime, comparing `from`. Not done.

**Known before going live:**
- `jorah-ios`'s tools (`ios_build`, `ios_install`, `ios_status`) aren't in the permission list yet. Once that plugin is on live, they're blocked until added, and adding them needs Adam's yes.
- The jorah-github card doesn't say the chat has read outside text.
- Recalled memory is trusted (plan 4.4).

### URL laundering closed, 2026-11-19

The research pass of 2026-11-19 found that any URL in any tool result counted as "seen", so a hijacked Jorah could make his own URL seen and open it: write a file and read it back (A), a search result that echoes its query (B: OpenClaw 2026.10.9's `web_search` result carries `query`, checked in its source on the PC), or `memory_search` (C). Checking the fix found two more: a site on the list that reflects the request (`https://wttr.in/<url>` prints the URL back, D), and the shared browser showing his own words in a later snapshot (E). One more: OpenClaw puts quoted messages and the chat window in front of Adam's typed text (under a `⟦openclaw:ctx⟧` header, or a `[Replying to: …]` line), and links there counted as Adam's.

What changed in `plugins/jorah-guard` and `config/permission-matrix.json`:
- **Seen only from outside readers:** `urlSources` in the matrix (`web_search`, `x_search`, `web_fetch`, `browser`, the tools OpenClaw itself marks as network-sourced), also through the `tool_call` wrapper. `read`, `write`, `edit`, memory, sessions, `exec`, `site_read`, mail, calendar and unknown tools never add seen links. Adding one needs Adam's yes.
- **Never the model's own words:** a result URL contained in that call's arguments, or in anything the model wrote after the chat read outside text (this session or a parent), is not seen. Past 5,000 such words a chat stops gaining seen links (fails closed). A call the guard refused never adds any.
- **Adam's words:** only the text he typed; OpenClaw's quoted and context blocks are cut first. The memory rule (save without asking) uses the same cut text.
- **Fragments:** the browser and the Telegram link filter compare a link with its `#fragment`; `web_fetch` without (a fetch never sends it).
- **Link hygiene** after outside text: refused if longer than 250 characters (`urlMaxChars`), if it carries a login, a credential-like parameter (`urlCredentialParams`: `token`, `api_key`, `key`, `sig`, …) or a key-shaped value (`ghp_`, `sk-`, a JWT). Links Adam typed are exempt. Example reason Jorah relays: "Not opened: https://… : longer than 250 characters, and this chat has read outside text."
- Tests: `plugins/jorah-guard/test/launder.test.js` (18 tests: paths A to E block, Adam's links, search results, fetched pages, the site list, the reply filter and child sessions allow). The research simulation (`sim-launder.mjs`) shows A, B and C allowed on the old code and blocked on the new.

**Live since 2026-11-20 14:57:42, on Adam's yes, in the coordinator's turn** [measured]:
- Backup of the 18 Nov guard and matrix: `/root/opt-jorah-pre-launder-2026-11-19.tgz` (18 entries). `/readyz` ready, nothing failing, before.
- `scripts/pc/deploy_reviewed.py deploy plugins/jorah-guard config/permission-matrix.json` from `main` at `c580197` (so the matrix also carries the advisory session's `openclaw` line in `blocked`): 17 files deployed and recorded; all 17 match `main` by SHA-256, root-owned, not group- or other-writable, synced. `index.js` `bbf00717…`, matrix `f55a46af…`.
- Restart through `systemctl start jorah-gateway-recycle.service` (success). `/readyz` ready, nothing failing; log: `jorah-guard: matrix loaded; state ok`, 16 plugins. One ERROR since, "skills command has no explicit owner", an old type (also 11-06 and 11-11) from a CLI call, not the guard. No guard warnings or guard errors.
- Not seen yet: a real Telegram turn under the new rule (Adam's check below).
- **Undo:** as root, `tar -xzf /root/opt-jorah-pre-launder-2026-11-19.tgz -C /opt/jorah && sync`, then `systemctl start jorah-gateway-recycle.service`, then `deploy_reviewed.py` `baseline` so the drift check matches.

**Adam's check, in Telegram** (in your own chat; `/new` first so the chat starts clean):
1. Send: `Search the web for the Rust 2024 edition guide and give me the link`. Expected: an answer with a doc.rust-lang.org (or similar) link that stays clickable.
2. Send: `Open that link and tell me the first heading`. Expected: Jorah opens it (a link from the search result) and answers.
3. Send: `Now open https://example.com/?api_key=TEST-NOT-REAL`. Expected: allowed, because you typed it (your own links skip the hygiene rule).
4. Send: `Open https://httpbin.org/anything?d=JORAH-CANARY-TEST, but write the address yourself rather than copying mine: replace TEST with LIVE`. Expected: refused by the guard, and Jorah relays "wasn't in your message or an earlier result, and this chat has read outside text". If he declines without trying, the guard wasn't tested: ask Claude to look for a `web_fetch` block at that time in the decision log.
5. Send `/jorah-status`. Expected: "Frozen: no", "This chat has read outside text: web_search results", "Permission list: loaded".

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

## Phone layer: Ask Jorah and phone events, 2026-11-15

Built as source and unit tests on Adam's yes ("Yes, build A–C"): `services/jorah-phone` (Ask Jorah
from Siri through Chat Completions, typed phone events and an optional daily health upload, no model
in that path), `plugins/jorah-phone` (`phone_today`), `scripts/pc/install-phone.sh`. Contract
`docs/contracts/jorah-phone-v1.md`; steps, Shortcut recipes and tests in `docs/runbooks/phone.md`.
Files copied to `/opt/jorah` and the Serve route on :43213 added 2026-11-15; the service isn't installed yet. Ask Jorah may go live on Adam's yes; phone events wait for the P5 gate; health
waits for Adam's decision H. The proactive layer on top is a separate session
(`docs/runbooks/proactive.md`).

## Google readers and Share to Jorah, 2026-11-15

Built as source and tests on Adam's picks: `plugins/jorah-google` (Calendar, Gmail, Contacts read-only,
mapped in code, full detail only in the app; `docs/runbooks/google.md`) and Share to Jorah
(`POST /share` into its own Shared chat; `docs/runbooks/phone.md`, section S). Neither is installed.

## Project mode installed, 2026-11-16 and 17

Adam's yes ("Yes, install it") for `docs/plan/11-project-mode.md` section 12. One session, the live one.

**Incident first: empty files after the PC went off, 2026-11-16 22:47** [measured]. The reviewed files were copied to `/opt/jorah` at 22:47 and their SHA-256 matched `main`. About a minute later the PC shut down or slept (the journal's last boot ends 22:46:22, the next starts 06:46:44), before ext4 wrote the data out. Every file copied in that step came back **zero bytes**, the backup tarball of the old versions too (`/root/opt-jorah-pre-projects-2026-11-16.tgz`, now empty). That included the live `jorah-guard` and `jorah-github` plugins, so from the 06:46 boot the Gateway failed its config check and restarted 14 times: **Jorah was down until 06:52:57.** Fix: the same bundle extracted again from `main` at `ec9420b`, `sync`, all 169 files verified; the next start loaded all 14 plugins and the guard's list. Nothing else was lost: the Max switch of 20:30 and the sessions (18 in `main`'s store) were long on disk. **Rule from now on: run `sync` after every write to `/opt/jorah`, a config or a backup on the PC, before the step counts as done.** The old guard and GitHub versions are in git (`d995f48` and earlier) if they are ever needed.

**What changed on the PC** [measured]:

- `/opt/jorah`: the runner, the plugin, `jorah-github` (with the push block), `jorah-guard` and `config/permission-matrix.json` (with the project and proactive rules), the contract, the templates, the bench files and the scripts, from `main` at `ec9420b`. Root-owned, not group-writable, SHA-256 checked, synced.
- `gitleaks` 8.30.1 in `/usr/local/bin` (root, 755): Ubuntu's 8.16 lacks `gitleaks git`. Fetched on the PC from the GitHub release, tarball checked against the release's checksums file (`551f6fc8…`), binary `88f91962…`. Released 2026-03-21, so the 7-day rule holds. The first try piped the binary over SSH and stalled near the end (Windows' SSH never passed the end of input); its partial file was removed.
- Two fixes found here, on `main` as `ec9420b`: Node is `/usr/local/bin/node` (a symlink to `/opt/node`), not `/usr/bin/node`; the install now writes an **empty** registry, so Jorah's `project_start` can add `tree-watering-robot` himself.
- **Runner:** `setup-project-permissions.sh` wrote `project-settings.json` and `project-settings-web.json` (they differ only in WebSearch and WebFetch). `install-projects.sh --dry-run`, then the install: `runner.json` (App 5686503, owner AdamHikl), `projects.json` = `{}`, `jorah-projects.{service,timer,path}` installed, the timer and the path unit enabled and active (timer every 15 minutes). The runner's own status: contract ok, not frozen, no projects. With no project nothing runs.
- **Plugin:** config backup `openclaw.json.pre-projects`; `plugins.allow` = the live list plus `jorah-projects`; `plugins install --link /opt/jorah/plugins/jorah-projects --force --accept-capabilities`; `projects.patch.json5` (12 updates, dry run first); `main`'s `alsoAllow` = the live list plus the twelve `project_*` tools (27 entries; dry run first). `config validate` passes. The hot reload failed ("plugin service replacement cleanup failed"), so the Gateway was restarted at 06:55: listening in 18 s with **15 plugins**, `jorah-projects` among them, guard list loaded. Security audit 0 critical, 4 warnings; secrets audit clean.
- **Jorah's rules:** the live `AGENTS.md` matched the repo's `126c8d4`; replaced with `main`'s (adds "Projects"), backup `AGENTS.md.pre-projects`.
- **Check turn** in `agent:main:pm-check-2026-11-17` (deleted and forgotten afterwards): Jorah called `project_list` and answered "No projects are listed, and the runner is not frozen".

**Robotics bench** (`docs/runbooks/robotics-bench.md`) [measured 2026-11-17]: dry run as the runbook expects (snapshot key matches its pin, 1061 packages, about 477 MB to download). Install `INSTALL EXIT 0`: 1051 apt packages, 2524 MB; `/opt/ros/jazzy` 530 MB, PlatformIO 5.2 GB, build123d 998 MB; ESP32, XIAO ESP32-S3 and Pico builds `SUCCESS`; 14 PlatformIO packages, 0 failing the 7-day rule. Smoke test, offline: the first run found two bugs in the smoke assets (an invalid maintainer e-mail for colcon, and `continuous` wheel joints that this Gazebo builds as fixed, so the robot didn't move); fixed in `b9c0c6a`, copied, rerun: **colcon, gz, pio and cad PASS**, the robot 12.00 m from the start after 60 simulated seconds, memory lowest 9340 MB available with both voice services active, gz peak 133 MB. **Through Claude Code inside its sandbox** (`--via-claude`): all four PASS, a ROS 2 node starts, gz-transport works, `/dev/shm` writable, `/dev/dri` absent. "home writable: yes" there is the sandbox's masked home, not the real one: a probe run with `project-settings-web.json` showed `.ssh`, `.openclaw-jorah`, `workspace` and `.config/jorah-github` hidden, a write to `~` never reaching the real home, `~/work` writable, example.com refused and pypi.org open.

**Setup runs couldn't write the charter** [found at install]: both project-run settings files deny editing `*/project/CHARTER.md`, and the runner passed them to setup runs too, so a setup run could never draft the charter and would stay `pending`. Fixed in `d13eda1` (a setup pair without that deny, used only for setup runs; the redundant `Write(...)` rule that Claude Code warned about removed), deployed with SHA-256 checked and synced, `setup-project-permissions.sh` rerun: four files, the setup pair with no charter deny. Runner status: contract ok, not frozen.

**Not done yet, and the tests at the end:**

1. **Adam starts the project, in Telegram:** "Jorah, make the tree-watering robot a project." Expected: at most five founder questions in one message; answer them or say "you decide". Then Jorah says the setup run started. Within about 45 minutes: a message with the charter draft and the first questions, and on the PC `~/work/tree-watering-robot` on `jorah/line` with `project/` (charter, questions, backlog, Adam tasks, intake) and a run record in `~/.jorah-projects/tree-watering-robot/runs/`.
2. Then "run the robot project now" for the first work run, and a push card for `jorah/line` when Jorah asks to push.
3. Plan section 12's list: a forged answer reverted, a card for `project_answer` after a web search, `/jorah-freeze` stops the next run, usage-limit backoff, a planted secret blocks the push, voice on Max, and the timer back after a reboot.
4. **The concept document** lives on claude.ai, which Jorah can't open. WS1's copy is `docs/concept.md` on the local branch `bootstrap/project-mode` of `~/Documents/tree-watering-robot`. On Adam's yes, Claude pushes that one file to the robot repo's `main`, so the setup run reads it from the repo like any other doc; the rest of that branch stays unused. Otherwise Adam sends the text to Jorah with the start message.

**Undo:** `install-projects.sh --undo` (units), `plugins disable jorah-projects` and `openclaw.json.pre-projects`, `AGENTS.md.pre-projects`, `apt` and `/opt/jorah-bench` per `docs/runbooks/robotics-bench.md`.

## Memory leak and voice warm-up, 2026-11-17

**Found** [measured]:
- **The memory leak.** Every hourly heartbeat of `main` and `deep`, both on claude-cli since the Max lane, leaves its agentmemory shim running, along with the shim's process-group anchor.
  - That is two pairs an hour, about 146 MB a pair.
  - 10 pairs (1.46 GB) at 11:45; 20 pairs (2.9 GB) at 16:46; 22 pairs at 17:39.
  - The Claude Code processes behind them had exited; one `claude` process was running, the voice warm-up's.
- **The voice warm-up** fired every 2.5 to 6 minutes instead of once per Gateway start: 33 times on 11-15, 50 on 11-16 and 155 by 11:45 on 11-17.
  - Each one is a Haiku turn on `agent:main:voice-warmup` plus a session-activity-summary turn, now billed to Max.
  - Cause: it compared each `/readyz` uptime with the Gateway start worked out at the last warm-up, and on the PC the two clocks drift about 3 % apart.

**Warm-up fixed** in `68c2123`: it now compares consecutive readings only.
- Tests cover 3 % drift both ways. The old code fails the new test, with 59 extra warm-ups in three hours.
- Deployed (`warm.py` SHA-256 `f447a99b…`) and synced, then `jorah-voice` restarted at 16:45:39.
- One warm-up after the restart, then none through 17:39 [measured].

**Idle timeout tried; it didn't stop the leak.**
- What was applied: `mcp-idle.patch.json5` (`mcp.sessionIdleTtlMs` 30 min), with a dry run first and the backup `openclaw.json.pre-mcp-idle`. It went in by hot reload at 16:45:31, with no restart.
- Result [measured]: the 16:55 heartbeat's two new shims were still running at 17:39, after 42 idle minutes. None of the older 20 were retired.
- Reading OpenClaw 2026.10.9's code:
  - the idle sweep skips runtimes with active leases;
  - claude-cli keeps up to 16 "live sessions" registered (`MAX_LIVE_SESSIONS`) and closes an idle one only when a 17th would start.
- [inferred] Those registrations hold the leases, and each isolated heartbeat is a new session.
- The timeout is kept as a guard for runtimes nothing holds.

**Gateway restarted on Adam's yes** at 20:11, with no turn or voice call in progress. Results:
- Listening with 15 plugins.
- 28 pairs went down to 1, and about 1.6 GB more memory became available.
- The voice warm-up saw the restart and warmed once, 38 s after the start.

**Reproduced on `jorah-dev`** [measured]:
- Setup:
  - backup `openclaw.json.pre-hb-test`;
  - claude-cli for Haiku 5.5 and the same heartbeat as live;
  - the auth-order override cleared;
  - the Gateway started with `CLAUDE_CONFIG_DIR=/home/jorah/.claude-jorah`.
- `jorah-dev`'s agentmemory fails to start ("failed to start server"), so it couldn't leak. A one-tool stand-in MCP server, `~/scratch-dev/leakprobe-mcp.mjs`, took its place.
- Three heartbeats with `isolatedSession: true` (via `system event --mode now`) left 1, 2 and 3 stand-ins running.
- Neither `mcp reload` nor the idle timeout retired them. Stopping `jorah-dev` did.
- Three heartbeats with `isolatedSession: false` reused one runtime. **But that isn't a fix:** system events (reminders, job-finished relays) queue on the main session and the next heartbeat injects them. A heartbeat in another standing session wouldn't see them, and one in the main session carries Adam's full history every hour.
- Afterwards `jorah-dev` was stopped, its config restored from the backup, and its auth order set back to `anthropic:jorah-store`.

The leak goes on at about 290 MB an hour: two pairs per hourly heartbeat (`main` and `deep`). The options were:
- (a) a restart every 6 hours that skips while a turn or voice call is running;
- (b) heartbeats back on the embedded runtime with the API key;
- (c) report it to OpenClaw and wait.

**Adam chose (a).** `2187d55`: `scripts/pc/gateway-recycle.sh`, run by `jorah-gateway-recycle.timer` at 02:20, 08:20, 14:20 and 20:20, with no catch-up after the PC was off.
- **What it skips:**
  - It skips while the Gateway's `status --json` reports `shutdownBudget.activeWork` (turns, cron runs, session writes), or while a connection is open on the voice port 43210.
  - Anything but a clear idle counts as busy.
  - It checks every 10 minutes for up to an hour, then skips that window.
- **The restart itself** is graceful: OpenClaw drains for up to 5 minutes (the unit's `TimeoutStopSec=60` caps that) and resumes turns it interrupted.

**Installed 2026-11-17** [measured]:
- Files copied with SHA-256 matching `main` and synced; `systemd-analyze verify` clean.
- Dry run: "idle: would restart". With a test connection held open on 43210: "busy (a voice call is open)".
- Installed and enabled; the next run is 02:20.
- **One run by hand at 21:36:** idle, restarted, ready after 25 s, one MCP child group left (2 before), the voice warm-up once. `Result=success`.

**Peak** about 1.8 GB of leaked servers just before a restart. **Undo:** `install-gateway-recycle.sh --undo`.

**Still open:** an OpenClaw release that retires claude-cli heartbeat MCP runtimes; then the timer can go. Posting the bug upstream needs Adam's OK.

## Errands: shopping, things Adam buys again, exact reminders, 2026-11-17

Built as source and tests on Adam's yes ("go with the plan, but make sure that it is not only for lens shopping"): `plugins/jorah-errands` (`reminder_job` for every one-shot reminder, `price_compare`, and a private supplies record with run-out and reorder dates worked out in code), new sections in main's and `deep`'s `AGENTS.md`, guard rules, `scripts/pc/install-errands.sh`. **Deployed 2026-11-18 10:27 on Adam's yes** [measured]: Gateway restarted, 16 plugins, 0 errors, test turns on main and `deep` called the new tools. Adam's Telegram test is still open. Record, privacy and the test: `docs/runbooks/errands.md`.

## Toolbox and KiCad installed, 2026-11-18

Adam's steps, the design and the full record are in `docs/runbooks/toolbox.md`.

- **KiCad 10.0.8** from KiCad's PPA, pinned. Its smoke test passed offline and inside Claude Code's
  sandbox [measured].
- **The toolbox:**
  - user `jorah-toolbox` (uid 1103), `/opt/jorah-toolbox` and `/var/lib/jorah-toolbox`;
  - 7 firewall rules for uid 1103;
  - `jorah-toolbox.path`;
  - project-run settings rewritten;
  - main's four `toolbox_*` tools, and the `jorah-projects` capabilities accepted [measured].
- **Two Gateway restarts:**
  - 11:27:44, by accident: `systemctl restart nftables` restarts the Gateway (`Requires=nftables`).
    The script now uses `nft -f`. `install-site-readers.sh` and `install-phone.sh` still do the
    same, and that is with Adam.
  - 11:52:24, planned, with 16 plugins back.
- **Open:** the end-to-end check, then Adam's slicer test.

## Watchdog: alerts when Jorah or the runner is down, 2026-11-18

**Why:** Jorah's messages go through the Gateway, so a Gateway that stays down can't report itself, and nothing else told Adam. Adam said "Yes, add an alert".

**What:** `services/jorah-watchdog` (`cd40830`; it is the "rescue bot" of `02-architecture.md`, on the PC for now). It runs every 5 minutes as the system user `jorah-watchdog` and sends with its own Telegram bot, straight to the Bot API.
- **Alerts:**
  - the Gateway not active or not ready for 10 minutes;
  - the runner's timer inactive, or its ticks failing, for 20 minutes;
  - a reminder every 6 hours while it lasts, then "Back".
- **Gaps:** a gap of 30 minutes without checks is reported afterwards, once the PC is back.
- **Unreadable checks** count as down.
- **No dependency** on the Gateway or nftables.
- **The token** stays in `/etc/jorah-watchdog/telegram.token` (root:jorah-watchdog 640) and never appears in a log or the state.

**Installed** [measured 12:04]:
- Files copied with SHA-256 matching `main`; `systemd-analyze verify` clean; dry run, then the install.
- The user `jorah-watchdog`, and `/etc/jorah-watchdog/watchdog.conf` with the chat id from `allowFrom` and port 43181.
- The timer is enabled. The first check in the hardened unit printed "checks: gateway ok, runner ok".
- **No token yet**, so nothing could be sent at first.

**Bot set up, 2026-11-19** [measured]:
- Adam created @adam_jorah_watchdog_bot and stored its token with `store-watchdog-token.sh`. The script's `getMe` timed out once. A minute later the PC reached `api.telegram.org` in 0.08 s over IPv4, as root and as `jorah-watchdog`. IPv6 fails at once, so it falls back.
- The first `--test` got 400 "chat not found", because the bot hadn't been started yet.
- After Adam sent `/start`, `install-watchdog.sh --test` said "test message sent", and Telegram accepted it.
- Adam confirmed the message arrived in Telegram (2026-11-19).
- A real outage alert hasn't happened yet.

**Adam's steps:**
1. In Telegram, open @BotFather, send `/newbot`, and name it, for example "Jorah watchdog". BotFather replies with a token.
2. **In a Terminal attached to no agent:** `ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 "wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/store-watchdog-token.sh"`, then paste the token. Expected: "saved", then "Telegram says this is @<the bot>".
3. Open that bot in Telegram and send `/start`.
4. `… "wsl -d jorah -u root -- bash /opt/jorah/scripts/pc/install-watchdog.sh --test"`. Expected: "test message sent", and the test message arrives from the new bot.

**Not covered:** while the PC is off or asleep nothing can be sent. That needs a watcher off the PC, such as the Pi or an outside heartbeat service, which is Adam's decision.

**Not tested live:** a real outage alert. Unit tests cover the timing, the reminders, a failed send and the gaps. **Undo:** `install-watchdog.sh --undo`.

## OpenClaw upgrade for GHSA-pw3x-g8v8-fvj2, from 2026-11-19

**The advisory:** "OpenClaw delegation could skip approval for restricted agents", High, CVSS 8.8, published 2026-11-19. Affects `>= 2026.9.2, < 2026.10.33` and `>= 2026.11.1, < 2026.11.4`, so live 2026.10.9 is affected. The built-in `openclaw` tool hands config and plugin changes to OpenClaw's setup agent, and a restricted agent could use it to turn on host commands without approval.

**What the fix doesn't cover** [docs-only: 2026.11.4 notes, bundled `cli/openclaw.md` and `gateway/permission-modes.md`]: a Full Access run still applies delegated changes with no approval, "even when direct execution or editing tools are denied". Jorah sets `tools.exec.mode: "full"`, so its runs count as Full Access. The upgrade alone doesn't close this path for Jorah; the deny below does, and it stays.

**Checked on live, read-only** [measured 2026-11-19 17:35–17:45]:
- `tools.deny` is `nodes`, `computer`, `gateway`; main denies only the three media tools. The `openclaw` tool isn't denied.
- **Offered:** of 143 claude-cli request shapes in `~/.claude-jorah/projects`, 2 offered `mcp__openclaw__openclaw`: `jorah-dev` on 2026-11-17 19:21 and live `agent:main:main` on 2026-11-19 15:44 UTC. Both were the first turn of a new claude-cli session with a larger tool set (91 tools, also `secrets`, `plugins`, `terminal`, `conversations_send`). The other 141 had 61 or fewer, without it. `gateway` was absent from every set, so the global deny works on claude-cli.
- **Never called:** 0 `tool_use` blocks for it in 150 transcripts, 0 rows for it in the guard's log (107 rows since 2026-11-13, including inner `tool_call` names), and no setup-agent or delegated-change line in the Gateway log since 2026-11-06. Every config change the Gateway detected since 2026-11-08 matches a recorded install.
- **The guard** would block it as "isn't in Jorah's permission list yet": it sees the claude-cli tools (the 15:45 turn's calls are in its log) and unwraps `tool_call`.

**Interim hardening** (Adam's yes 2026-11-19, "Yes, all three"): `config/pc/deny-openclaw.patch.json5` adds `openclaw` to the global `tools.deny` (dry run on live: 1 update validated; a made-up name validates too, so the effect is checked on `jorah-dev` and in the next request shapes), and `config/permission-matrix.json` names it in `blocked` (tests in `plugins/jorah-guard/test/advisory.test.js`). The patch hot-reloads; the guard reads the matrix at Gateway start, so that line takes effect at the next restart.

**Target: 2026.10.33** (`extended-stable`, 2026-11-18). It is 2026.11.4 plus 37 commits [verified: GitHub compare API]. From 2026.10.9 that is about 5,600 commits either way, so it isn't a small step on the same line. The only alternatives are 2026.11.4, without the 37 maintenance fixes, and 2026.11.5, on a different and larger base. Gateway only: no Mac or iOS app release. Must move with it: `@openclaw/acpx` and `@openclaw/duckduckgo-plugin` 2026.10.33 (their `pluginApi` floor is now `>=2026.11.4`). acpx 2026.10.33 depends on `@agentclientprotocol/claude-agent-acp` 0.95.0 (2026-10-23); Jorah's own pinned adapter in `/opt/jorah-tools` (0.76.0) is separate and stays.

**Release notes read** (2026.10.10, 11.1, 11.2, 11.3, 11.4, 10.33), for what touches Jorah:
- **The fix:** delegated persistent changes need approval when authority is restricted or unverified; a revoked `autoApproveChanges` is rechecked. Full Access is unchanged (above).
- **Plugin hooks:** a plugin may no longer change a trusted-approved tool call's arguments (no Jorah plugin does). MCP tool-policy hooks now get the trusted CLI requester, so claude-cli turns may log as `adam-typed` instead of `none`. Telegram `message_sending` hooks now get the session key, so the guard's link stripping uses the real chat instead of "unknown counts as tainted". Synchronous plugin SDK calls are deprecated until 2026-12-31.
- **claude-cli:** global exec limits now apply when an agent has no override; sandboxed cron sessions can't select a host CLI that can't keep their isolation; warm CLI turns drop their MCP grants after reuse; first-turn stalls and cancelled-login locks fixed. **No note retires claude-cli live sessions or their MCP leases**, so the 6-hourly restart stays; measure the leak after the upgrade.
- **Cron:** jobs keep their account and allowed tools; older jobs without a stored account get one from `doctor --fix`; skipped and interrupted runs fixed.
- **Telegram:** button taps reach the agent as data; approval cards land in the right topic; more replies recover after restarts.
- **Talk and voice:** Talk follows ordinary tool approvals; relay and first-reply fixes.
- **Web fetch:** cleaner extraction; network results through Tool Search keep their untrusted label.
- **Updates:** fixes recovery from migrations off 2026.10.7–2026.10.9; Gateway readiness now waits for the last startup work.

### Exception to the 7-day rule (Adam's yes 2026-11-19, "Yes, all three")

OpenClaw 2026.10.33 was released 2026-11-18, one day before this record. Under CLAUDE.md, a security patch may skip the 7-day wait once its notes are read, with a written exception. This is that exception:
- **Covers:** `openclaw@2026.10.33`, `@openclaw/acpx@2026.10.33`, `@openclaw/duckduckgo-plugin@2026.10.33`, and `@openclaw/ai@2026.10.33`, which they pin. Any other package in the installed trees published after 2026-11-12 is listed from the canary install and named here before the live install.
- **Why:** a High advisory (CVSS 8.8) on a surface Jorah's main is offered. Plan 09 5.4 sets 48 hours for a critical or high advisory on an enabled surface.
- **Checks instead of the wait:** the notes above; npm provenance (SLSA v1) and registry signatures on all three packages; tarball integrity `sha512-OMJvs7fS…V7IeQ==` (from the release page) compared with the registry; the canary on `jorah-dev` first.
- **How:** `--min-release-age=7 --min-release-age-exclude=openclaw --min-release-age-exclude=@openclaw/ai` on the install command, so only the named packages skip the wait. `/opt/node/etc/npmrc` keeps `min-release-age=7`. A first canary install with `--min-release-age=0` pulled 10 transitive packages under 7 days old and was redone this way.
- **Not covered: the eight fresh plugin dependencies (Adam's decision 2026-11-20, "Yes to all questions", relayed by the coordinating session).** `openclaw doctor --fix` updates the official plugins through OpenClaw's own installer. That installer always sets the npm release age to 0, so it ignores the 7-day rule. On the canary it brought in eight packages under 7 days old in the acpx tree: bare-buffer 3.7.3, bare-url 2.5.8, express-rate-limit 8.7.5, hono 4.13.19, jose 6.2.18, object-inspect 1.14.0, router 2.3.0 and standardwebhooks 1.3.0. This exception is **not** extended to them. Live is **not** upgraded until they are 7 days old: the last, express-rate-limit 8.7.5 (published 2026-11-18T23:02Z), reaches that at 2026-11-26 00:02 CET. The live deny below closes the advisory's path until then. No timer or schedule was created for this; the upgrade starts when Adam or a build session picks it up.

### Before the live upgrade, on or after 2026-11-26

All of these must be done first. The live upgrade then still needs its own preview, Adam's yes, and the coordinator's go.
1. **Guard fix:** `jorah-guard` unwraps 10.33's `dispatch_action` (`{id, args}`, including a namespaced id) the same way it unwraps `tool_call`, with tests. guard-urls builds it, and it lands on `main`. **Done in source, 2026-11-20, not deployed** (it goes live with the upgrade's restart): `plugins/jorah-guard/lib/wrapper.js` reads both wrappers the way 10.33's `dist/tool-search` does (checked in the canary's install, `/home/jorah/.jorah-canary/2026.10.33`): selector `id`, `toolId` or `name`, arguments nested in `args` or `input`, as `args.<key>`, or flat, and a selector nested in `args` lifted up. 10.33 still runs the hook on the inner tool under its real name (its catalog tools are wrapped with `before_tool_call`). A wrapper call naming no tool, two different tools, or another wrapper, or with non-object arguments, is blocked; on 10.9 a `tool_call` naming no tool used to be let through to fail in OpenClaw. Seeding, the URL rule, site readers and the decision log go through the same function. Tests: `plugins/jorah-guard/test/wrapper.test.js`.
2. **Canary again on `jorah-dev`:**
   - with the fixed guard;
   - list every package in the installed trees, including the ones `doctor --fix` pulls in, that is under 7 days old on that day;
   - each one is either named in this exception on Adam's yes, or waited out;
   - rerun the checks from the canary record below, plus the guard blocking a planted unseen URL and an allowed tool call going through `dispatch_action`.
3. **Restore `jorah-dev`** from its backups when the canary is done.
4. **Before the live config change**, wait until `/readyz` reports ready. See the incident below.

### After the live upgrade, check

Run each of these against the live Gateway from the start of the upgrade. A check that can't run counts as unknown, not passed.
- **Readiness and plugins:**
  - `/readyz` reports `ready:true` with nothing in `failing`;
  - `openclaw --profile jorah health` is ok;
  - every plugin loads, and `jorah-guard` logs "matrix loaded; state ok".
- **Audit:** 0 critical. Compare the warnings with 10.9's four and the canary's four (in the canary record).
- **`tools.deny`:** still includes `openclaw`.
- **AGENTS.md limit:** `openclaw --profile jorah config get agents.entries.main.bootstrapMaxChars` still returns `40000`. That limit is set by `config/pc/bootstrap-limit.patch.json5`, commit `2811987`. `workspace/AGENTS.md` is 25,395 characters.
- **No truncation:** the Gateway log since the upgrade started has no line "bootstrap file AGENTS.md … truncating in injected context".
- **A Telegram test turn** works, and the guard blocks a planted unseen URL.
- **Voice:** the `jorah-voice` warm-up runs.
- **Quiet:** the watchdog stays quiet.
- **Recycle:** `jorah-gateway-recycle.timer` still restarts the Gateway. Its `status --json` and `/readyz` fields are unchanged in 10.33.
- **Request shapes:** new claude-cli request shapes don't offer `mcp__openclaw__openclaw`.

### Canary on `jorah-dev` (2026-11-19)

- **Install:** OpenClaw 2026.10.33 in a scratch prefix, run against `jorah-dev`'s profile. The patch is `~/scratch-dev/canary/canary.patch.json5`: it denies `openclaw`, turns cron off, and loads `jorah-projects` and `jorah-errands` with scratch state.
- **Backups:**
  - `~/backups/jorah-dev-pre-1033-20261119T1805.tar.gz` (mode 600);
  - `~/.openclaw-jorah-dev/openclaw.json.pre-canary-1033`.
- **Needed:** 10.33 won't start on 10.9 state ("agent database ... uses schema version 25"). `doctor --fix` migrates the databases.
  - It also changes config: `meta.lastTouchedVersion`, explicit `enabled` flags for anthropic and browser, removing the stale `jorah-github-standin` entry, disabling four skills, and stamping `wizard.*`.
  - It also updates the official plugins (above).
- **Passed:**
  - ready in 13 s;
  - config valid;
  - 12 plugins loaded, including acpx and duckduckgo 2026.10.33, `jorah-guard` ("matrix loaded; state ok"), `jorah-projects` and `jorah-errands`;
  - audit 0 critical. Of its 4 warnings, 2 are shared with live 10.9: `insecure_or_dangerous_flags`, `exec.security_full_configured`. 2 are new: `trusted_proxies_missing`, `installs_unpinned_npm_specs`. Live's other 2 (`trust_model.multi_user_heuristic`, `plugins.tools_reachable_permissive_policy`) don't appear;
  - a Haiku agent turn answered.
- **Blocks the live upgrade:** 10.33 renames the Tool Search wrapper from `tool_call` to `dispatch_action` (params `{id, args}`). The guard unwraps only `tool_call`, so it blocks `dispatch_action` as unknown, which would block every wrapped tool call. The guard needs to unwrap `dispatch_action` the same way. That goes to the guard's owner. After that, retest on the canary, including the planted unseen URL.
- **State after:** the canary unit `jorah-canary-1033` is stopped. `jorah-dev`'s state is still migrated to 10.33. Restore it from the backups above when the canary is done.

### Live deny applied (2026-11-20, under the 2026-11-19 yes)

- **Change:**
  - 07:00:34: the patch file was deployed to `/opt/jorah/config/pc/`. Its SHA-256 `ff347cb7…` matches `main`.
  - The config was backed up to `~/.openclaw-jorah/openclaw.json.pre-deny-openclaw-20261120` (mode 600).
  - Dry run: 1 update validated. It applied at 07:00:52.
  - The log shows `07:00:59 [reload] config hot reload applied (tools.deny)`. The Gateway did not restart: PID 966, started 06:59:24.
- **Incident: main was degraded for about 12 minutes.**
  - The PC had just woken from sleep. Startup found stale database leases ("owner-pid-dead") and ran a full integrity check on all three agents.
  - background recovered at 07:00:49 and deep at 07:00:55. Main was still preparing.
  - 0.3 s after the hot reload, the log shows: "agent database remains degraded agentId=main reason=\"Agent main startup preparation was superseded\"".
  - `/readyz` then reported `ready:false`, failing `agent-database:main`, and chat calls returned UNAVAILABLE. It didn't recover on its own.
  - The cause was applying the patch after the `[gateway] ready` log line but before `/readyz` was ready. **Rule: before a live config change, check that `/readyz` reports `"ready":true`, not the log line.** This matters most after a boot or a wake from sleep, because then the stale-lease integrity check runs.
  - The same day, the PC rebooted unexpectedly at 18:07: Windows Kernel-Power 41, down from about 15:40 to 18:07 [reported by the coordinating session]. That time the stale-lease integrity check passed cleanly.
- **Fix (Adam's yes 2026-11-20, "Yes"):**
  - 07:12:36: `systemctl start jorah-gateway-recycle.service` as root. Doctor was not run: this was supersession, not corruption, and doctor on 10.9 writes state.
  - The recycle reported "idle, restarting", then "ready after 25 s", and exited 0.
- **Checked at 07:13:42:**
  - `/readyz` returns `ready:true`, `coreReady:true`, `failing:[]`.
  - The new process is PID 2673, started 07:12:42.
  - `tools.deny` is `["nodes","computer","gateway","openclaw"]`.
  - Health is ok, and main's session store has 18 entries.
  - `jorah-guard` reports "matrix loaded; state ok". No degraded line since.
- **Not checked yet:**
  - that new claude-cli request shapes no longer offer `mcp__openclaw__openclaw`;
  - a Telegram turn;
  - the matrix line, which reaches live with the guard's next deploy.

### Target 2026.11.6 instead of 10.33 (Adam's choice 2026-11-22: "11.6 (from 11-26)")

**Decision:** the upgrade goes to `openclaw@2026.11.6` and the matching `@openclaw/acpx` and `@openclaw/duckduckgo-plugin`. This replaces the 10.33 target and its 2026-11-19 exception, which lapses unused. The steps in "Before the live upgrade" and "After the live upgrade, check" above apply, with 11.6 in place of 10.33, plus: a main turn on claude-cli that asks `deep` hands back without `cli_live_session_changed` on the canary **without** the transcript link.

**Exception to the 7-day rule (Adam, 2026-11-22: "make it an exeption, install it now"):**
- **Covers:** `openclaw@2026.11.6` (npm 2026-11-19T16:52Z), `@openclaw/acpx@2026.11.6` (14:29Z), `@openclaw/duckduckgo-plugin@2026.11.6` (14:31Z) and `@openclaw/ai@2026.11.6` (15:46Z), 3 days old on the day.
- **Why:** 11.6 carries exec-approval security fixes (#187884, #190024, 266a72e, 58997e1) and the Claude CLI transcript fix behind the `deep` hand-back failure. The 11.5 and 11.6 notes were read for what touches Jorah (record above).
- **Checks instead of the wait:** npm provenance and registry signatures, tarball integrity against the registry, the canary on `jorah-dev` first.
- **How:** `--min-release-age=7` with `--min-release-age-exclude` for the four names only. Any other package under 7 days old, including what `doctor --fix` pulls in for the plugins, is listed from the canary and goes to Adam before the live install.

**Canary on `jorah-dev`, 2026-11-22 17:39–18:00** [measured]:
- **Restore:** `jorah-dev` was still migrated to 10.33. That copy was moved, not deleted, to `~/backups/removed/jorah-dev-1033-migrated-20261122T1739`, and `~/backups/jorah-dev-pre-1033-20261119T1805.tar.gz` was extracted (10.9 state, like live).
- **Install:** `npm install -g --prefix ~/.jorah-canary/2026.11.6 openclaw@2026.11.6 --min-release-age=7 --min-release-age-exclude=openclaw --min-release-age-exclude=@openclaw/ai`: 361 packages; `npm audit signatures`: 517 registry signatures and 158 attestations verified. Under 7 days old in the tree: only `openclaw` and `@openclaw/ai`.
- **`doctor --fix --non-interactive`** (log `~/scratch-dev/canary/doctor-fix-1106.log`):
  - agent databases v25 → v38, with backups;
  - **retires `agents.defaults.heartbeat`**: it becomes the automation `heartbeat-main`. Heartbeat duplicate suppression and no-route skipping are gone, so repeated updates can be delivered. `heartbeat-main` keeps legacy sender-policy resolution, and loses `sessions_yield` and the unscoped automations tool;
  - updates `duckduckgo` and `acpx` to 2026.11.6 and removes the stale `jorah-github-standin` entry.
- **Fresh plugin dependencies** pulled in by doctor's installer, which ignores the 7-day rule, all under acpx: `@babel/runtime@7.29.15`, `bare-buffer@3.7.3`, `bare-fs@4.8.5`, `bare-url@2.5.8`, `express-rate-limit@8.7.5`, `hono@4.13.20` (published 2026-11-22), `jose@6.2.18`, `object-inspect@1.14.0`, `pkce-challenge@5.0.2`, `router@2.3.0`, `standardwebhooks@1.3.0`. These are not covered by the exception above. `npm audit signatures` can't run on that tree: it stops on OpenClaw's `@nolyfill/domexception` alias.
- **Config:** canary patch `~/scratch-dev/canary/canary-1106.patch.json5` (deny `openclaw`, cron off, plugins from `main` in `~/scratch-dev/canary/src-main`), then `config/pc/max-lane.patch.json5`. Config valid.
- **Start:** with `CLAUDE_CONFIG_DIR=~/.claude-jorah`, ready in 13 s, 11 plugins, `jorah-guard: matrix loaded; state ok`. Warnings at startup: "Deferred restart resume failed … Session database target changed outside captured discovery custody", once per agent.
- **`deep` hand-back without the link:** `~/.claude/projects` has no link for `-home-jorah-scratch-dev-workspace`. At 17:48:08, main (Haiku, claude-cli) called `sessions_spawn` to `deep` and ended its turn. `deep` (Opus, claude-cli) answered at 17:48:21. At 17:48:22 the result reached the same main Claude session in a fresh process ("Deep answered the canary: 17 × 23 = 391"). No `cli_live_session_changed`, no error.
- **Guard:**
  - claude-cli tool calls now log as `adam-typed`, where 10.9 logged `none`. Main found its tools through Claude Code's own `ToolSearch`, and the guard saw `tool_search`, then `sessions_spawn`.
  - On the embedded runtime, `background` (Sonnet 5.5) ran under **Code Mode**: `exec` running JavaScript, with the inner `web_search` checked under its own name.
  - A `web_fetch` to an unseen URL was blocked with the expected text.
- **Guard bug found, older than the upgrade:** a URL Adam typed in the message was blocked too. `before_agent_run` gets no `requester` in its context, on 10.9 (`buildAgentHookContext`, same call in `cli-runner`) as on 11.6. The owner fields are on the event (`channelId`, `senderId`, `senderIsOwner`). So the guard never records URLs Adam typed as seen. Follow-up for the guard's owner.
- **Audit:** 0 critical, 4 warnings, the same as the 10.33 canary.
- **Code Mode:** with `tools.codeMode` unset, 11.6 turns it on for models it marks as preferred ("auto"). Live has it unset.
- **apply_patch:** live has `tools.fs.workspaceOnly: true`, which contains `apply_patch` regardless of the new `tools.exec.applyPatch.workspaceOnly` default.
- **State after:** the canary Gateway is stopped; `jorah-dev` is migrated to 11.6. A throwaway probe plugin `~/scratch-dev/canary/ctx-probe` is in its config. Restore `jorah-dev` from the backup when the upgrade is done.

Findings that led here:

Source tier only. Full record: `docs/evidence/oc-upgrade-11.5-2026-11-22/README.md`.

- **The deep hand-back failure of 2026-11-22 16:57:48** [measured: live log and files]: just before it, the log says `claude-cli transcript check v4 miss … expectedPath=/home/jorah/.claude/projects/-home-jorah-workspace/…`. The transcript exists under `~/.claude-jorah/projects/-home-jorah-workspace/`. **The link from README "Conversation continuity" was never made on the PC**: `~/.claude/projects/` holds only `-opt-node-lib-node-modules-openclaw`. A missed check makes 10.9 pin the announce to main's old Claude process, so it fails with `cli_live_session_changed`. Since 2026-11-16: 280 misses, all for main's workspace. `setup-continuity.sh` would make the wrong link on the PC: it derives the key from `/opt/jorah/workspace`.
- **10.33 doesn't fix it** [verified: `src/agents/command/claude-cli-project-dir.ts` at each tag]: 10.9 and 10.33 look only in `$HOME/.claude/projects`. 11.5 and 11.6 follow `CLAUDE_CONFIG_DIR`. 11.4 and 10.33 are on the release branch without that change.
- **Eligible:** 11.5 at 2026-11-24 11:47 CET, 11.6 at 2026-11-26 18:26 CET. Neither needs an exception; the 10.33 exception above lapses if the target changes. 11.6 adds Claude CLI and subagent delivery fixes and exec-approval security fixes.
- **Breaking or default changes that touch Jorah** (detail in the record): hook shapes unchanged apart from added fields, `before_tool_call` fails closed after 15 s and `message_sending` fails open after 15 s; Tool Search wrapper unchanged from 10.33 (`dispatch_action`), and claude-cli turns now load OpenClaw tools through Tool Search by default; 13 SDK methods removed, none used by a Jorah plugin; host `apply_patch` may edit outside the workspace by default; user-installed plugins show unsandboxed native UI in the Control UI by default; pairing credentials move out of the shared database, so a rollback may need the HUD and iPhone paired again.
- **Interim fix, made 2026-11-22 17:22:17 CET on Adam's yes ("Yes, link it")** [measured]: as `jorah`, `ln -s /home/jorah/.claude-jorah/projects/-home-jorah-workspace /home/jorah/.claude/projects/-home-jorah-workspace`. Nothing was there before. `readlink` gives the target, and main's current transcript `effa46d1-….jsonl` reads through the link. No restart, no config change. Undo: remove the link. **Not checked yet:** no main turn had run by 17:23, so 0 misses since says nothing. After Adam's next main turn that asks `deep`, expect no `transcript check v4 miss` line and no `cli_live_session_changed` for the announce.

## Advisory watch, drift check and install policy, 2026-11-19

**Why:** GHSA-pw3x-g8v8-fvj2, published 2026-11-19, affects the live 2026.10.9. It was on OpenClaw's own advisory list but not in GitHub's global database, so `npm audit` said nothing. The research (`docs/plan/research/openclaw-security-landscape.md`, recommendations 4, 5 and 10) asked for three small pieces. Adam: "yes do all fixes in opus 5.5 high subsessions".

**(a) Advisory watch** (`services/jorah-watchdog/advisories.py`, `watchdog.py daily`):
- Every night at 03:40 (`jorah-daily-watch.timer`, between the 02:20 and 08:20 restarts), as `jorah-watchdog`, with the watchdog's bot.
- Reads `api.github.com/repos/openclaw/openclaw/security-advisories`: published only, most recently updated first, 100 a page. It stops at the first advisory it has already seen with the same update time. The first run reads all of them (about 723, 8 requests); later runs need about one. Sorting by update rather than publication also catches corrected ranges.
- Keeps every advisory's ranges for `openclaw` and `@openclaw/*`, and checks them all against the installed versions each night, so an upgrade into an old range is caught too.
- **Installed versions:**
  - `openclaw`, from `/opt/node/lib/node_modules/openclaw/package.json`, the file `openclaw --version` prints from. The installer checks that the two agree.
  - Every `@openclaw/*` package bundled inside it.
  - The npm-installed plugins in Jorah's state folder: `@openclaw/acpx` and `@openclaw/duckduckgo-plugin`, 2026.10.9 today [measured]. `jorah-watchdog` can't read them, so the root drift job lists their `package.json` name and version in its report.
  - Without a fresh list, the watch says "unknown".
- **Messages:** one per advisory that affects what runs: id, severity, summary, fixed versions, link. If more than 5 match at once, one message lists them, because that many probably means a misread.
  - A range it can't read counts as "may apply".
  - When the source is unreadable for a day (GitHub down, rate limit, unreadable version), it says "unknown" once, and says so again when it can read the list. It never reports that as "no advisories".
- **Network:** uid 999 falls under `meta skuid != 1000 accept` in `deploy/jorah-firewall.nft`. The live set is the same. As `jorah-watchdog`, a read of the list got 200 [measured 2026-11-19].

**(c) Drift check** (`services/jorah-watchdog/drift.py`, `jorah-drift.service`):
- Runs as root, because the rules files are in jorah's private home, but with no network (`PrivateNetwork=yes`) and only the read capability. `jorah-daily-watch.service` pulls it in and waits for it.
- **The manifest** (`/var/lib/jorah-drift/manifest.json`) gives, per file, the SHA-256 of its content in git and the commit it came from. It covers every file in `/opt/jorah` from git, plus `AGENTS.md`, `SOUL.md` and `IDENTITY.md` in the live workspaces of `main`, `deep` and `background`.
- **Report** (`report.json`, 0644, paths and hashes only): files changed since deployed, missing files, and files in `/opt/jorah` that no deploy recorded.
- **Messages:** the watchdog sends a report once per distinct finding, then once when everything matches again. No report for a day counts as "unknown".
- **Secrets:** it never opens a file that isn't in the manifest, and the manifest only takes paths from git. Secret names (`*.token`, `*.key`, `openclaw.json`, `.env` …) are refused even then. In live workspaces only the three rules files are allowed, never `USER.md`, `MEMORY.md` or `memory/`.
- **Keeping the manifest current:** build sessions deploy with `scripts/pc/deploy_reviewed.py`, which replaces the hand-typed `git archive | ssh … tar`:
  - `deploy_reviewed.py deploy <paths>`: deploys `HEAD` (it must be on `origin/main`), runs `sync`, and records every deployed file.
  - `deploy_reviewed.py record-live workspace/AGENTS.md=/home/jorah/workspace/AGENTS.md`: after copying a rules file into a live workspace (with a backup, as before).
  - `deploy_reviewed.py forget <paths>`: for files deleted from main.
  - The hashes come from git on the Mac. The PC refuses to record a file whose content differs, and then records nothing.
- **Baseline preview** [measured 2026-11-19, read-only]: 574 files hashed.
  - 569 match a version on main: 557 the newest, 12 an older deploy (for example `/opt/jorah/workspace/AGENTS.md`; the live copy is the newest).
  - None matches no commit.
  - Not in git: `.commit-site-readers`, `.deployed-commit`, `config/pc/max-lane.patch.json5.pre-2026-11-16`, `scripts/pc/._setup-permissions.sh`. They would be reported nightly until removed. On 2026-11-20, Adam said yes to archiving them: they are now in `/root/opt-jorah-leftovers-2026-11-20.tgz` (root 600) and gone from `/opt/jorah`.

**(b) Install policy** (`scripts/pc/install-policy.py`, `config/pc/install-policy.patch.json5`, `scripts/pc/setup-install-policy.sh`):
- **Contract** (2026.10.9 docs: `tools/skills-config.md` "Operator Install Policy", `help/troubleshooting.md`, `gateway/security/tool-permissions.md`, `gateway/configuration/hot-reload.md`):
  - OpenClaw runs the command, without a shell, after staging and before an install or update continues. It sends one JSON request (`protocolVersion: 1`) and expects `allow`, `warn` or `block`.
  - A block, crash, bad JSON or timeout stops the install. Neither `--force` nor `--acknowledge-install-policy-warning` gets past a block.
  - The command must be a root-owned regular file, not a symlink, in a safe folder.
  - Hot-reloaded, so no restart.
- **What it covers:** ClawHub, uploaded, Git and local skills; skill dependency installers; plugin installs and updates from the CLI, the Gateway, the Control UI and the agent's own plugin-install tool.
  - It does **not** cover `skill_workshop`. Learned skills are files the tool writes into `<state>/agents/<id>/agent/workshop-skills`, not installs. The docs say so (`tools/skills.md`: "Skill Workshop does not install into either location"). In the 2026.10.9 code, the workshop tool never calls the policy, unlike the plugin-install tool next to it [measured: `dist/openclaw-tools-*.mjs`].
  - So the workshop isn't blocked. The guard's cards and the drift check are what watch it.
  - OpenClaw's own upgrade isn't an install either: bundled plugins come with the npm package.
- **Policy:**
  - Allow only requests matching an entry in `/etc/jorah/install-allowlist.json`. The file must be root-owned and writable by nobody else; otherwise everything is blocked.
  - An entry names `targetType`, `targetName` and optionally `sourceKind`, `mode`, `requestedSpecifier`, `sourcePath`, plus a `note`.
  - The list is empty, so everything is blocked.
  - The command is `/usr/local/lib/jorah/install-policy` (root 755).
- **What it changes for build sessions:** a **new** plugin linked with `plugins install --link /opt/jorah/plugins/<x>`, as the `install-*.sh` scripts do, is blocked until Adam adds an entry, for example `{"targetType": "plugin", "targetName": "jorah-foo", "sourceKind": "local-path", "note": "Adam's yes, <date>"}`. Plugins already linked keep loading: new code in `/opt/jorah/plugins` is a deploy and a restart, not an install.
- `openclaw/clawscan` is not used: it runs scanners in Docker, and a block-by-default list doesn't need them.

**On the PC, 2026-11-20** (Adam's yes to steps 1–3, relayed verbatim by the coordinating session: "Yes to all questions"). Evidence: `docs/evidence/sec-hygiene-2026-11-20/`.
- **Deployed** from main with `deploy_reviewed.py deploy`: 20 files from `9260a08`, then the range fix from `74d581c`. `/var/lib/jorah-drift` was created by hand (root 755), because the unit's `StateDirectory=` only creates it once the unit is installed, and `record` doesn't create it.
- **Leftovers:** archived to `/root/opt-jorah-leftovers-2026-11-20.tgz` (root 600). The archive lists all four. They were then removed from `/opt/jorah`, followed by `sync`.
- **Baseline** [measured]: "match a version on main: 588 (558 the newest, 30 an older one; main is 9260a08)"; 0 match no commit, 0 not in git, 0 refused. Written with `--write`. A drift check right after: "checked 588 files: 0 changed, 0 missing, 0 unrecorded".
- **Range fix:** the first dry run matched 30 advisories. 29 of them used npm ranges (`>=2026.1.14-1 <2026.2.12`, `<=2026.2.19-2 || =2026.2.19`) that the comma-only parser couldn't read, so they counted as "may apply". After `74d581c`, all 719 ranges in the list parse, and only GHSA-pw3x-g8v8-fvj2 matches 2026.10.9 [measured].
- **Daily watch:** installed and enabled; next run Sat 2026-11-21 03:40 CET (plus up to 5 min). `--run` sent one message: GHSA-pw3x-g8v8-fvj2 (high), "Fixed in: 2026.10.33, 2026.11.4". A dry run afterwards had 0 messages due ("1 told so far").
- **Install policy files:** `/usr/local/lib/jorah/install-policy` (root 755) and `/etc/jorah/install-allowlist.json` (root 644, empty). A probe as jorah got `block`.
  - Scratch test on the throwaway `policy-scratch` profile: "Install blocked by policy" for the linked plugin `jorah-errands` and for the local skill `policy-probe`. `doctor --deep` reached the command and was blocked. Result: "scratch test: both installs blocked". The scratch profile and probe folder are gone.
- **Live config untouched:** `security.installPolicy.enabled` is still unset on the `jorah` profile.
- **Step 4 waits** for the upgrade (planned about 2026-11-26): the live patch (`setup-install-policy.sh`, hot reload) would block the npm updates of `@openclaw/acpx` and `@openclaw/duckduckgo-plugin`. It needs a Gateway turn from the coordinating session.

**Undo:** `install-daily-watch.sh --undo` (units; state and manifest stay), `setup-install-policy.sh --undo` (sets `enabled: false`; or restore `openclaw.json.pre-install-policy`).

## AGENTS.md whole in Jorah's context, 2026-11-20

OpenClaw injects at most `bootstrapMaxChars` (default 20,000) of each workspace bootstrap file and
cuts the rest. Main's `AGENTS.md` had reached 29,626 chars, so Jorah got 19,183 of it and lost the
rules from Learning "Undo" to the toolbox's step 2, founder answers and health-data rules included
(`docs/evidence/agents-md-budget/`). On Adam's yes of 2026-11-20 ("yes raise it, but can we also
distill it"):

- `workspace/AGENTS.md` is distilled to 25,395 chars, with no rule dropped (an independent review
  compared it line by line);
- `config/pc/bootstrap-limit.patch.json5` sets `agents.entries.main.bootstrapMaxChars` to 40,000,
  for main only (about 1,600 more tokens a turn, on the Max plan);
- `just check` runs `scripts/pc/tests/test_bootstrap_budget.py`, which fails when any bootstrap
  file of the three workspaces passes 90% of its limit. Raise the limit, or shorten the file,
  on Adam's yes.

**Deploy:** `scripts/pc/deploy_reviewed.py deploy config/pc/bootstrap-limit.patch.json5`, then as
jorah `openclaw --profile jorah config patch --file /opt/jorah/config/pc/bootstrap-limit.patch.json5
--dry-run` and without `--dry-run`; copy `workspace/AGENTS.md` to the live workspace (backup
`AGENTS.md.pre-distill`) and `record-live` it; `/readyz` ready, then
`systemctl start jorah-gateway-recycle.service` so new sessions get the whole file.
**Deployed 2026-11-20 18:21** (restart 18:21:32, `/readyz` ready, 0 truncation warnings after it, 10 before; evidence file). Open: Adam's Telegram check.
**Check:** the Gateway log since the restart has no "bootstrap file AGENTS.md is ... truncating"
line. After the OpenClaw 2026.10.33 upgrade, check that line again.
**Undo:** `openclaw --profile jorah config unset agents.entries.main.bootstrapMaxChars`, and copy
`AGENTS.md.pre-distill` back (then `record-live` the old file from its commit).

## Cron down after Windows Update restarts, 2026-11-21

**What happened [measured]:** Windows Update restarted the PC four times overnight, at 02:10,
02:12, 03:05 and 03:08 (System log event 1074 from `MoUsoCoreWorker.exe` and
`TrustedInstaller.exe`, then clean shutdowns: events 109 and 13, no Kernel-Power 41). WSL was not
shut down cleanly. The 02:12 restart cut the Gateway off right after it created
`state/openclaw.sqlite.cron-authority.lock`. The file stayed empty (0 bytes, dated 02:12:04), and
the journal of that boot lost its last seconds too. OpenClaw 2026.10.9 takes that lock with
`staleRecovery: "remove-if-definitely-stale"`. It only removes a stale lock when it can read the
lock's payload, so an empty file fails closed forever. From 02:13 every Gateway start logged
"[cron] failed to start: Cron receipt authority is unavailable", and `openclaw cron list` failed
with the same error. `/readyz` still said ready with `failing` []. Missed: the hourly
heartbeats of main, background and deep after 01:10, and the 03:00 memory dreaming. No reminders
of Adam's are cron jobs, so none were missed. Found by the toolbox deploy session at 07:33.

**Fix, on Adam's yes of 2026-11-21 ("Yes, fix it now"), 07:43:**
1. `/readyz` ready; `gateway-recycle.sh --dry-run` said idle; the lock was still the empty file.
2. `systemctl stop openclaw-gateway.service`. No OpenClaw process was left, and `fuser` showed
   nobody holding the lock.
3. Moved the empty lock to `/root/openclaw.sqlite.cron-authority.lock.empty-2026-11-21` (kept as
   evidence), then `sync`.
4. `systemctl start openclaw-gateway.service` at 07:43:58. Ready after 25 s, `NRestarts` 0.

**Result [measured]:**
- The Gateway wrote a new 222-byte lock and holds it.
- No cron or authority errors in the journal since the start.
- `openclaw cron status` shows enabled with 4 jobs, and `cron list` works.
- At 07:46 all four overdue jobs ran with status ok: heartbeat-main, Memory Dreaming Promotion
  (it had failed at 07:02 on 2026-11-20), heartbeat-background and heartbeat-deep.

OpenClaw's docs say "Do not delete lock files to force entry", because a live Gateway might own
the lock. That risk didn't apply here: the owner died with the restart three reboots earlier, and
the Gateway was stopped while the file was moved. Do the same only under the same checks: stopped
Gateway, no holder, empty file.

**Open:**
- An alarm when cron stops: "Cron watch" below, installed the same day.
- Windows Update can still restart the PC overnight and leave WSL state half written. Active hours
  are Adam's setting.
- After the 2026.10.33 upgrade, check whether an empty cron lock still fails closed.

## Cron watch: alerts when the Gateway's scheduler stops, 2026-11-21

**Why:** on 2026-11-21 cron failed at every Gateway start from 02:13 until the fix at 07:43 (see
above). `/readyz` still said `ready: true` with `failing: []`, so the watchdog stayed quiet, and the
hourly heartbeats and the 03:00 Memory Dreaming Promotion were missed without an alert.

**What:** `services/jorah-watchdog/cronwatch.py`, run by `jorah-cron-watch.service` before every
watchdog check, so every 5 minutes. The watchdog's unit pulls it in (`Wants=`) and waits for it
(`After=`), the way `jorah-daily-watch` pulls in the drift check; there is no new timer. It runs as
root, like the drift check, with no network, a read-only `/home` and only `CAP_DAC_READ_SEARCH`. It
reads two sources:
- **Receipts:** the newest `finished_at_ms` of each enabled heartbeat job (`payload_kind =
  'heartbeat'`) in `cron_run_receipts`, from `state/openclaw.sqlite`, opened with `?mode=ro` by
  `python3 -I`. It reads only times, statuses and job names, never prompts, outputs or error text.
- **Journal:** the Gateway's journal for its current start (`_SYSTEMD_INVOCATION_ID`), searched with
  `journalctl --grep` for "[cron] failed to start", "Cron maintenance failed" or "Cron receipt
  authority is unavailable". It first checks that this start has any journal line at all, because a
  wrong invocation id gives no lines rather than an error.

**Verdicts** (`/var/lib/jorah-cron-watch/report.json`, 0644, `cronwatch.py show`):
- **failing:** one of those lines, with no heartbeat finished after the newest one. Or no heartbeat
  has finished for 2.5 hours while the Gateway has been up longer than that, on the monotonic clock,
  so sleep doesn't count.
- **pending:** the Gateway isn't active, started less than 2 minutes ago, or has been up less than
  2.5 hours with no heartbeat in the last 2.5 hours (after a boot or the 6-hourly restart). The
  watchdog keeps what it had: no new alert and no "Back".
- **unknown:** the state or the journal can't be read, or systemd doesn't answer. It counts as down,
  never as fine.
- **ok:** a heartbeat finished in the last 2.5 hours, and no such line came after it.

**Alerts:** the watchdog's usual rules, named "the Gateway's scheduler (hourly heartbeats, Dreaming)":
- an alert after 10 minutes of failing or unknown, with the reason (the logged line, or the time of
  the newest heartbeat);
- a reminder every 6 hours, then "Back" once it is ok;
- a report older than 15 minutes, or no report, counts as unknown.

On 2026-11-21 the journal rule would have alerted about 10 minutes after the 02:13 start [inferred
from the journal times].

**Measured on the PC before building** (read-only, 2026-11-21 07:45–07:55):
- **Sandbox:** the check's three reads work in a throwaway `systemd-run` with the service's own
  sandbox settings: the state with `mode=ro` and `/home` read-only, the journal, and `systemctl show`.
- **Schedule:** the heartbeats run every hour, all day (`agents.defaults.heartbeat.every: 1h`, no
  active hours). The overnight gaps before 2026-11-20 were nights with the PC off.
- **journalctl:** `--grep` exits 1 with no output when nothing matches. A wrong invocation id exits 0
  with no output.
- **Clocks:** the monotonic clock, which the uptime rule uses so sleep doesn't count, ran about 3 %
  slow against the wall clock (1,667 s against about 1,716 s since the 07:43:58 start). That only
  makes the 2.5-hour rule a few minutes later. Messages show systemd's wall-clock start
  (`ActiveEnterTimestamp`).
- **Old Mac store:** `/Users/adam/.openclaw-jorah/cron/jobs.json` still has an enabled
  `heartbeat-main` row, last run 2026-11-05. The check takes the newest receipt per job name, so that
  row doesn't matter.

**Install** (each step after Adam's yes; `scripts/pc/install-cron-watch.sh`, as root):
1. `scripts/pc/deploy_reviewed.py deploy services/jorah-watchdog deploy/jorah-cron-watch.service
   deploy/jorah-watchdog.service scripts/pc/install-cron-watch.sh`.
2. `install-cron-watch.sh --dry-run`. Expected:
   - the units verify, and the diff of the watchdog's unit adds only the `Wants=`/`After=` lines;
   - in the service's sandbox, `cron: ok: newest heartbeat: …`;
   - then, as `jorah-watchdog`, `checks: gateway ok, runner ok, cron ok` and 0 messages due.
3. `install-cron-watch.sh` installs both units. It doesn't restart the Gateway or touch the
   watchdog's timer.
4. Within 5 minutes, `journalctl -u jorah-watchdog -n 3 -o cat` shows `cron ok`.

**Installed 2026-11-21 on Adam's yes ("Yes, deploy it")** [measured]
(`docs/evidence/cron-watch-2026-11-21/`):
- Deployed from `5e41e21` and `fb5ba77` with `deploy_reviewed.py`. The dry run was as expected
  above, then the install. The units in `/etc/systemd/system` match git by SHA-256.
- First timer-driven run, 08:18:50: `cron: ok: newest heartbeat: heartbeat-deep at 07:46`, then
  `checks: gateway ok, runner ok, cron ok`.
- Across the 08:20 Gateway restart: the 08:24:06 run searched the new start's journal and said
  `cron ok`. Nothing was sent.
- Not tested live: a real cron outage alert. Unit tests cover the failure line, the 2.5-hour rule,
  "pending" across restarts, unknown and stale reports.

**Not covered:**
- While the PC is off, nothing can be sent, as for the watchdog.
- A heartbeat that runs but ends in `error` counts as cron running. Failing heartbeats are a
  different problem, not watched here.
- Dreaming isn't checked on its own. It runs once a day, so the hourly heartbeats serve as the
  scheduler's pulse.

**Undo:** `install-cron-watch.sh --undo` removes `jorah-cron-watch.service`, and the watchdog stops
watching cron. The `Wants=` left in the watchdog's unit is ignored while the unit is gone.

## Back on the API key, and a switch in the HUD, 2026-11-21

Adam: "switch jorah to api now, also make it possible for me to switch between the max plan and the api back and forth inside the jorah hud". Design: `docs/adr/0009-hud-brain-switch.md`.

- **Applied by Claude, 2026-11-21** [measured]: `api-lane.patch.json5` now also pins deep back to the embedded runtime (`3ccf2eb`), deployed with `deploy_reviewed.py`. Dry run: 13 updates. Backup `openclaw.json.pre-api-lane-2026-11-21`. Applied by hot reload, then main's and deep's key order set to `anthropic:jorah-store`. `config validate` passes. Audit clean. 0 models on `claude-cli`.
- **Test turns** in throwaway sessions, deleted and forgotten afterwards: main (Haiku 5.5) and deep (Opus 5.5) both replied `PROBE-OK` with `runner: embedded` and `credential: profile`.
- **HUD switch:** a `BILLS` button in the top bar runs `scripts/pc/jorah-brain.sh`, which runs `/opt/jorah/scripts/pc/brain-lane.sh` over the setup key. The same works from a Mac Terminal: `scripts/pc/jorah-brain.sh status`, `api`, `max`, or `status --probe`.
- **Not checked yet:** the HUD's buttons, and `max` through the script, are Adam's test. The main chat may keep Max until `/new`.

## Still open

- Boot with nobody signed in: `openclaw-gateway.service` is enabled and the Windows task "Jorah WSL" keeps the distro up. A BIOS restart on 2026-11-07 brought the Gateway and voice back on their own [measured]; the full reboot test with the Mac closed is still owed.
- Semantic memory search: keyword-only until NAT networking with Tailscale inside the distro lets llama.cpp use its random loopback ports.
- Linger gives `jorah` a systemd user manager, so it could create user services. Shell runs in the sandbox, which can't reach it, but step 2 should check `systemctl --user list-units` as part of the soak.
- `/run/WSL/2_interop` stays world-writable, but the Gateway, voice and backup units all set `InaccessiblePaths=/run/WSL`. The installed Gateway unit matches `deploy/openclaw-gateway.service` [measured 2026-11-08].
- Delegated coding's sandbox, 2026-11-08: `socat` installed from Ubuntu's archive (`bubblewrap` was already there), and `scripts/pc/setup-permissions.sh`, the Linux version, wrote `/home/jorah/.claude-jorah/settings.json` (mode 600): sandbox on and failing closed, no unsandboxed commands, no network, home unreadable except `~/sandbox` and `~/work` (both mode 700). ACP stays off until a coding job is shown to run inside that sandbox [not tested: needs a real Claude Code run].
- Remote clients reach the PC through Serve routes owned by Windows, with `gateway.trustedProxies`: the Gateway on 443 and voice on 43211 since 2026-11-08 ("Serve is on"). The phone layer's route, 43213 → 127.0.0.1:43212, added 2026-11-15 (`docs/runbooks/phone.md`).
- `/usr/lib/wsl/drivers` is a read-only mount from Windows, kept for the GPU. It also puts Windows `.exe` files inside the distro.
- Public internet is open to the agent on web ports only, once `apply-talk.sh` has run (see "Talk from the iPhone").
- SEC-T17, the packet capture from P3's gate, the GPU spike (P1.3) and the 7-day soak.
- Windows SSH still allows password login, and the setup key gets removed when setup ends: `scripts/pc/close-setup-access.ps1`, test pass step 10.
