# Voice on the PC, with the Mac as mic and speaker

**Status: written, not yet run on the PC.** Steps marked [unverified] have never been tried, so stop and report if one behaves differently.

`jorah-voice` runs in its own WSL distro under its own Linux user. The distro has no Windows drives and can't start Windows programs. Windows only runs WSL and Tailscale. The Mac runs `mac-ear`, a small program with no third-party code, which only moves audio.

Run commands with a secret or a sign-in in a terminal attached to no agent.

## 1. Inventory (PC)

Paste `scripts/pc/p1-inventory.ps1` into PowerShell as Administrator. It reads names and versions and changes nothing. Bring the result back. Nothing below starts until it has been read, because old Merlin setup may still be on this PC.

## 2. Tailscale (both)

- **Mac:** open Tailscale and sign in.
- **PC:** install Tailscale for Windows, sign in to the same tailnet, then in Administrator PowerShell run `tailscale set --unattended=true`.
- **Check from the Mac:** `tailscale status` lists the PC as online.

## 3. The distro (PC, Administrator PowerShell)

```powershell
wsl --update
wsl --install -d Ubuntu-24.04 --name jorah-voice --no-launch
```

[unverified] Which Windows user owns this distro decides whether it starts with nobody signed in. P1's `jorah-svc` user is the target, and the inventory decides how to get there.

## 4. Set up inside the distro

From the Mac, once the setup SSH from P1.2 is on:

```bash
ssh <pc> "wsl -d jorah-voice -u root -- bash -s" < scripts/pc/wsl-voice-setup.sh
ssh <pc> "wsl --terminate jorah-voice"
```

## 5. Deploy the code (Mac)

```bash
git archive HEAD services/jorah-voice deploy | ssh <pc> "wsl -d jorah-voice -u root -- tar -x -C /opt/jorah-voice"
ssh <pc> "wsl -d jorah-voice -u root --cd /opt/jorah-voice/services/jorah-voice -- /home/jorah-voice/.local/bin/uv lock"
ssh <pc> "wsl -d jorah-voice -u jorah-voice --cd /opt/jorah-voice/services/jorah-voice -- env UV_PROJECT_ENVIRONMENT=/home/jorah-voice/.venv /home/jorah-voice/.local/bin/uv sync --frozen --no-build --no-install-project"
ssh <pc> "wsl -d jorah-voice -u root -- cp /opt/jorah-voice/deploy/jorah-voice.service /etc/systemd/system/"
```

[unverified] The first `uv lock` creates `uv.lock` on the PC. Bring it back and commit it, so later deploys use the same hashes. The code folder stays owned by root, so the service can't change its own code.

## 6. Log Jorah in (PC, Adam only)

In a terminal attached to no agent:

```powershell
wsl -d jorah-voice -u jorah-voice -- env CLAUDE_CONFIG_DIR=/home/jorah-voice/.claude-jorah /home/jorah-voice/.local/bin/claude auth login
```

## 7. Test it with no client

```powershell
wsl -d jorah-voice -u jorah-voice --cd /opt/jorah-voice/services/jorah-voice -- /home/jorah-voice/.venv/bin/python -m jorah_voice.check --output /tmp/reply.wav
```

Expected: a line from Jorah, first-token and whole-reply times, and `Wrote /tmp/reply.wav`. The first run downloads about 620 MB.

## 8. Open the way in (PC)

```powershell
wsl -d jorah-voice -u root -- systemctl enable --now jorah-voice
tailscale serve --bg --tcp 43210 tcp://localhost:43210
```

Expected: `wsl -d jorah-voice -u root -- systemctl status jorah-voice` shows `active`, and the log says `Listening on 127.0.0.1:43210`. [unverified] that Serve reaches WSL's loopback through Windows.

## 9. The Mac

Adam, in Terminal attached to no agent. Print the token on the PC:

```powershell
wsl -d jorah-voice -u jorah-voice -- cat /home/jorah-voice/.config/jorah-voice/token
```

Then on the Mac, which asks for the token at a hidden prompt:

```bash
security add-generic-password -s jorah-voice -a adam -w
```

Then build and run:

```bash
just mac-ear
build/mac-ear --url ws://<pc>.<tailnet>.ts.net:43210
```

macOS asks to allow the mic the first time. Expected: `● MIC OPEN`. Say "Hey, can you hear me?" and Jorah answers out loud. Say "goodbye" and it shows `○ MIC CLOSED` with timings.

## Still open before this counts as done

- Reaching the internet is allowed from the service, with no rule yet stopping it reaching the LAN. It needs an outbound rule that allows only Anthropic.
- Reboot with nobody signed in, as in P1's soak.
- SEC-T17 on this distro, and the packet capture from P3's gate (no audio leaves the PC).
- GPU, from P1.3.
