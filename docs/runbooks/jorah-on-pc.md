# Jorah on the PC

One agent, one sandbox, one system: Jorah runs in the `jorah` WSL distro on the PC and keeps working with the Mac closed. Telegram, the iPhone and the Mac's mic are only ways to talk to it.

Steps marked [measured] ran on the PC on 2026-11-05. The rest haven't run yet, so stop and report if one behaves differently. Commands with a secret or a sign-in go in a terminal attached to no agent.

## Where it stands

| Step | What | State |
|---|---|---|
| 1 | Distro, user, Node, OpenClaw, firewall, speech models | Done [measured]. No Gateway started |
| 2 | Starts at boot with nobody signed in | Not run |
| 3 | Stage 0 settings for the PC, secrets store, new Telegram token | Not run |
| 4 | Move: stop the Mac Gateway, back up, restore here, sign in. **Never two Gateways** | Not run |
| 5 | Proof: Mac closed, PC rebooted, Telegram answers and recalls a saved fact | Not run |
| 6 | Speech feeds Jorah's main session, and `brain.py` goes | Not run |
| 7 | Pair the iPhone and the Mac as clients | Not run |

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
```

[measured] on the distro as it was built: these pieces ran one at a time, and the whole script hasn't run from a clean distro. That build started under the name `jorah-voice`, and WSL has no rename command, so its `DistributionName` under `HKCU\Software\Microsoft\Windows\CurrentVersion\Lxss` was edited.

## What the sandbox blocks

[measured] as user `jorah`, with `deploy/jorah-firewall.nft` loaded and after a distro restart:

- **Blocked:** Windows' loopback services (Ollama, sshd, Sunshine), the LAN and router, the PC's own LAN and tailnet addresses, other tailnet machines, link-local.
- **Allowed:** public internet, including Anthropic, Telegram, GitHub and npm. Narrowing this is still open.
- **Own ports:** 43181-43199 for the Gateway, 43210 for speech. Windows can reach a listener on them, which is what Tailscale Serve needs.
- **Can't change it:** `nft` refuses as `jorah`, and the OpenClaw and Node folders are read-only to it.

Mirrored networking in `.wslconfig` sends all loopback TCP through `loopback0`, so an interface rule can't tell local from Windows. That's why own ports are listed. Any other loopback port is refused, and a scratch Gateway must confirm OpenClaw needs nothing else.

## Still open

- Boot with nobody signed in is untested on Windows Home.
- `/run/WSL/2_interop` is world-writable. Launching Windows programs the normal way is off, but using the socket directly hasn't been tried.
- `/usr/lib/wsl/drivers` is a read-only mount from Windows, kept for the GPU.
- Public internet is open to the agent.
- SEC-T17, the packet capture from P3's gate, the GPU spike (P1.3) and the 7-day soak.
- Windows SSH still allows password login, and the setup key gets removed when setup ends.
