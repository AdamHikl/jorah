# P3 voice path, 2026-11-06

Voice from the Mac to Jorah's main session on the PC, built to source and install. No acceptance test ran: Adam runs them at the end. No secrets or tokens below.

## Tier reached

| Tier | State |
|---|---|
| Source | Done. `clients/mac-ear` error message now names the right runbook section |
| Tests | `just mac-ear`: 10 of 10 stand-in checks pass on the Mac. `just check` before commit |
| Install, PC | Done [measured]: `jorah-voice.service` enabled and active |
| Launch, PC | Done [measured]: `Listening on 127.0.0.1:43210` 13 s after start |
| Serve route | **Not up.** Serve isn't enabled on the tailnet, which needs Adam's admin consent |
| Mac client launch, signed-in acceptance | Not run. Adam's steps in `docs/runbooks/jorah-on-pc.md`, "Voice from the Mac" |

## What ran

**Files on the PC match `main` (43cd636).** The 18 files of `services/jorah-voice` and `deploy/jorah-voice.service` under `/opt/jorah` passed `sha256sum -c` against `git show HEAD:<file>`, with no extra files, and `/etc/systemd/system/jorah-voice.service` is byte-identical to the deployed unit. The lockfile was unchanged, so `uv sync` didn't run, and nothing was copied.

**Service, as root in the distro:**

```
systemctl enable --now jorah-voice
Created symlink /etc/systemd/system/multi-user.target.wants/jorah-voice.service → /etc/systemd/system/jorah-voice.service.
active
15:56:45 Started jorah-voice.service
15:56:46 Loading speech models
15:56:59 Listening on 127.0.0.1:43210
LISTEN 0 100 127.0.0.1:43210 0.0.0.0:* users:(("python",pid=4267,fd=22))
```

`openclaw-gateway` was active and wasn't touched. The token files in `/home/jorah/.config/jorah-voice/` are `jorah`'s, mode 600; their contents weren't read.

**Windows reaches it:** `Test-NetConnection 127.0.0.1 -Port 43210` returned `True` from Windows. `Get-NetTCPConnection` shows no Windows listener on 43210, so Serve's port doesn't clash with the distro's.

**Serve, on Windows Tailscale 1.104.2** (`rocket.tail1574a5.ts.net`, 100.115.240.14). Before: `tailscale serve status` and `tailscale funnel status` both `No serve config`.

```
tailscale serve --bg --yes --https=43210 http://127.0.0.1:43210
Serve is not enabled on your tailnet.
To enable, visit:
         https://login.tailscale.com/f/serve?node=<this node>
```

The command waits for that consent, an admin sign-in, so it was stopped, and `tailscale serve status` is still `No serve config`. `tailscale status --json` shows no `CertDomains`, so HTTPS certificates are probably off as well, and the consent page may turn them on. Port 43210, not 443, keeps 443 free for the Gateway's route for remote clients. HTTPS on the tailnet only, Funnel off.

**Mac client:** `just mac-ear` built `build/mac-ear` with Swift on macOS 27. It warns that `AVAudioPlayerNode.play()` and `AVAudioEngine.connect(_:to:format:)` are deprecated in macOS 27; they still work, and the stand-in checks pass. It reads its token from the Keychain (service `jorah-voice`, account `adam`) or `--token-file`, and refuses any host that isn't `localhost`, a `.ts.net` name or a 100.64/10 address.

## Not done here, on purpose

- No OpenClaw config change and no Gateway restart: another session owns the live Gateway.
- No firewall change: 43210 was already one of `jorah`'s own ports.
- Nothing installed.

## Open

- Adam's Serve consent, then the `tailscale serve` command and its `status` (runbook steps 1 and 2).
- The token in the Mac's Keychain (step 3).
- First real turn through the Gateway, and whether `x-openclaw-session-key: agent:main:main` lands in Telegram's session (steps 4 and 5).
- The source address Serve shows inside the distro wasn't checked. `jorah-voice` doesn't use it.
