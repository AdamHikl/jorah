# Deployment topology and compatibility

Research for Jorah, 2026-11-02. Nothing here has been installed or changed. Every command is a plan for a later session and needs Adam's explicit yes where it changes accounts, services, schedules or data.

## How to read the labels

- `[verified: X]`: read directly from primary source X, or observed on this Mac today. `docs:` means `/opt/homebrew/lib/node_modules/openclaw/docs/` (OpenClaw 2026.10.9).
- `[docs-only: X]`: stated in a secondary source or a search snippet, and I could not open the primary page.
- `[inference]`: my reasoning. Not stated by any source.
- "Spike" means a short test a later session must run before relying on the claim.

Verified documentation is still not proof that it works in this setup. No PC exists in this plan yet, so everything about the PC is at best the "source check" evidence tier: no install, no launch, no acceptance.

The session's web search budget ran out before I could confirm some prices and two product facts. Those are listed in section 17. An independent check then corrected this file, see the Verification section at the end.

---

## 1. Recommendation

1. **Now, on this Mac:** create a standard macOS user `jorah` and move the Gateway there. This closes the largest known gap, Jorah's own `exec` running as Adam, and it rehearses the exact migration the PC will need. Also sign in to Tailscale, which is currently logged out. Adam's admin user runs Serve on the Mac, not `jorah` (fact 16).
2. **PC host:** Windows 11 Pro, because Fusion and Resolve need a desktop OS and the PC is the always-on GPU box.
3. **PC Gateway:** inside a dedicated WSL2 distro `jorah-gw`, not native Windows. Claude Code's sandbox does not run on native Windows. Worker container isolation is unsupported there too. Those two facts decide it.
4. **PC desktop:** a separate headless CLI node host in a Windows user `jorah-desk`, for GUI work and robot bridges. Windows computer control is labelled experimental by OpenClaw, so prefer scripts and APIs over pixels.
5. **Mac after the move:** a node, not a Gateway. Worker user `jorah` runs iOS builds through root-owned allowlisted wrappers. Adam's own user runs the OpenClaw app for voice wake and Talk, with `system.run` denied locally. iMessage stays here.
6. **Failover:** manual only. One Gateway owns state. A rescue bot on the Mac reports the PC is down and offers a wake and a runbook. No automatic takeover.
7. **Network:** Tailscale on the Windows host only, with **Run unattended** on, because otherwise the tailnet drops whenever nobody is signed in. Serve in front of a loopback Gateway, no public exposure. Tag the PC, keep the Mac as a user device, replace the default allow-all policy with narrow grants and policy tests.
8. **Hardware:** do not buy before running the PC check in section 15. GPU prices are badly inflated right now. An RTX 5090 is above EUR 5,000 in Germany and one aggregator shows about EUR 8,000, so 16 GB cards are the sane target unless a used 24 GB card turns up.

---

## 2. Facts that constrain the design

| # | Fact | Consequence | Evidence |
|---|---|---|---|
| 1 | Claude Code sandbox: supported on macOS, Linux, WSL2. Native Windows runs commands unsandboxed. WSL1 unsupported. | Native Windows Gateway loses the current delegated-task boundary. | [verified: https://code.claude.com/docs/en/sandboxing] |
| 2 | Default when the sandbox cannot start is to run unsandboxed. `sandbox.failIfUnavailable: true` refuses instead. Repo already sets it. | Keep that setting on the PC. A bad bubblewrap setup fails closed, which is correct. | [verified: same URL; `scripts/setup-permissions.sh` line 102] |
| 3 | Ubuntu 24.04+ AppArmor policy can block the user namespaces bubblewrap needs. Needs `bubblewrap` and `socat`. | Add to the PC setup checklist. | [verified: same URL] |
| 4 | Node worker container isolation is supported on Linux and macOS, unsupported on Windows. | Do not host OpenClaw sessions on a native Windows node. | [verified: docs:nodes/session-hosting.md] |
| 5 | Paired-device session runners support the embedded runtime and Codex `remote-exec`. "ACPX routes cannot dispatch to a paired device." | On the Claude CLI brain, Claude Code cannot be placed on the Mac by session hosting. iOS work needs node exec and wrappers. | [verified: docs:nodes/node-host.md] |
| 6 | Voice wake is documented for macOS (26+), iOS and Android. Windows Hub lists Talk push-to-talk and `talk.speak` commands, no wake word. | No built-in "Hey Jorah" on the PC. Mac is the first always-listening device. PC wake word is custom work (voice track). | [verified: docs:nodes/voicewake.md, docs:platforms/windows.md] |
| 7 | Windows and Linux `computer.act` is "experimental, direct SDK". Primary display only. No held keys or modifier-held clicks or drags. The `key` action rejects digit and punctuation keys. Node must start from the interactive desktop session. | GUI automation of Fusion's viewport by pixels will be limited on Windows. | [verified: docs:nodes/computer-use.md] |
| 8 | Windows Hub has two channels. `releases/latest` is stable v2026.9.8-1 (7 Oct). The newest pre-release is v2026.10.8-alpha.20 (28 Oct). The bundled doc's "stable" is correct. The doc also says OpenClaw stable releases mirror a Hub build, but the v2026.10.9 release assets list no Hub installer. | Use the stable channel if Hub is used at all, and check it against the pinned Gateway. Do not make it load-bearing, because it lags and is not needed for this design. | [verified: GitHub API `repos/openclaw/openclaw-windows-node/releases/latest` and `repos/openclaw/openclaw/releases/tags/v2026.10.9`] |
| 9 | One Gateway owns state and channels. Gateway startup enforces unique state-directory ownership. Never copy live SQLite. | No active-active. Migration requires stopping first. | [verified: docs:gateway/remote.md, docs:gateway/multiple-gateways.md, docs:install/backups.md] |
| 10 | Nodes dial out to the Gateway. | The Mac needs no inbound port for node work, and works from any network on the tailnet. | [verified: docs:gateway/remote.md] |
| 11 | Tailscale says do not run it on both Windows and WSL at once, and recommends the Windows host only. | Tailscale on the host. Gateway stays in WSL behind `tailscale serve`. | [verified: https://tailscale.com/kb/1295/install-windows-wsl2] |
| 12 | Tailscale SSH server runs on Linux and on macOS only in the open source CLI variant. Windows not listed. This Mac has the standalone notarized app (`io.tailscale.ipn.macsys`). | Use plain macOS Remote Login on the tailnet, not Tailscale SSH. | [verified: https://tailscale.com/kb/1193/tailscale-ssh; local `defaults read`] |
| 13 | Free Resolve lost Python scripting in 21.1. It moved to Studio. One outlet says interactive console scripting remains in free, and that external access and Workflow Integrations need Studio. Puget says all scripting went. Studio 21.1 also has a native MCP server. | Automated Resolve needs Studio either way. Headless ffmpeg route needs nothing. | [verified: https://www.blackmagicdesign.com/support/content/readme/59dd4eef1f4941c29fb8dc48b33f5c87]; [docs-only: https://digitalproduction.com/2026/09/08/resolve-21-1-adds-mcp-and-finally-gets-presets/, https://www.pugetsystems.com/blog/2026/09/10/how-davinci-resolve-free-v21-1-scripting-changes-affect-puget-bench/] |
| 14 | Fusion's own pages list Windows (10 22H2 or later) and macOS (14 or later), with no Linux desktop version. | Fusion does not run in WSL. It also runs on this Mac, which allows an interim path. | [docs-only: https://autodesk.com/de/support/technical/article/System-requirements-for-Autodesk-Fusion-360, https://www.autodesk.com/products/fusion-360/product-details] Search summary only. The product page returned 403 when opened. |
| 15 | The Windows Tailscale client runs in the user's login session and disconnects on sign-out or restart until someone signs in. **Run unattended** (`tailscale set --unattended=true`) keeps the device reachable with nobody signed in. It is Windows only. | Required on the PC, which has no autologon. Without it Serve, RDP and SSH over the tailnet all die at the first reboot. | [verified: https://tailscale.com/kb/1088/run-unattended] |
| 16 | The macOS Standalone client does not run before login. Its LocalAPI proof file is `root:admin` mode 0640 by design, so a standard user cannot read it. The CLI inside `Tailscale.app` uses XPC instead, and that path is untested from a second user. | No tailnet until someone logs in, so FileVault SSH unlock must come over the LAN. Do not assume a `jorah` Gateway can manage Serve. Run Serve from `adam` as externally managed, which is also the PC pattern. | [verified: https://tailscale.com/kb/1065/macos-variants; https://github.com/tailscale/tailscale/blob/main/safesocket/safesocket_darwin.go; local `ls -l /Library/Tailscale`]. XPC from a second user is [unverified] |

### This Mac today

All from read-only commands on 2026-11-02. [verified: local]

| Item | State | Meaning |
|---|---|---|
| Tailscale | 1.96.5, `BackendState: NeedsLogin`, 0 peers | Installed but not signed in. Must be done first. |
| Remote Login | Port 22 not listening | Off. Needed later for iMessage wrapper and backups. |
| Users | Only `adam` (admin, `_developer`, secure token on) | No separate user yet. |
| FileVault / SIP | On / enabled | Keep both. |
| `pmset` | AC `sleep 0`, `womp 1`, `tcpkeepalive 1`, `powernap 1`, Wake On Wireless supported | Never sleeps on AC with lid open. Closed lid is a separate matter, see section 8. |
| `/Users/adam` mode | `drwxr-x---+` | A second standard user cannot list it, subject to a real test. |
| OpenClaw.app | Not in `/Applications` | Only CLI is installed. Voice wake needs the app. |
| Disk use | `~/.openclaw-jorah` 2.0 GB (941 MB `tmp`, 648 MB `extensions`, 313 MB `models`, 3.5 MB `state`, 4.5 MB `agents`), `~/.claude-jorah` 31 MB, `~/.jorah-brain` 116 KB, `~/work` 1.4 GB | State itself is small. Fast to move. |
| `gateway.port` | Unset in config. The Gateway listens on `127.0.0.1:43181` as `adam` today, while the docs' default is 18789 | Set explicitly before moving. `openclaw node run` defaults to 18789, so always pass the port. |
| Tailscale LocalAPI | `/Library/Tailscale/sameuserproof-*` is `root:admin` 0640. The extension runs as root | `adam` can use the CLI. `jorah` cannot read this file. |
| Node | v26.13.0 | Meets the required 26.12.1+. |

---

## 3. Target topology

```
                         tailnet (WireGuard), no public ports
   iPhone + Watch ───┐
   (user devices)    │  wss://pc.<tailnet>.ts.net
   MacBook (adam) ───┼──────────────┐
    OpenClaw.app     │              ▼
    voice wake, Talk │   ┌───────────────── Windows PC (tag:jorah-pc) ─────────────────┐
    node, no exec    │   │ Tailscale on host; `tailscale serve` 443 -> 127.0.0.1:PORT  │
   MacBook (jorah) ──┘   │                                                             │
    headless node        │  user jorah-svc -> WSL2 distro jorah-gw (hardened)          │
    iOS wrappers         │    Gateway, Telegram, memory, Claude CLI + bubblewrap,      │
    iMessage bot         │    Docker sandbox, CUDA models                              │
    rescue bot           │                                                             │
         ▲               │  user jorah-desk -> console session when leased             │
         │ SSH 22 only   │    `openclaw node run` -> computer.act, Fusion, Resolve,    │
         └───────────────┤    robot-bridge MCP, COM ports, UVC cameras, ffmpeg.exe     │
          (imsg, backup) │                                                             │
                         │  user adam -> admin, owner's own use, holds no Jorah state  │
                         └─────────────────────────┬───────────────────────────────────┘
                                                   │ LAN, IoT Wi-Fi/VLAN
                                     ESP32 arm, tracked robot, ESP32-S3 mics
```

| Machine | Role | Runs |
|---|---|---|
| PC, WSL2 `jorah-gw` | Gateway. Single source of truth. | OpenClaw Gateway, channels, memory, cron, Claude CLI brain, delegated Claude Code, sandbox containers |
| PC, Windows `jorah-desk` | Desktop and hardware node | CLI node host, GUI apps, robot bridges |
| Mac, `adam` | Voice and presence node | OpenClaw.app: voice wake, Talk, notifications. Local exec approvals set to deny |
| Mac, `jorah` | iOS worker, iMessage, rescue | Headless node host, wrappers, `imsg`, rescue profile |
| iPhone, Watch | Mobile nodes | OpenClaw iOS app, Watch Talk |
| Android/Wear (if used) | Mobile nodes | OpenClaw Android and Wear OS |
| ESP32 devices | Not nodes | Talk to a bridge on the PC over LAN |

---

## 4. Decision: PC operating system and where the Gateway runs

**Pick: Windows 11 Pro host, Gateway in a dedicated WSL2 distro, desktop node on Windows.**

| Concern | Native Windows Gateway | **WSL2 Gateway + Windows node** | Dual-boot | Linux host, Windows VM | Mini-PC Gateway + Windows node |
|---|---|---|---|---|---|
| Claude Code sandbox | None. Unsandboxed [verified] | Bubblewrap [verified] | Linux side only | Yes | Yes |
| Worker container isolation | Unsupported [verified] | Yes, Linux [inference: WSL counts as Linux, spike] | Linux side only | Yes | Yes |
| OpenClaw Docker sandbox | Not assessed. Docs centre on Linux | Docker Engine inside distro [inference] | Linux side | Yes | Yes |
| GPU for AI | Best native | CUDA works through the Windows driver. Limits: partial NVML, no GPU selection by index, no OpenGL-CUDA interop, pinned memory limits [verified: https://docs.nvidia.com/cuda/wsl-user-guide/index.html] | Native, one OS at a time | Needs passthrough, a second GPU helps [inference] | Remote only |
| NVENC | Yes | Likely works. 2026 reports show `h264_nvenc` from a dynamically linked ffmpeg and `nvh264enc` in GStreamer, with `libnvidia-encode.so.1` in `/usr/lib/wsl/lib`. Statically linked ffmpeg fails [docs-only: https://github.com/NoMercy-Entertainment/nomercy-ffmpeg/issues/42, https://github.com/games-on-whales/wolf/discussions/448]. No NVIDIA support statement found. Spike | One OS at a time | Depends on passthrough | No |
| Mic and speakers | Native | WSLg bridges audio through its RDP link [verified: https://github.com/microsoft/wslg]. Do not use for wake word [inference] | One OS | VM audio | Separate |
| USB/serial to ESP32 | Native COM ports | usbipd-win, attach after each reboot or `--auto-attach`; device leaves Windows while attached [verified: https://learn.microsoft.com/en-us/windows/wsl/connect-usb] | One OS | Passthrough | Plug into mini-PC |
| Fusion, Resolve GUI | Yes | Yes, in the Windows node | Windows side only, then Gateway is down or the apps are | In VM, GPU pain | Yes on the PC |
| Reliability 24/7 | Good on paper. Task Scheduler with S4U runs before login [verified: docs:platforms/windows.md] | Known idle-shutdown risk (see below). Windows reboots take it down | Poor: rebooting moves everything | Good, but VM GPU is fragile | Best |
| Isolation of agent from Adam's data | Runs as a Windows user. Only NTFS ACLs | Separate kernel namespace, separate filesystem. Interop and automount can be switched off [verified: https://learn.microsoft.com/en-us/windows/wsl/wsl-config]. Not a hard boundary [inference] | Good | Strong | Strongest |
| Upfront cost | 0 | 0 | 0 | Second GPU maybe | Mini-PC, price not confirmed |

**Why:** the sandbox and worker isolation exist only on the Linux or macOS side. Fusion and Resolve exist only on the Windows or macOS side. WSL2 is the only option that gets both on one machine without a reboot or a second box. OpenClaw also describes WSL2 as its most Linux-compatible Windows runtime [verified: docs:platforms/windows.md].

**Runner-up:** a small always-on Linux box for the Gateway, with the Windows PC as GPU and desktop node. It is more reliable and better isolated, and needs extra hardware. The migration runbook is the same, so this can be swapped in later.

**What would change the decision:**
- The 7-day soak in step C3 fails, for example the distro keeps being killed.
- The PC is a daily gaming machine that reboots or runs out of GPU often.
- Spike S2 (Serve to WSL loopback) cannot be made to work.
- Adam's PC turns out to be unable to run WSL2 well, or has an AMD GPU and local AI matters. CUDA-on-WSL is NVIDIA's path.

**Why not the Windows Hub "Set up locally":** it creates an app-owned `OpenClawGateway` distro [verified: docs:platforms/windows.md]. We need our own hardening, profile, port and user, and Hub's stable channel lags its pre-releases. Hub can still connect to our Gateway if wanted.

### WSL reliability hardening

Open issue microsoft/WSL#13416: the VM stops about 15 to 20 seconds after the last terminal closes, despite running systemd services. Reports span from 2.4.13 to 2.7.3, no Microsoft fix was reported, and the reported workarounds are community ones [verified: https://github.com/microsoft/WSL/issues/13416]. Current WSL stable is 3.0.3 (9 Oct), 3.0.4 pre-release (20 Oct), and the 3.0.3 and 3.0.4 notes do not mention it [verified: https://github.com/microsoft/WSL/releases]. So assume it can still bite, and test. The issue thread also lists `vmIdleTimeout` among the settings that did not help, so the soak has to prove `instanceIdleTimeout=-1` and the boot chain.

`%UserProfile%\.wslconfig` for `jorah-svc`. All keys documented, values mine. [verified keys: https://learn.microsoft.com/en-us/windows/wsl/wsl-config]

```ini
[wsl2]
memory=24GB              ; default is 50% of RAM. Size to the PC.
swap=8GB
networkingMode=nat       ; keeps the Gateway off the LAN by default
firewall=true
guiApplications=false
nestedVirtualization=false
vmIdleTimeout=-1         ; -1 not documented for this key, and issue 13416 reports the key does not help. Do not rely on it.

[general]
instanceIdleTimeout=-1   ; documented: -1 disables auto shutdown

[experimental]
sparseVhd=true           ; only affects VHDs created after this is set, so write it before creating the distro
```

`/etc/wsl.conf` in `jorah-gw`:

```ini
[boot]
systemd=true
[automount]
enabled=false            ; no C:\ inside the distro
mountFsTab=true          ; only what /etc/fstab names
[interop]
enabled=false            ; the distro cannot launch Windows programs
appendWindowsPath=false
[user]
default=jorah
```

Mount only a media folder in `/etc/fstab`, for example `D:\\jorah-media /mnt/media drvfs rw,noatime 0 0` [inference: syntax follows `mountFsTab` docs, spike].

Boot chain per the doc, adapted to our distro and user [verified: docs:platforms/windows.md]:

```bash
# Inside jorah-gw
sudo apt-get install -y dbus-x11 bubblewrap socat
sudo loginctl enable-linger jorah
openclaw --profile jorah gateway install
```

```powershell
# Admin PowerShell. /ru must be the distro's owning user, not SYSTEM.
schtasks /create /tn "JorahWSLBoot" /tr "wsl.exe -d jorah-gw --exec dbus-launch true" /sc onstart /ru jorah-svc
```

Fallback if the distro still idles out: a task running `wsl.exe -d jorah-gw --exec sleep infinity` [verified as a reported community workaround: issue 13416]. Run it from Windows, because interop is off inside. That report covers only about 20 minutes of uptime, and the same thread says a plain `sleep infinity` system service inside the distro does not help.

Check bubblewrap inside the distro: `sysctl kernel.apparmor_restrict_unprivileged_userns`. If `1`, add the AppArmor profile from the Claude Code sandbox docs.

---

## 5. Decision: Windows users and who owns the console

**Pick: three Windows accounts, GUI work by lease.**

| User | Rights | Owns | Autologon |
|---|---|---|---|
| `adam` | Admin | Adam's own use, BitLocker recovery, updates | No |
| `jorah-svc` | Standard | The WSL distro and boot task. VHDX under its own profile | No, runs from a scheduled task with stored password |
| `jorah-desk` | Standard | Node host, Fusion, Resolve, COM access | No at first |

Facts:
- Distros are per Windows user, not visible to SYSTEM [verified: docs:platforms/windows.md].
- GUI automation has no desktop to work with when the session is locked or a Remote Desktop session is closed. `tscon <id> /dest:console` is the usual fix, it leaves the machine unlocked, and resolution can fall back to low values [docs-only: https://support.smartbear.com/testcomplete/docs/testing-with/running/via-rdp/keeping-computer-unlocked.html, https://www.edgeverve.com/assistedge/knowledge-base/RPA19.1/Troubleshooting/Running_UI_RDPdisconnected.htm]. Vendor docs, not Microsoft.
- Autologon stores the password as an LSA secret that any admin can decrypt [verified: https://learn.microsoft.com/en-us/sysinternals/downloads/autologon].
- OpenClaw node hosts keep per-user interactive tasks for desktop access [verified: docs:platforms/windows.md].
- The Windows `computer.act` fulfiller controls only the primary display, and it cannot detect a same-geometry display swap within a session. The docs advise a stable single-display session [verified: docs:nodes/computer-use.md]. So do not add or remove a monitor during a leased job.
- Windows client editions normally allow one active interactive session, so an RDP login as another user would likely disconnect the leased console [unverified: standard behaviour, not checked against a Microsoft source]. Use SSH for admin while a GUI job runs.

**The lease model** [inference]: one interactive console at a time. If Adam is using the PC, GUI jobs wait or run on the Mac, which can also run Fusion and Resolve. When a GUI job needs the desktop, Jorah asks on Telegram, Adam says yes, a small admin-scoped task moves `jorah-desk` to the console, and the job runs. When it finishes, the session is locked. This matches "preview and get an explicit yes" and avoids leaving an unlocked desktop in a room.

Add an HDMI dummy plug on the GPU so the console keeps a real resolution with no monitor [inference]. Price not confirmed, it is a low-cost item.

**Runner-up:** autologon of `jorah-desk` plus always-unlocked console. More autonomous, and anyone in the room gets a logged-in session. Revisit once a robot or overnight job needs unattended GUI.

**What would change it:** if the PC is effectively headless, dedicated to Jorah, in a locked room.

---

## 6. Decision: network and Tailscale

**Pick: Tailscale on the Windows host. `tailscale serve` to the WSL loopback Gateway. Tag the PC. Grants plus policy tests.**

Options compared:

| | A. Tailscale on Windows host (pick) | B. Tailscale inside WSL only | C. Both |
|---|---|---|---|
| Vendor advice | Recommended [verified] | Described as advanced [verified] | Told not to [verified] |
| OpenClaw managed Serve | No. Must use "externally managed Serve" with `gateway.trustedProxies`. No identity headers. Token stays required [verified: docs:gateway/tailscale.md] | Yes, native | n/a |
| Reach host when WSL is dead | Yes, this is why | No. Recovery needs physical access | n/a |
| Separate tailnet identity for Gateway | No | Yes | n/a |

The Gateway stays on loopback. In NAT mode WSL forwards localhost to the host by default and the LAN cannot reach it [verified: https://learn.microsoft.com/en-us/windows/wsl/wsl-config, https://learn.microsoft.com/en-us/windows/wsl/networking].

```powershell
# On Windows, as the tailnet device owner
tailscale set --unattended=true
tailscale serve --bg --https=443 http://127.0.0.1:<gateway-port>
```

The Serve syntax is documented, `--bg` routes survive a reboot, and proxy targets must be `http://127.0.0.1` [verified: https://tailscale.com/kb/1242/tailscale-serve; local `tailscale serve --help`]. Unattended mode is fact 15.

```json5
// OpenClaw, in WSL. Keep token auth. Add 127.0.0.1 only if the Serve hop arrives as loopback.
{ gateway: { bind: "loopback", port: <fixed>, trustedProxies: ["127.0.0.1"], auth: { mode: "token" } } }
```

Doc warning: a loopback entry trusts same-host processes to supply proxy attribution, so token auth must stay on [verified: docs:gateway/tailscale.md]. On a WSL NAT setup "same host" includes anything on Windows that can reach localhost [inference]. Tailscale identity headers do not authenticate node-role connections anyway, so nodes use token or device pairing either way [verified: docs:nodes/node-host.md].

Direct loopback connections can be auto-approved for pairing [verified: docs:network.md]. A connection relayed through WSL's localhost forwarding may look like loopback to the Gateway, so a Windows process holding the token might pair without an approval prompt [inference]. The docs' own test rig notes that the Gateway silently approves loopback node-device pairing, while the node's command surface still needs approval [verified: docs:nodes/computer-use.md]. Check this in S2.

**Spike S2:** confirm WebSocket through Serve into WSL, a node join, whether the Windows-side node triggers an approval, and the iOS app showing **Full** access. Run it with nobody signed in except what the boot task starts, and after a reboot. It must prove that `tailscaled` and the `jorah-desk` node can reach `jorah-svc`'s VM through localhost. The docs describe forwarding from the VM to the host, but I found no source covering a different Windows user or a non-interactive owner [unverified]. If it fails, fall back to option B with Windows OpenSSH reachable another way, or to an SSH tunnel as the universal fallback.

Plan limits: Personal is free and non-commercial, up to 6 users, unlimited user devices, 50 tagged resources, up to 3 ACL groups, basic SSH up to 5 hosts. Extra tagged resources cost $1 per month each. Standard is $8 per user per month [verified: https://tailscale.com/pricing]. If Jorah becomes a business, this tailnet needs a paid plan.

Tags: a device has a user identity or a tag identity, never both. Tags are meant for servers. Tagged devices get no key expiry by default and can SSH only to other tagged devices [verified: https://tailscale.com/kb/1068/tags]. So:

- Tag the PC `tag:jorah-pc`.
- Keep Mac and phone as user devices. Pick out the Mac by a `hosts` entry.
- Tailscale identity is per machine, not per OS user. Anything running as `jorah` on the Mac has the Mac's tailnet access [inference]. Keep the Mac's grants narrow too.

Policy (replace the default allow-all). Addresses and login are placeholders. [verified syntax: https://tailscale.com/kb/1324/grants, https://tailscale.com/kb/1337/policy-syntax; host aliases in grants: https://tailscale.com/docs/reference/targets-and-selectors]

```json5
{
  "groups": { "group:owner": ["adam@example.com"] },
  "tagOwners": { "tag:jorah-pc": ["group:owner"] },
  "hosts": { "adam-mac": "100.x.y.z", "adam-iphone": "100.x.y.w" },
  "grants": [
    // Owner devices reach the Gateway and PC admin ports
    { "src": ["group:owner"], "dst": ["tag:jorah-pc"], "ip": ["tcp:443", "tcp:22", "tcp:3389"] },
    // The PC may reach only SSH on the Mac (imsg wrapper, backups)
    { "src": ["tag:jorah-pc"], "dst": ["adam-mac"], "ip": ["tcp:22"] },
    // Interim only, while the Gateway is on the Mac: remove at cutover
    { "src": ["adam-iphone"], "dst": ["adam-mac"], "ip": ["tcp:443"] }
  ],
  "tests": [
    { "src": "adam@example.com", "accept": ["tag:jorah-pc:443"] },
    { "src": "tag:jorah-pc", "accept": ["adam-mac:22"], "deny": ["adam-mac:5900", "adam-mac:445", "adam-iphone:443"] }
  ]
}
```

Tests run on every policy change and block a bad update [verified: policy-syntax page]. If portals are used later, add their ports: OpenClaw portals use separate Serve ports and grants must allow them [verified: docs:gateway/tailscale.md].

**Do not** use Funnel, router port forwards, or Cloudflare for the Gateway. Telegram long polling needs no inbound access [verified: docs:channels/telegram/transports.md]. ESP32 devices stay off the tailnet on a separate Wi-Fi network. The bridge on the PC talks to them [inference].

Cost: EUR 0 on Personal.

**Runner-up:** bind to tailnet with direct `ws://`. Simple but plaintext, and the iOS app limits plaintext setups [verified: docs:platforms/ios.md].

---

## 7. Interim boundary: dedicated macOS user

**Pick: standard user `jorah` on this Mac, Gateway moved there now. Do this before any new capability.**

**Why:** `exec` currently runs as Adam, with read access to everything Adam can read. A separate non-admin account is the cheapest real boundary macOS offers. It also rehearses the PC move using the same backup and restore flow.

**Runner-up:** OpenClaw's Docker sandbox for `exec` under Adam's user. It does nothing for plugins or the Gateway itself, which stay in-process with the host [verified: docs:gateway/sandboxing/supported-capability-matrix.md]. Do it as a second layer, not instead.

**Cost:** EUR 0, one to two hours.

**What it does and does not protect:**

| Protected | Not protected |
|---|---|
| Adam's home, Documents, SSH keys, `~/.claude` | Network egress. `jorah` can reach the internet and anything the Mac can reach on the tailnet |
| Adam's login Keychain | World-readable system files, `/Applications`, `/opt/homebrew` |
| Adam's Messages database | Local privilege escalation bugs |
| Writing to Homebrew and global npm (owned by `adam`) | Anything Adam passes to it through a channel |
| | Loopback ports opened by Adam's processes |

### Steps (need Adam's explicit yes; all require admin)

1. **Prepare.** Commit the repo, which has no commits yet. Run `./scripts/snapshot-brain.sh`.
2. **Create the user.** Password prompted, not on the command line.
   ```bash
   sudo sysadminctl -addUser jorah -fullName "Jorah" -home /Users/jorah -password -
   sudo createhomedir -c -u jorah 2>/dev/null || true
   sudo dseditgroup -o edit -a jorah -t user _developer   # Xcode tools without admin password
   dscl . -read /Groups/admin GroupMembership              # jorah must NOT be listed
   fdesetup list                                           # note whether jorah can unlock FileVault
   ```
   `DevToolsSecurity` confirms what `_developer` grants [verified: `man DevToolsSecurity`]. Log in once through Fast User Switching to finish Setup Assistant and create the login Keychain.
3. **Prove the boundary before moving anything.**
   ```bash
   sudo -iu jorah ls /Users/adam/Documents        # expected: Permission denied
   sudo -iu jorah cat /Users/adam/.zshrc          # expected: Permission denied
   sudo -iu jorah test -w /opt/homebrew/bin; echo $?   # expected: 1
   ```
4. **Stop and back up.** Stop the foreground Gateway in Adam's terminal.
   ```bash
   mkdir -p ~/Backups/openclaw
   openclaw --profile jorah backup create --output ~/Backups/openclaw --verify
   ```
5. **Restore into the new user.** Copy the archive to `/Users/Shared`, restrict it to `jorah`, restore to staging, activate using `manifest.json`. Doctor adjusts the rest. [verified: docs:install/migrating.md]
   ```bash
   sudo -iu jorah
   openclaw --profile jorah backup restore /Users/Shared/<archive>.tar.gz --target ~/openclaw-restored
   # Move state to ~/.openclaw-jorah per manifest.json
   git clone <repo> ~/jorah
   # Move restored workspace into ~/jorah/workspace
   ```
6. **Re-apply config so paths point at the new home.** `scripts/configure.sh` sets absolute paths from `$HOME` and `$REPO`, and calls `setup-permissions.sh`, `setup-learning.sh`, `setup-continuity.sh`. [verified: repo]
7. **Log Claude in as `jorah`.** `CLAUDE_CONFIG_DIR=$HOME/.claude-jorah claude auth login`, then the `models auth login` line from the README. Keychain entries do not move between users. Do this in the GUI session. If the Keychain is locked, as in SSH, Claude Code falls back to `.credentials.json` mode 0600 under `CLAUDE_CONFIG_DIR` [verified: https://code.claude.com/docs/en/authentication].
8. **Re-download the embedding model.** The `tools` tree is regenerable and excluded from archives [verified: `backup create --dry-run` today].
9. **Start.** Foreground first, per the README. Then `openclaw --profile jorah gateway install`, which creates a per-user LaunchAgent `ai.openclaw.jorah` [verified: docs:gateway/index.md]. Only after Adam approves running it as a service.
10. **Reset execution policy.** Set exec approvals and tool policy with the security track's values. The boundary is not a licence for `full` mode.
11. **Remove the old copy only after acceptance.** Keep `~/.openclaw-jorah` under Adam, stopped, for two weeks.

### Acceptance evidence

| Test | Expected |
|---|---|
| Telegram message to the bot | Reply, no new pairing request |
| Ask Jorah to run `whoami` and `ls /Users/adam` | `jorah`, Permission denied |
| `/acp doctor` then a delegated task | Works in sandbox, cannot read outside |
| `./scripts/switch-brain.sh status --probe` as `jorah` | `ACTIVE ROUTE: cli` |
| Memory search for a known fact | Found |
| `openclaw --profile jorah status` | One Gateway, correct state dir |
| Reboot, then login path | See below |

**Reboot behaviour:** FileVault means nothing runs until someone unlocks. macOS 26+ can unlock FileVault over SSH when Remote Login was on before the reboot, using an administrator's password, on Apple silicon. Wi-Fi was reported working as of 26.5 [docs-only: https://www.jeffgeerling.com/blog/2025/you-can-finally-manage-macs-filevault-remotely-tahoe/]. Spike on this Mac. The Standalone Tailscale client does not run before login [verified: https://tailscale.com/kb/1065/macos-variants], so this unlock cannot come over the tailnet [inference]. It needs the LAN, or another route in. After unlock, `jorah`'s LaunchAgent still needs a login session. A custom LaunchDaemon with `UserName` is possible with `OPENCLAW_SERVICE_REPAIR_POLICY=external` [verified: docs:gateway/index.md] but it has no GUI context, so no permission prompts. Keep the supported LaunchAgent for the interim, since Adam is nearby during this phase.

**Open points to test:**
- Tailscale after a session change: does the tunnel stay up for a `jorah` LaunchAgent when `adam` logs out, and does `jorah` need its own Tailscale app running? No source covers this [unverified].
- Docker Desktop is set up for `adam`. `jorah` cannot reach that engine's socket [inference]. If `jorah` needs containers, test a per-user engine. Worker container isolation tries `docker` then `podman` [verified: docs:nodes/session-hosting.md].
- Claude transcript link: `setup-continuity.sh` recreates it under the new home. The Claude project key derives from the workspace path, so CLI resume history starts fresh unless the old folder is copied to the new key [inference: repo README describes per-workspace keys].

---

## 8. The Mac after the move

### Sleep, lid, wake

| Situation | Behaviour | Evidence |
|---|---|---|
| Lid open, on power | Stays awake. This Mac is already `sleep 0` on AC | [verified: `pmset -g`] |
| Lid closed, power + external display + keyboard and mouse approved | Runs. Apple requires the display, mouse and keyboard to be allowed first | [verified: https://support.apple.com/en-us/102282]; [docs-only: https://support.apple.com/en-us/102501 for power] |
| Lid closed, no display | Sleeps. Tailscale does not hold it awake | [inference, standard behaviour] |
| `pmset disablesleep 1` | Not in `man pmset`, though `pmset -g` shows a `SleepDisabled` flag. Unsupported, possible heat in a closed laptop | [verified: local man page]. Do not use |
| Asleep | Tailscale cannot wake it. Nodes disconnect | [inference] |
| Wake | `womp 1`, Wake On Wireless reported supported. Sleep proxy needed across subnets | [verified: local; docs-only: https://support.apple.com/guide/remote-desktop/sleep-shut-down-log-out-or-restart-a-computer-apd5535ee19/mac] |

**Pick: when home, dock it. Power, Ethernet adapter, external monitor or a dummy plug, keyboard and mouse approved once. Then lid closed works and the Mac is a real worker. When Adam leaves, it becomes a roaming node.**

Wake-on-LAN packets need a same-LAN sender. WSL NAT cannot broadcast to the LAN [inference]. So the Windows node sends it. Spike: Ethernet and Wi-Fi magic packets on this Mac.

Battery: macOS 26.4+ on Apple silicon has a Charge Limit under Battery, from 80 to 100 percent [verified: https://support.apple.com/en-us/102338]. Set it to 80 for a docked laptop. Cost: dummy plug and dock if needed, not priced.

**Handling a missing Mac:** docs say a hosted session waits while the device is offline and a dormant node's environment is treated as gone after 14 days; pairing remains [verified: docs:nodes/session-hosting.md]. Jorah should report "waiting for the Mac", never pretend work happened.

**What would change it:** if iOS or iMessage must be reliable while the MacBook travels, buy a Mac mini. Apple's page shows M6 and M5 Pro as current, with a EUR 949 financing example that I cannot confirm as the start price [verified: https://www.apple.com/de/mac-mini/]. The smallest shop configuration is M6, 16 GB, 256 GB, but the page text I could read shows no price [verified: https://www.apple.com/de/shop/buy-mac/mac-mini]. Alza.at listed an older M4 16/256 at EUR 628.90 [docs-only: https://www.alza.at/cheap-mac-mini/18854903.htm]. OpenClaw's docs also favour a dedicated Mac for iMessage [verified: docs:channels/imessage/private-api.md].

### What must stay on a Mac

| Capability | Why | Which user |
|---|---|---|
| iMessage | Needs a signed-in Messages host. Linux and Windows cannot do the local path [verified: docs:install/macos-vm.md] | `jorah` with a bot Apple ID |
| Xcode, signing, simulators | macOS only | `jorah` |
| Apple Speech voice wake | App needs macOS 26+, on-device recognizer [verified: docs:platforms/mac/voicewake.md] | `adam` |
| Mac camera, screen, Calendar, Reminders, Photos via node | Per-user TCC grants [verified: docs:nodes/command-policy.md for commands] | `adam` only if Adam opts in |
| Rescue bot | Must survive the PC being down | `jorah` |

### iMessage

**Pick: a bot Apple ID in `jorah`, basic mode, SIP on.** Adam texts Jorah. Jorah has no access to Adam's `chat.db`.

- Remote wrapper pattern from the Gateway: `cliPath` to a script running `ssh -T jorah@mac imsg "$@"`, plus `remoteHost` and `dbPath` [verified: docs:channels/imessage/deployment.md].
- Needs Full Disk Access and Automation in that user's context. There is a documented failure, AppleEvents `-1743`, where the Automation grant lands on `sshd-keygen-wrapper` [verified: docs:channels/imessage/setup.md]. Spike early.
- Basic mode gives text and media send and receive. Reactions, edits and threaded replies need SIP off, and SIP off also stops iOS apps running on the Mac [verified: docs:channels/imessage/private-api.md]. Keep SIP on.
- A restart replays missed messages automatically [verified: docs:channels/imessage.md].

Reading Adam's own messages is a separate, higher-risk feature. It means granting Full Disk Access in `adam`'s context. Leave it as an open decision for Adam.

### Adam's OpenClaw.app node

Runs as `adam`, so its `system.run` would re-open the original gap. Mitigate three ways:

1. Local exec approvals to deny. On macOS node mode `system.run` is gated by the app's exec approvals [verified: docs:nodes/node-host.md].
2. Turn off **Allow Computer Control** in This Mac capabilities unless needed [verified: docs:nodes/computer-use.md].
3. Review the first pairing surface and reject what is not needed. Dangerous commands such as `camera.snap`, `screen.record` need explicit `gateway.nodes.commands.allow` [verified: docs:nodes/command-policy.md]. `gateway.nodes.commands.deny` is Gateway-wide, so it would hit other nodes too [inference].

The docs warn against a second CLI node for the same Mac, because the app is the sole node identity [verified: docs:nodes/index.md]. Our case is two different OS users with separate state directories, so it should be two identities, but no doc covers it. **Spike S4.**

---

## 9. Remote iOS builds from the PC

**Pick: node exec from the Gateway to a headless node host in the `jorah` macOS user, restricted to root-owned wrapper commands.**

Why:
- Nodes dial out, so no inbound port on the Mac [verified: docs:gateway/remote.md].
- Exec approvals are enforced on the node host, with the exact approved plan bound at approval [verified: docs:nodes/node-host.md].
- Claude-Code-on-node through ACPX is not possible [verified: docs:nodes/node-host.md].

Runner-up: SSH with `command=` forced commands. Simple and well understood, but needs an inbound port and has no approval flow. Keep SSH for iMessage and backups only.

Second runner-up: Codex paired-device execution is documented if Adam wants Codex for this [verified: docs:nodes/node-host.md]. Or full session hosting if the brain is on the API route, since that uses the embedded runtime.

Cost: EUR 0.

### Setup

```bash
# As jorah, once the Gateway is on the PC. Join code from the Gateway host.
openclaw connect <join-url> --service --commands system.run,system.run.prepare,system.which,file.fetch
```

`--commands` advertises an exact list and disables computer use, skill publishing, MCP and worker hosting on that node [verified: docs:nodes/node-host.md]. Also disable node auto-update so the pin holds: `openclaw config set nodeHost.autoUpdate.enabled false` [verified: same doc].

Allowlist only wrapper paths:

```bash
openclaw approvals allowlist add --node mac-worker "/usr/local/libexec/jorah/ios-build"
openclaw approvals allowlist add --node mac-worker "/usr/local/libexec/jorah/ios-test"
openclaw approvals allowlist add --node mac-worker "/usr/local/libexec/jorah/ios-archive"
openclaw approvals allowlist add --node mac-worker "/usr/local/libexec/jorah/claude-task"
```

**Wrappers must be owned by root.** An allowlist entry that points at a file the agent can edit is no allowlist [inference]. OpenClaw also denies approval-backed interpreter runs unless it can bind exactly one concrete file [verified: docs:nodes/node-host.md].

Wrapper rules [inference]:
- Takes `<repo-alias> <scheme> <destination-alias>`. Rejects anything else. Aliases come from a root-owned config file.
- Works only in `/Users/jorah/work/<repo>`, a full clone, per the README's project rules. Never in Adam's `~/Documents`.
- Fetches from GitHub with a read-only deploy key. Pushing stays disabled.
- Runs `xcodebuild` with a fixed `-derivedDataPath` and `-resultBundlePath` under `/Users/jorah/artifacts/<run-id>`.
- Returns a short JSON result. Small artifacts come back through the File Transfer plugin's `file.fetch`, with allowed read paths limited to `/Users/jorah/artifacts`. It handles binaries up to 16 MB [verified: docs:plugins/reference/file-transfer.md], so `.ipa` files and result bundles over that limit go over the restricted SSH path instead [inference].
- `claude-task` runs `claude -p` in the clone under `~/.claude-jorah` Seatbelt rules, so code edits stay sandboxed. `xcodebuild` runs outside that sandbox in a separate step [inference: network and DerivedData would otherwise fail].

### Signing and release

- `jorah` gets a Development certificate only, in its own Keychain.
- Automatic signing over a non-GUI session can use App Store Connect keys: `-allowProvisioningUpdates` with `-authenticationKeyPath`, `-authenticationKeyID`, `-authenticationKeyIssuerID` [verified: local `xcodebuild -help`]. Lowest role that works.
- No Distribution certificate. Adam's standing rule: for a Production release, build and verify the IPA, hand over the path, Adam uploads through Transporter. If Jorah must produce a signed IPA, that is a deliberate later grant.
- Keychain over SSH or headless is locked by default [inference, also implied by Claude Code's docs]. Spike whether a node host in the GUI session avoids it. Otherwise a dedicated build keychain with a known password stored by the wrapper.

### Tests needed before trusting this

| Spike | Expected | Why |
|---|---|---|
| `xcodebuild` as `jorah` from a node host, no GUI login | Builds, or a clear keychain error | Decides whether a GUI session is required |
| `xcrun simctl` boot and screenshot as `jorah` | Works in GUI session, may fail without | Simulators may need a login session [inference] |
| `xcrun devicectl` to Adam's iPhone | Pairing per user unknown | Do not assume |

Adam's evidence tiers still apply: a build success is not an install, an install is not launch, launch is not device acceptance.

---

## 10. GUI automation on the PC

**Pick: scripts and APIs first, pixels last.**

| Task | First choice | Where | Notes |
|---|---|---|---|
| Video cut, captions, silence removal, render | ffmpeg + Whisper or similar, headless | WSL2 for AI, Windows `ffmpeg.exe` for NVENC if WSL lacks it | No GUI, no lease, no licence. Use a dynamically linked ffmpeg in WSL, since a static build fails on the WSL `libcuda` shim [docs-only: nomercy-ffmpeg issue 42]. Spike S5 on NVENC |
| Resolve project assembly | Resolve Studio Python API, or its native MCP server | Windows node | Free edition lost scripting in 21.1 [verified above]. Studio is $295 list, one-time, with $236 seen in an October sale [docs-only: https://www.newsshooter.com/2026/10/20/blackmagic-davinci-resolve-studio-20-off/]. EUR price not confirmed. The Studio MCP server is reported to connect to Claude Code, but its permissions and safeguards are not explained [docs-only: digitalproduction.com article in fact 13]. Test it before trusting it |
| Fusion model | Python add-in using Fusion's API, in the running app | Windows node, or Mac in the interim | I could not open Autodesk's API page (404), so "no headless mode" is unconfirmed. Assume a logged-in GUI is required [inference] |
| Anything else | `computer.act` | Windows node, or Mac | Windows is experimental with limits. The Mac has Peekaboo by default and CUA in signed builds [verified: docs:nodes/computer-use.md] |

Node host must start in the interactive session [verified: docs:nodes/computer-use.md]. Steps:

```powershell
# As jorah-desk, interactive
openclaw plugins enable cua-computer
openclaw doctor --lint --only cua-computer/driver-artifacts
# Token comes from OPENCLAW_GATEWAY_TOKEN. Windows reaches the WSL loopback through localhost forwarding.
openclaw node run --host 127.0.0.1 --port <port> --display-name "pc-desk"
```

`computer.act` is a default on Windows once the pairing update is approved, so it can be held back with `gateway.nodes.commands.deny` until needed [verified: same doc]. Windows node allowlist mode makes `cmd.exe /c` runs require approval [verified: docs:nodes/node-host.md]. Use PowerShell 7 from MSI for unattended exec [verified: docs:platforms/windows.md].

**Interim:** Fusion and Resolve both run on this Mac with its 64 GB and M1 Max. Install under `jorah` when that track starts. Then GUI skills can be proven before the PC exists, on a provider that is less restricted. Resolve 21.1 on macOS needs Apple silicon and macOS 15 or later. On Windows with NVIDIA it needs 16 GB RAM, 4 GB VRAM and Studio driver 581.57 or newer [verified: Blackmagic readme in fact 13].

Licences: Fusion for personal use is limited to non-commercial home projects with 10 active documents [docs-only: search summary of Autodesk's terms, Autodesk's page returned 403]. So if Jorah becomes a business, Fusion needs a paid licence. I have not confirmed how the personal licence treats automation or a second machine [unverified]. Check before relying on it.

---

## 11. ESP32, serial and robots

**Pick: runtime traffic over LAN to a `robot-bridge` on the Windows side, published as a node-hosted MCP server. USB only for flashing and bench work.**

- WSL NAT makes inbound LAN traffic awkward [verified: https://learn.microsoft.com/en-us/windows/wsl/networking]. A Windows-side bridge has direct LAN and COM access.
- MCP servers are configured on the node machine under `nodeHost.mcp` [verified: docs:nodes/mcp-and-skills.md]. Note `--commands` disables MCP on a node, so the `pc-desk` node must not use it, or a separate node is needed [verified: docs:nodes/node-host.md].
- Safety state, e-stop and rate limits live in the bridge and firmware, not in the model (robotics track). A WSL or Gateway crash must not leave a motor running [inference].

USB in WSL remains possible for development. WSL 3.0.3 ships kernel 6.18.54.1 [verified: https://github.com/microsoft/WSL/releases/tag/3.0.3]. The 6.18 branch config builds `CP210X`, `CH341`, `FTDI_SIO`, `USB_ACM`, `USB_VIDEO_CLASS` and the USB/IP client as modules [verified: https://raw.githubusercontent.com/microsoft/WSL2-Linux-Kernel/linux-msft-wsl-6.18.y/arch/x86/configs/config-wsl]. Load with `modprobe` and add to `/etc/modules` [docs-only: https://developer.espressif.com/blog/espressif-devkits-with-wsl2/]. usbipd-win is at 5.3.0 (October 2025, still the latest release) and has auto-attach [verified: https://github.com/dorssel/usbipd-win/releases]. Windows also needs the chip's driver.

USB cameras go on Windows. USB/IP over the VM for video is a poor bet [inference].

Runner-up: robot bridge inside WSL with usbipd auto-attach. It fails if the VM restarts mid-motion, which is the wrong failure.

---

## 12. Moving the Gateway from Mac to PC

Exact artifacts. The dry run today listed two assets, state and workspace, and skipped regenerable `acpx/node_modules`, `llama-cpp/node_modules`, `plugin-skills`, `tmp`, `tools` [verified: `openclaw --profile jorah backup create --dry-run --json`].

| Artifact | Path on Mac (after section 7) | Method | Portable? | After restore |
|---|---|---|---|---|
| Config | `~/.openclaw-jorah/openclaw.json` | Archive | Yes, has absolute paths | Re-run `scripts/configure.sh`, review diff |
| Global DB | `state/openclaw.sqlite` | Archive only, never raw copy | Yes | Has pairing, cron, voicewake, auth store |
| Agent DB | `agents/main/agent/openclaw-agent.sqlite` | Archive | Yes | Memory index, sessions |
| Learned skills | `agents/main/agent/workshop-skills` | Archive | Yes | Check paths inside skills |
| Wiki | `wiki/main` | Archive | Yes | None |
| Workspace | `workspace/` with `USER.md`, `MEMORY.md`, `memory/`, `DREAMS.md`, `skills/` | Archive | Yes | Move to `~/jorah/workspace` |
| Repo | `~/jorah` | `git clone` | Yes | Needs first commit and a private remote or `git bundle` |
| Telegram token | In state | Archive | Yes | Check without printing it, see doc's `awk` line |
| Telegram DM pairing | `channel_pairing_allow_entries` in global DB [verified: docs:channels/pairing.md] | Archive | Yes | Should not need re-pairing. Acceptance test |
| Telegram offset | Durable ingress in state [verified: docs:channels/telegram/transports.md] | Archive | Yes | Updates kept up to 24 hours on Telegram [verified: https://core.telegram.org/bots/api] |
| Claude login | `~/.claude-jorah` plus macOS Keychain | **Do not move** | No | `claude auth login` on PC, stored at `~/.claude-jorah/.credentials.json` 0600 [verified: authentication docs] |
| Claude settings | `~/.claude-jorah/settings.json` | Regenerate | Yes | `setup-permissions.sh`. Remove Mac-only paths such as `/private/var/folders`, or confirm harmless |
| Claude transcripts | `~/.claude-jorah/projects/<key>` | Optional copy | Key changes with path | OpenClaw's own history is in SQLite [inference]. Continuity link via `setup-continuity.sh` |
| Plugins | `extensions/*/node_modules` | Reinstall | No | `openclaw doctor --fix`. "plugin node_modules trees must be reinstalled" [verified: docs:install/migrating.md] |
| Embedding runtime | `tools/llama.cpp` | Re-download | No, macOS binary | README's `models auth login --provider llama-cpp --method local` |
| Embedding model | `models/` 313 MB | Archive | Yes | Same model, no reindex [inference] |
| Exec approvals | `exec_approvals_config` in DB | Archive | Mac paths are meaningless | Reset to allowlist with Linux paths |
| Cron jobs | SQLite | Archive | Yes | List and review before enabling. Adam's rule: no silent schedules |
| Device pairings | Gateway DB | Archive | Partly | Clients cache credentials by route [verified: docs:gateway/remote.md]. Plan to re-enroll nodes with `devices join-code` and remove stale rows |
| Node pin and Node.js | System | Reinstall | n/a | Same OpenClaw version or newer. Never run an older build on migrated data [verified: docs:platforms/windows.md] |
| `~/.jorah-brain` | Local git repo | `git bundle` over the tailnet | Yes | Keep running `snapshot-brain.sh` on the PC. Mac copy becomes a read-only archive |
| `~/work` clones | Git | Re-clone, bundle local-only branches | Yes | `~/work/cognio` is a local-only pilot. Keep push disabled |
| Absolute symlinks | Anywhere | Review | No | Backup keeps original targets [verified: docs:install/migrating.md] |
| Secrets in env | Never | n/a | n/a | README rule: no `ANTHROPIC_API_KEY` in env |

### Cutover runbook

Rehearse first with a staging profile and a second Telegram bot. Real cutover:

1. PC ready: Section 16 phase C passed.
2. On Mac: `openclaw --profile jorah gateway stop`, confirm stopped.
3. `openclaw --profile jorah backup create --output <dir> --verify`, then `backup verify` on the copy after transfer.
4. On PC, in WSL: install the same OpenClaw and Node. `backup restore <archive> --target ~/openclaw-restored`. "Restore never activates in place." Move assets per `manifest.json` [verified: docs:install/migrating.md].
5. Run `scripts/configure.sh`. Log Claude in. Re-download the runtime. `openclaw --profile jorah doctor`, then `gateway install` and start.
6. Prove: Telegram reply without pairing, `/acp doctor`, delegated task sandboxed, `switch-brain.sh status --probe`, memory search, `openclaw status`.
7. Set up Serve. Re-enroll Mac and iPhone as nodes. On Mac: `openclaw-mac primary set --direct-url wss://pc.<tailnet>.ts.net --token-file <file>` once the app is installed [verified: docs:platforms/mac/remote.md].
8. Remove the interim grant. Keep Mac's old state stopped for two weeks.

**Rollback before step 6 passes:** stop PC, start Mac. **After PC has taken real traffic:** state has diverged; back up the PC, restore on the Mac, accept any gap. Do not run both, ever [verified: docs:gateway/remote.md for single ownership]. Two pollers on one bot token conflict [inference: standard Telegram behaviour; the Bot API section I read does not state it].

---

## 13. Failover, backups, power, remote access, updates

### Failover if the PC is off

**Pick: manual promotion, with a Mac rescue bot.** Doc pattern: `--profile rescue`, its own Telegram bot, a base port at least 120 away [verified: docs:gateway/multiple-gateways.md].

| Stage | Behaviour |
|---|---|
| PC healthy | Mac is a node. Rescue bot idle except a health check |
| PC unreachable | Rescue bot says so. Offers Wake-on-LAN or smart plug if available. Telegram messages to main bot wait, up to 24 hours [verified] |
| PC down long | Adam says "promote". Mac first verifies the PC is off or tells Adam it cannot, restores the latest verified archive as `jorah`, starts Gateway. Runbook in repo |
| PC back | Fence the PC's Gateway before starting it. Back up Mac, restore on PC |

Rescue bot limits: no main bot token, no real channels, read-only copy of the last snapshot, no robots, no scheduled work beyond the health probe. That probe is a schedule, so Adam approves it.

**Why not automatic:** split brain would double-fire cron, double-answer channels and possibly drive a robot twice. The Mac may also be asleep or away when needed. A Mac node also cannot host for a Gateway; nodes are peripherals [verified: docs:nodes/index.md].

**Runner-up:** read-only Mac only, no promotion. Simpler. Add promotion after one successful drill. **What would change it:** continuous replication with `sqlite3_rsync` or Litestream reduces data loss on promotion [verified: docs:install/backups.md], and could shorten the runbook, but it does not make automatic takeover safe.

Cost: EUR 0, plus a second free Telegram bot.

### Backups

`~/.jorah-brain` is not a full backup. It holds only memory, wiki and learned skills [verified: `scripts/snapshot-brain.sh`]. It has no auth, no sessions, no config, no cron, no channel state. Keep it for history and rollback of learning. Do not rely on it for recovery. It also has no remote by design.

| Layer | What | How | Where |
|---|---|---|---|
| 1 | Full encrypted archive, daily | `openclaw backup enable --to <location> --every 24h --keep-daily 7 --keep-weekly 4 --keep-monthly 12` | Second disk on PC, `filesystem` location [verified: docs:concepts/storage-locations.md] |
| 2 | Copy to Mac | Restricted SSH upload key over tailnet | `/Users/jorah/backups`. Mac is often the only other machine |
| 3 | Offsite | Encrypted before upload. R2 is the documented provider [verified: docs:concepts/storage-locations.md]. Or an external disk moved monthly | Pick one, see open decisions |
| 4 | Learning history | `snapshot-brain.sh` on PC | Local git |
| 5 | Media | Raw footage and renders are not in archives. Own folder, own policy | D: drive |

Passphrase: `OPENCLAW_STORAGE_PASSPHRASE` from a secret store, with a recoverable copy kept by Adam outside the PC [verified: storage-locations doc]. Backups contain auth and channel credentials [verified: docs:install/backups.md], so no plaintext archive leaves the machine.

**A backup is not proven until restored.** Monthly: `openclaw backup verify` plus a restore to a staging path with a test profile. Scheduling is Adam's call, previewed first.

Estimated size: under 1 GB today [inference from dry-run assets]. It grows with media and transcripts, watch `tmp`.

### Power and UPS

| Item | Pick | Cost | Evidence |
|---|---|---|---|
| UPS | Line-interactive with a true sine output, sized for peak. Target at least 865 W if the GPU is 300 W class. **CyberPower CP1500EPFCLCD**: 1500 VA, 900 W, pure sine on battery, active-PFC compatible, Schuko, USB HID | No current EUR price found [unverified]. The larger CP1600EPFCLCD showed about EUR 384 to 439 in undated shop snippets | [verified spec: https://www.cyberpower.com/eu/en/product/sku/cp1500epfclcd]; prices [docs-only: search snippets] |
| Rejected UPS | APC BR1500GI, named in the first draft. 865 W, but listed as a stepped approximation to a sine wave on battery, so it misses the target above | About EUR 459 to 531, mid-2026 | [docs-only: https://automa.net/apc/br1500gi/, https://community.se.com/t5/APC-UPS-for-Home-and-Office-Forum/What-s-the-difference-between-br1500ms-and-back-ups-pro-1500va/td-p/294302, prices as first found at https://www.mediamarkt.at/de/product/_apc-br1500gi-back-ups-pro-usv-darkslategray-158470641.html]. Schneider's own pages could not be read |
| Cheaper UPS | APC BX1600MI, 900 W | About EUR 201 to 266 | [docs-only: https://www.comparateur-gamer.fr/prix/apc-back-ups-bx-1600va-prises-iec-731304410829, https://www.kaina24.lt/ru/s/bx1600mi/] Output waveform not confirmed. Check against an active-PFC PSU |
| Electricity | Household price 19.85 ct/kWh, H1 2026, Eurostat | See below | [verified: https://www.euenergyprices.eu/en/electricity/sk] Secondary, citing `nrg_pc_204` |

Running costs [inference, wattages are estimates to measure with a plug meter]:

| Load | Average | kWh/year | EUR/year |
|---|---|---|---|
| PC idle | 80 W | 701 | 139 |
| PC with regular AI and renders | 150 W | 1,314 | 261 |
| Docked Mac | 15 W | 131 | 26 |

Settings:
- BIOS: restore on AC power loss, Wake-on-LAN on, virtualization on.
- Windows: never sleep, hibernate off, `powercfg /change standby-timeout-ac 0`.
- UPS over USB: Windows sees HID UPS as a battery and can shut down at a threshold [inference]. Then `wsl --shutdown` happens with Windows. Test real power loss once, with the Gateway idle.
- Router and switch on the UPS too, or the tailnet dies first.
- The Mac has a battery, which helps it survive short cuts.
- BitLocker with TPM only, so the PC can reboot unattended [inference]. A pre-boot PIN is stronger but stops recovery after a power cut. Decide with the security track. Windows Pro needed for BitLocker management and RDP host [inference, not re-verified].

**What would change it:** frequent outages push toward a bigger UPS. A brief-outage area can use the cheap one or none at first. It is not required for MVP.

### Remote access

| Need | Path |
|---|---|
| Chat | Telegram, no inbound ports |
| Control UI, nodes, iOS app | `https://pc.<tailnet>.ts.net` via Serve |
| Windows admin | Windows OpenSSH or RDP over the tailnet, as `adam`, key only |
| WSL admin | SSH or RDP in as `jorah-svc`, key only, then `wsl -d jorah-gw`. A distro is visible only to the user that owns it |
| See the GUI job | Node desktop stream, approved separately [verified: docs:nodes/command-policy.md], or RDP read-only by policy |
| Mac | Screen Sharing over tailnet from Adam's devices only |

`ws://` plaintext is allowed on tailnet hosts, but the iOS app marks it Limited [verified: docs:gateway/remote.md, docs:platforms/ios.md]. Use `wss://` through Serve.

### Updates

| Component | Policy | Evidence |
|---|---|---|
| OpenClaw | Pin in `configure.sh`. Verified backup, `openclaw update --dry-run`, upgrade Gateway first, then nodes. N-1 protocol accepted for nodes. Never run older builds on migrated data | [verified: docs:nodes/pairing-and-status.md, docs:install/updating/rollback-and-recovery.md] |
| Nodes | Disable auto-update: packaged headless nodes check hourly by default. `nodeHost.autoUpdate.enabled: false` | [verified: docs:nodes/node-host.md] |
| Mac app | Turn off automatic app updates. App protocol must match | [verified: docs:platforms/macos.md] |
| Windows Update | Active hours up to 18 hours. Plan a weekly window. No-auto-restart policies are unreliable, per Microsoft, and devices with no signed-in user or active RDP session are restarted, which is this PC's normal state | [verified: https://learn.microsoft.com/en-us/windows/deployment/update/waas-restart] |
| WSL | Update by hand in the same window, then soak | [inference] |
| GPU driver | Manual, Studio branch, not during jobs. Resolve guides ask for current Studio drivers | [docs-only] |
| macOS, Xcode | Manual. Rebuild after each | [inference] |
| Tailscale | Auto-update fine. Recheck Serve and unattended mode afterwards | [inference] |

After any reboot, check the boot chain with a Windows-side health script: Tailscale up, distro running, `systemctl --user status`, Gateway health, Telegram test. Docs warn a successful task result does not prove health [verified: docs:platforms/windows.md].

---

## 14. Compatibility matrix

Legend: yes, no, limited, "?" = unknown, needs a spike. Sources are in the notes under the table.

| Capability | Win native | WSL2 | Mac | iPhone | Watch | Android/Wear | Linux box | ESP32 | Notes |
|---|---|---|---|---|---|---|---|---|---|
| Gateway | yes | yes, **pick** | yes, interim | no | no | no | yes | no | 1 |
| Claude CLI brain | yes | yes | yes | no | no | no | yes | no | |
| Delegated Claude Code sandbox | **no** | yes | yes | no | no | no | yes | no | 2 |
| Worker container isolation | no | ? likely | yes | no | no | no | yes | no | 3 |
| Claude Code placed on a node | no | no | no | no | no | no | no | no | 4 |
| Exec on node | limited | n/a | yes | no | no | no | yes | no | 5 |
| Voice wake built in | **no** | no | yes, macOS 26+ | yes, may suspend in background | no | yes, foreground | no | custom | 6 |
| Talk | Hub, PTT | browser Control UI | yes | yes | yes, realtime Talk | yes | browser only | custom | 7 |
| Camera | Hub | no | yes | yes | no | yes | V4L2 via plugin | ESP32-CAM custom | 8 |
| Screen capture | Hub | n/a | yes | yes | no | ? | ? | no | |
| `computer.act` | experimental | no | yes | no | no | `mobile.ui.*` | experimental | no | 9 |
| Xcode, iOS signing | no | no | **only here** | no | no | no | no | no | |
| iMessage | no | via SSH to Mac | **only here** | no | no | no | via SSH to Mac | no | 10 |
| Telegram, WhatsApp, Signal, email | via Gateway | **via Gateway** | via Gateway | | | | | | Channels land on Gateway |
| Calendar, Reminders via node | Graph API instead | n/a | yes | yes | no | yes | no | no | 11 |
| Health summaries | no | no | no | yes, opt-in | no | ? | no | no | `health.summary` needs explicit allow [verified: docs:nodes/command-policy.md] |
| Fusion | yes | **no** | yes | no | no | no | **no** | no | 12 |
| Resolve GUI | yes | no | yes | no | no | no | yes, Rocky | no | 13 |
| Resolve scripting | Studio | no | Studio | no | no | no | Studio | no | 13 |
| ffmpeg headless | yes | yes | yes | no | no | no | yes | no | |
| NVENC | yes | likely, spike | no, VideoToolbox | no | no | no | yes | no | 14 |
| CUDA | yes | yes, limits | no | no | no | no | yes | no | 15 |
| Metal local models | no | no | yes, M1 Max 64 GB | no | no | no | no | no | Node can publish local inference [verified: docs:nodes/mcp-and-skills.md] |
| USB serial to ESP32 | yes | via usbipd | yes | no | no | no | yes | n/a | 16 |
| Browser automation | yes | yes, own Chromium or Docker | yes | no | no | no | yes | no | 17 |
| OpenClaw Docker sandbox | ? | yes, Docker Engine | per-user engine | | | | yes | | 18 |

Notes:
1. [verified: docs:platforms/windows.md, docs:platforms/linux.md, docs:nodes/index.md]
2. [verified: https://code.claude.com/docs/en/sandboxing]
3. [verified: docs:nodes/session-hosting.md] WSL as Linux is inference.
4. "ACPX routes cannot dispatch to a paired device" [verified: docs:nodes/node-host.md]
5. Windows shell wrappers need approval [verified: docs:nodes/node-host.md]
6. [verified: docs:nodes/voicewake.md, docs:platforms/mac/voicewake.md, docs:platforms/android.md]. iOS: "iOS may suspend these foreground connections after the app enters the background" [verified: docs:platforms/ios.md]. So iPhone is not an always-on ear. Mic availability on PC needs a custom service; ESP32-S3 mic satellites are the voice track's call.
7. Linux desktop shell cannot give the microphone to its WebView [verified: docs:platforms/linux.md]. Watch and Wear [verified: docs:platforms/ios.md, docs:platforms/android.md].
8. [verified: docs:platforms/linux.md, docs:nodes/command-policy.md]. `camera.snap`, `camera.clip` need explicit allow.
9. [verified: docs:nodes/computer-use.md, docs:nodes/command-policy.md]
10. [verified: docs:channels/imessage/setup.md, docs:install/macos-vm.md]
11. [verified: docs:nodes/command-policy.md]. Other tracks should prefer direct APIs on the Gateway for mail and calendar.
12. [docs-only: Autodesk system requirement pages]
13. Rocky Linux 8.6 and Resolve 21.1 requirements, and scripting moving to Studio [verified: Blackmagic readme in fact 13].
14. 2026 community reports say it works with dynamic linking [docs-only: see section 4]. NVIDIA's WSL CUDA guide does not mention video encode [verified: https://docs.nvidia.com/cuda/wsl-user-guide/index.html]. Its DeepStream FAQ tells users to bind-mount `libnvidia-encode.so.1` from WSL into containers [verified: https://docs.nvidia.com/deepstream/text/DS_WSL2_FAQ]. The older forum thread saying the library is missing no longer matches these reports.
15. [verified: https://docs.nvidia.com/cuda/wsl-user-guide/index.html, https://learn.microsoft.com/en-us/windows/ai/directml/gpu-cuda-in-wsl]
16. [verified: https://learn.microsoft.com/en-us/windows/wsl/connect-usb]
17. Chrome MCP is host-local, and raw remote CDP from WSL to Windows Chrome needs a port exposed across the boundary [verified: docs:tools/browser-wsl2-windows-remote-cdp-troubleshooting.md]. With interop off prefer a browser inside the distro. Residential IP helps, sites block data-centre IPs [verified: docs:install/macos-vm.md].
18. Docker defaults to `docker.network: "none"` [verified: docs:gateway/sandboxing/supported-capability-matrix.md].

---

## 15. PC hardware tiers

**Check the existing PC first.** In admin PowerShell:

```powershell
winver
Get-ComputerInfo | Select-Object OsName,OsVersion,OsArchitecture,CsTotalPhysicalMemory,CsProcessors
Get-CimInstance Win32_VideoController | Select-Object Name,DriverVersion
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv
Get-PhysicalDisk | Select-Object FriendlyName,MediaType,Size
Get-Volume | Select-Object DriveLetter,SizeRemaining,Size
Get-Tpm | Select-Object TpmPresent,TpmReady
wsl --version
Get-NetAdapter | Select-Object Name,LinkSpeed,Status
systeminfo | findstr /i "Virtualization Hyper-V"
```

Also check: BIOS has Restore on AC power and Wake-on-LAN; Ethernet to router; edition Pro or Home; free USB ports; PSU wattage; whether the PC is used for gaming; where it physically sits (noise and who can touch it).

| Tier | Purpose | CPU | RAM | GPU | Disk | Gets you |
|---|---|---|---|---|---|---|
| **Minimum** | Gateway, cloud voice and brain, light desktop | 6 cores with virtualization | 32 GB | Any NVIDIA 8 GB, or whatever is there | 1 TB NVMe | All of phases A to D, cloud models |
| **Recommended** | Above, plus local voice, a small local model, Fusion, 4K Resolve | 8+ cores | 64 GB | NVIDIA 16 GB | 2 TB NVMe plus a data disk for footage | Local STT and TTS with spare room, one moderate local model. Not at the same moment as heavy Resolve |
| **Stretch** | Large local models alongside media | 12+ cores | 96 to 128 GB | 24 GB or more | 4 TB NVMe plus data disk | Most local autonomy |

Memory budget [inference, to measure]: Gateway and workers 2 to 4 GB (docs: several hundred MiB per retained worker [verified: docs:nodes/session-hosting.md]); Claude CLI processes about 1 GB each; local STT and TTS 4 to 8 GB of VRAM; local LLM 12 to 24 GB of VRAM; Resolve guides quote about 12 GB of VRAM for 4K [docs-only]. WSL takes at most 50 percent of RAM by default, so it must be set [verified: wsl-config docs]. GPU use by Resolve and a local model conflicts. Schedule rather than share.

### Prices seen, EU, 2026-11-02

Germany aggregator data, not Slovak retailers. The market is unusually distorted by memory shortages [docs-only: https://abit.ee/en/graphics-cards/nvidia-geforce-rtx-50-rtx-5090-gpu-prices-europe-3dcenter-memory-shortage-radeon-rx-9000-en].

| Part | VRAM | Price | Date | Source | Note |
|---|---|---|---|---|---|
| RTX 5060 Ti 16 GB | 16 | EUR 775 to 855 | 1 Nov | [docs-only: https://gpupricehistory.com/de/rtx-5060-ti] | Listing cards only, no retailers named, and the page's own minimum (EUR 570) contradicts its 8 GB listings. Check it is the 16 GB model. 8 GB cards are EUR 518+ |
| RTX 5070 Ti | 16 | EUR 1,176 lowest new in stock, MSI Gaming Trio OC on Amazon.de | 2 Nov | [verified: https://gpuprix.com/germany/gpus/geforce-rtx-5070-ti] | Search snippet showed EUR 916 earlier, the page now does not |
| RTX 5080 | 16 | EUR 1,899 to 2,099 | 31 Oct | [unverified: same aggregator as the 5090 row, not rechecked] | Same 16 GB VRAM. Poor value here |
| RTX 5090 | 32 | EUR 5,243 cheapest per Geizhals, reported 13 Sep. EUR 8,079 "minimum" on one aggregator on 1 Nov, while that same page lists a card at EUR 5,458 | Sep, Nov | [docs-only: https://betterfps.com/news/rtx-5090-germany-prices-5200-euro-73-percent-increase-3rrp, https://gpupricehistory.com/de/rtx-5090]. Geizhals and Igor's Lab returned 403 | November street price not confirmed. Do not buy at either price |
| RX 9070 XT | 16 | EUR 655 to 759 | Undated | [docs-only: https://gpupricehistory.com/fr/rtx-3090-ti/vs/rx-9070-xt, https://gpupricehistory.com/nl/rx-9070-xt/vs/rtx-3090-ti] | No CUDA, so WSL local AI is harder. Fine for Resolve |
| Used RTX 3090 | 24 | **Not confirmed** | | | Check bazos.sk and kleinanzeigen. Best VRAM per euro if clean. Runs hot, older warranty |
| DDR5 64 GB kit | | **Not confirmed for Nov 2026** | | Last point: EUR 376 in Oct 2025 [docs-only: https://www.ebay.de/itm/317397499892], "way above last year's prices" in Feb 2026 [docs-only: https://www.notebookcheck.net/DDR5-gets-cheaper-RAM-prices-appear-to-drop-in-Germany-and-to-some-extent-in-the-US-as-well.1232770.0.html] | Check Geizhals and Alza. If the PC has DDR4, the sums change |
| NVMe 2 TB, Windows Pro, HDMI dummy, dock | | **Not confirmed** | | | Look up at purchase |

**GPU pick:** RTX 5060 Ti 16 GB if the PC needs a card and money is the limit. Used 24 GB 3090 if local LLMs matter most and a sound one appears. Otherwise keep the existing GPU and start with cloud models. Runner-up RTX 5070 Ti, which is about 50 percent more money for the same VRAM and much faster media and games. **What would change it:** GPU prices falling, or the other tracks concluding that a specific local model must run alongside voice. Do not wait for RTX 50 Super cards: reports range from a delay to cancellation, the latest points to CES 2027 at the earliest, and nothing is official [docs-only: https://www.igorslab.de/en/nvidia-geforce-rtx-50-super-allegedly-postponed-to-q3-2026/, https://80.lv/articles/report-we-will-not-see-new-rtx-gpus-from-nvidia-in-2026].

Do not buy any of it until phases A to C have run on what exists. The Mac has 64 GB and can host local models meanwhile.

---

## 16. Steps to execute

Each step has an evidence gate. Stop at a failed gate. Items marked **Adam** need Adam personally.

### Phase A: Mac boundary (this week)

| # | Step | Evidence gate |
|---|---|---|
| A1 | **Adam:** sign in to Tailscale on the Mac and iPhone. Enable MagicDNS and HTTPS certificates | `tailscale status` shows both |
| A2 | Replace default policy with the interim grants. Preview diff, **Adam** approves | Tests pass in admin console |
| A3 | Commit repo. Push to a private remote or make a bundle. **Adam** picks | `git log` shows a commit, `.gitignore` excludes memory |
| A4 | Section 7 steps 2 and 3 | Permission-denied proofs recorded |
| A5 | Section 7 steps 4 to 10 | All acceptance tests pass |
| A6 | Spike S1: FileVault SSH unlock on this Mac, from the same LAN. The tailnet is not up yet at that stage | One planned reboot unlocked remotely. Record how long until the tailnet returns and who had to log in |
| A7 | As `adam`, run `tailscale serve --bg --https=443 http://127.0.0.1:<port>`. In `jorah`, keep `gateway.bind: loopback` and token auth, and set `gateway.trustedProxies: ["127.0.0.1"]`. iPhone connects. Do not use `tailscale.mode: serve`, unless a test shows `jorah` can drive the CLI | iOS shows **Full** access |

### Phase B: Mac as a device (next)

| # | Step | Evidence gate |
|---|---|---|
| B1 | Install OpenClaw.app in `adam` as node to the local Gateway | Node listed, surface reviewed |
| B2 | Voice wake list `["jorah","hey jorah"]`. Preview first, global setting | Says "Hey Jorah", gets a reply. Note false wakes |
| B3 | Exec denied on this node | `system.run` on it returns denied |
| B4 | Spike S4: second node for `jorah` user | Two identities coexist or documented failure |
| B5 | Dock test: closed lid, power, display or dummy | Node stays connected 24 hours |
| B6 | Install wrappers in `/usr/local/libexec/jorah`. Clone a test app in `~/work` | `ios-build` builds; other commands refused |
| B7 | Spike S6: `xcodebuild`, `simctl`, `devicectl` from node | Results recorded by evidence tier |

### Phase C: PC readiness

| # | Step | Evidence gate |
|---|---|---|
| C1 | **Adam:** run the section 15 check and share output | Tier decided |
| C2 | Install Windows 11 updates, create users, BitLocker, Tailscale tagged with `tailscale set --unattended=true`, WSL 3.x, `jorah-gw` distro hardened | `wsl -l -v` shows v2. `/mnt/c` absent. `wsl.exe` not callable inside. After a reboot with nobody signed in, the PC answers on the tailnet |
| C3 | Staging OpenClaw on a new profile, fresh Telegram test bot, no restored state. **7-day soak** | Uptime log shows no idle kills over 7 days, including one reboot |
| C4 | Claude Code sandbox in WSL | `/sandbox` clean. Read of `~/.ssh` and outbound network blocked. `failIfUnavailable` refuses when `bwrap` is removed |
| C5 | Spike S2: Serve to WSL Gateway with `jorah-svc` not signed in, node join from `jorah-desk`, iOS **Full** | Works after a reboot, or fall back and update this doc |
| C6 | Spike S3: Windows node host, `jorah-desk`, `cua-computer` lint | `no findings`. A Notepad type-and-read test |
| C7 | Spike S5: GPU in WSL, `libnvidia-encode.so.1` under `/usr/lib/wsl/lib`, real `h264_nvenc` encode with a dynamically linked ffmpeg, Docker with GPU | `nvidia-smi` works. NVENC yes or no recorded from a real output file |

### Phase D: Cutover

| # | Step | Evidence gate |
|---|---|---|
| D1 | Rehearsal restore to staging profile, second bot | Skills, memory, pairing present |
| D2 | **Adam** approves window. Section 12 runbook | All step 6 proofs pass |
| D3 | Re-enroll Mac nodes and iPhone. Remove interim grant. Windows Hub only if wanted | Nodes online. Policy tests pass |
| D4 | Set up iMessage bot and wrapper. Spike `-1743` | Text round trip |
| D5 | First iOS build from a Telegram request | Build log and artifact returned. Claim only "build" tier |

### Phase E: Resilience

| # | Step | Evidence gate |
|---|---|---|
| E1 | Encrypted backup location and schedule. Preview, **Adam** approves | Scheduled run, `backup verify` |
| E2 | Copy to Mac, offsite | File present, restored in staging |
| E3 | Rescue bot on Mac | Pull PC network: rescue bot reports it |
| E4 | Failover drill: promote Mac, then demote | Conversation continues. Data loss noted |
| E5 | UPS install and a power-pull test | Clean shutdown, automatic return, Gateway healthy |
| E6 | Windows Update window. First cycle watched | Everything returned unaided |

### Phase F: GUI and hardware

| # | Step | Evidence gate |
|---|---|---|
| F1 | Headless video pipeline on PC | Video made from a test clip |
| F2 | GUI lease script and `tscon` flow, HDMI dummy | Correct resolution, session locks after job |
| F3 | Fusion or Resolve scripted job, on Mac or PC | Output file opens and matches request |
| F4 | `robot-bridge` as node MCP, with a benign LED device first | Command round trip, kill on bridge crash proven |

---

## 17. Not confirmed

- Current DDR5, NVMe, Windows Pro and HDMI dummy prices. Search budget ended before I could look.
- Used RTX 3090 market price.
- Slovak retail prices. All are German or other EU figures.
- Exact Mac mini start price. The EUR 949 on Apple's German page is a financing example.
- Fusion's API and headless options, because Autodesk's help page returned 404. Fusion's personal licence terms on automation and second machines. The non-commercial limit comes from a search summary only.
- Resolve Studio's EUR price. The USD list price is secondary. Whether free Resolve keeps console scripting, since sources disagree. The Studio MCP server's safety model.
- November street price of the RTX 5090. Geizhals could not be opened.
- Current EUR price of the CyberPower CP1500EPFCLCD. BR1500GI's waveform from Schneider's own datasheet.
- Any NVIDIA statement that NVENC is supported on WSL2. Only community reports and indirect NVIDIA docs exist.
- Whether localhost forwarding from `jorah-svc`'s WSL VM reaches other Windows users and SYSTEM when `jorah-svc` is not signed in interactively.
- Whether the Tailscale CLI inside `Tailscale.app` works for a standard macOS user through XPC, and whether the tunnel survives `adam` logging out.
- Whether the WSL idle-shutdown bug is present on WSL 3.0.x.
- `vmIdleTimeout=-1` semantics. Docs document `-1` only for `instanceIdleTimeout`.
- Whether Windows Hub and a CLI node host can coexist on one PC.
- Whether two macOS users can each hold a separate node identity.
- Whether Telegram's conflict on concurrent `getUpdates` is stated in the section of the Bot API I read. It is standard behaviour, and a cutover must stop the old poller regardless.
- Windows Home's limits for this design. I assume Pro.

---

## 18. Risks

| Risk | Impact | Mitigation |
|---|---|---|
| WSL dies with Windows reboots or idle bug | Jorah down | Boot chain, soak, watchdog, mini-PC as fallback |
| Serve-to-WSL does not work cleanly | Remote access harder | S2 early, fallback documented |
| Windows `computer.act` too limited for Fusion | GUI skills blocked | API first, Mac as GUI host |
| `jorah` on Mac has broad network | Exfiltration of what it can read | Boundary limits what it can read, narrow grants, security track |
| Backups contain credentials | Credential leak | Encryption required, passphrase kept off the machine |
| MacBook travels | iOS and iMessage pause | Honest offline status, Mac mini option |
| Node auto-update breaks pin | Version skew | Disable, staged upgrades |
| Prices | Overspend | Buy after phase C |
| Windows Hub stable lags its alphas | Version skew with the Gateway | Not load-bearing |
| Tailscale unattended mode missed or reset | PC unreachable over the tailnet after a reboot | Set it in C2, gate on a no-login reboot, recheck after updates |
| Autologon or unlocked console | Physical access gives a session | Lease model, no autologon at first |

---

## 19. Primary sources

OpenClaw bundled docs, all read under `/opt/homebrew/lib/node_modules/openclaw/docs/`: `platforms/windows.md`, `platforms/linux.md`, `platforms/macos.md`, `platforms/ios.md`, `platforms/android.md`, `platforms/mac/remote.md`, `platforms/mac/voicewake.md`, `platforms/mac/bundled-gateway.md`, `gateway/remote.md`, `gateway/tailscale.md`, `gateway/stable-https-url.md`, `gateway/multiple-gateways.md`, `gateway/index.md`, `gateway/sandboxing.md`, `gateway/sandboxing/supported-capability-matrix.md`, `network.md`, `nodes/index.md`, `nodes/node-host.md`, `nodes/session-hosting.md`, `nodes/node-exec.md`, `nodes/command-policy.md`, `nodes/computer-use.md`, `nodes/talk.md`, `nodes/voicewake.md`, `nodes/mcp-and-skills.md`, `nodes/file-transfers.md`, `plugins/reference/file-transfer.md`, `nodes/pairing-and-status.md`, `install/migrating.md`, `install/backups.md`, `install/macos-vm.md`, `install/updating/rollback-and-recovery.md`, `cli/backup.md`, `concepts/storage-locations.md`, `channels/imessage.md`, `channels/imessage/deployment.md`, `channels/imessage/setup.md`, `channels/imessage/private-api.md`, `channels/pairing.md`, `channels/telegram/transports.md`, `tools/browser-wsl2-windows-remote-cdp-troubleshooting.md`, `auth-credential-semantics.md`.

Web:
- https://tailscale.com/kb/1088/run-unattended
- https://tailscale.com/kb/1065/macos-variants
- https://tailscale.com/kb/1242/tailscale-serve
- https://tailscale.com/docs/reference/targets-and-selectors
- https://github.com/tailscale/tailscale/blob/main/safesocket/safesocket_darwin.go
- https://www.blackmagicdesign.com/support/content/readme/59dd4eef1f4941c29fb8dc48b33f5c87
- https://digitalproduction.com/2026/09/08/resolve-21-1-adds-mcp-and-finally-gets-presets/
- https://www.newsshooter.com/2026/10/20/blackmagic-davinci-resolve-studio-20-off/
- https://support.apple.com/en-us/102338
- https://www.apple.com/de/shop/buy-mac/mac-mini
- https://www.cyberpower.com/eu/en/product/sku/cp1500epfclcd
- https://automa.net/apc/br1500gi/
- https://community.se.com/t5/APC-UPS-for-Home-and-Office-Forum/What-s-the-difference-between-br1500ms-and-back-ups-pro-1500va/td-p/294302
- https://betterfps.com/news/rtx-5090-germany-prices-5200-euro-73-percent-increase-3rrp
- https://www.igorslab.de/en/nvidia-geforce-rtx-50-super-allegedly-postponed-to-q3-2026/
- https://80.lv/articles/report-we-will-not-see-new-rtx-gpus-from-nvidia-in-2026
- https://github.com/games-on-whales/wolf/discussions/448
- https://github.com/NoMercy-Entertainment/nomercy-ffmpeg/issues/42
- https://docs.nvidia.com/deepstream/text/DS_WSL2_FAQ
- https://raw.githubusercontent.com/microsoft/WSL2-Linux-Kernel/linux-msft-wsl-6.18.y/arch/x86/configs/config-wsl
- https://github.com/microsoft/WSL/releases/tag/3.0.3
- https://code.claude.com/docs/en/sandboxing
- https://code.claude.com/docs/en/authentication
- https://learn.microsoft.com/en-us/windows/wsl/connect-usb
- https://learn.microsoft.com/en-us/windows/wsl/networking
- https://learn.microsoft.com/en-us/windows/wsl/wsl-config
- https://learn.microsoft.com/en-us/windows/ai/directml/gpu-cuda-in-wsl
- https://learn.microsoft.com/en-us/windows/deployment/update/waas-restart
- https://learn.microsoft.com/en-us/sysinternals/downloads/autologon
- https://docs.nvidia.com/cuda/wsl-user-guide/index.html
- https://github.com/microsoft/WSL/issues/13416
- https://github.com/microsoft/WSL/releases
- https://github.com/microsoft/wslg
- https://raw.githubusercontent.com/microsoft/WSL2-Linux-Kernel/linux-msft-wsl-6.6.y/arch/x86/configs/config-wsl
- https://github.com/dorssel/usbipd-win/releases
- https://github.com/openclaw/openclaw-windows-node/releases
- https://developer.espressif.com/blog/espressif-devkits-with-wsl2/
- https://tailscale.com/pricing
- https://tailscale.com/kb/1068/tags
- https://tailscale.com/kb/1193/tailscale-ssh
- https://tailscale.com/kb/1295/install-windows-wsl2
- https://tailscale.com/kb/1324/grants
- https://tailscale.com/kb/1337/policy-syntax
- https://support.apple.com/en-us/102282
- https://support.apple.com/en-us/102501
- https://support.apple.com/guide/remote-desktop/sleep-shut-down-log-out-or-restart-a-computer-apd5535ee19/mac
- https://www.apple.com/de/mac-mini/
- https://www.jeffgeerling.com/blog/2025/you-can-finally-manage-macs-filevault-remotely-tahoe/
- https://www.macworld.com/article/3063625/finally-apple-adds-macbook-battery-charge-limit-to-macos-26-4.html
- https://core.telegram.org/bots/api
- https://www.pugetsystems.com/blog/2026/09/10/how-davinci-resolve-free-v21-1-scripting-changes-affect-puget-bench/
- https://davinciresolveclub.com/davinci-resolve-system-requirements-2026/
- https://autodesk.com/de/support/technical/article/System-requirements-for-Autodesk-Fusion-360
- https://www.autodesk.com/products/fusion-360/product-details
- https://support.smartbear.com/testcomplete/docs/testing-with/running/via-rdp/keeping-computer-unlocked.html
- https://www.edgeverve.com/assistedge/knowledge-base/RPA19.1/Troubleshooting/Running_UI_RDPdisconnected.htm
- https://forums.developer.nvidia.com/t/building-ffmpeg-with-nvenc-inside-docker-container-in-wsl-2-linux-distro/155102
- https://gpupricehistory.com/de/rtx-5060-ti
- https://gpupricehistory.com/de/rtx-5080
- https://gpupricehistory.com/de/rtx-5090
- https://gpuprix.com/germany/gpus/geforce-rtx-5070-ti
- https://igorslab.de/en/geforce-rtx-5090-when-even-the-partially-enabled-chip-becomes-too-valuable-for-gamers-analysis
- https://abit.ee/en/graphics-cards/nvidia-geforce-rtx-50-rtx-5090-gpu-prices-europe-3dcenter-memory-shortage-radeon-rx-9000-en
- https://www.notebookcheck.net/DDR5-gets-cheaper-RAM-prices-appear-to-drop-in-Germany-and-to-some-extent-in-the-US-as-well.1232770.0.html
- https://www.euenergyprices.eu/en/electricity/sk
- https://www.mediamarkt.at/de/product/_apc-br1500gi-back-ups-pro-usv-darkslategray-158470641.html
- https://www.saturn.de/de/product/_apc-br1500gi-back-ups-pro-usv-darkslategray-158470641.html
- https://www.comparateur-gamer.fr/prix/apc-br1500g-fr-7313042687348
- https://www.comparateur-gamer.fr/prix/apc-back-ups-bx-1600va-prises-iec-731304410829
- https://www.kaina24.lt/ru/s/bx1600mi/
- https://www.alza.at/cheap-mac-mini/18854903.htm

---

## Verification

Independent check, 2026-11-02, by a second agent trying to refute this file. Read-only: bundled docs, local `ls`, `lsof`, `--help` and `config get` commands, GitHub API, web pages. Nothing was installed or changed outside this file. All of it is the source-check evidence tier. No claim about the PC has been tested on hardware.

### Does the recommendation still hold?

**Yes, with five changes.** WSL2 Gateway plus Windows node remains the pick, because the deciding facts held: no Claude Code sandbox on native Windows, no worker isolation there, and Fusion and Resolve not running in WSL. The dedicated macOS user also stands. The changes are:

1. **PC network:** Tailscale Run unattended is mandatory. The first draft omitted it, and the design would have lost tailnet access at every reboot.
2. **Mac interim Serve:** Adam's admin user runs an externally managed route. A `jorah` Gateway using `tailscale.mode: serve` is not a safe assumption.
3. **Remote unlock:** FileVault SSH unlock has to come over the LAN, because the Standalone client has no tunnel before login.
4. **UPS:** CyberPower CP1500EPFCLCD replaces the APC BR1500GI, which does not meet the true-sine target.
5. **Media:** NVENC in WSL moves from doubtful to likely. If spike S5 passes, the render pipeline may not need `ffmpeg.exe` on Windows, and Resolve Studio's native MCP server becomes an option to test.

### What I checked

| # | Claim | Result | Source |
|---|---|---|---|
| 1 | Claude Code sandbox: macOS, Linux, WSL2 only. Native Windows unsandboxed. WSL1 no | Confirmed | https://code.claude.com/docs/en/sandboxing |
| 2 | Default runs unsandboxed. `failIfUnavailable` refuses. Repo sets it. AppArmor, bubblewrap, socat | Confirmed. Repo line 102, and line 104 also sets `allowUnsandboxedCommands: false` | same URL; `scripts/setup-permissions.sh` |
| 3 | Worker container isolation unsupported on Windows | Confirmed | docs:nodes/session-hosting.md |
| 4 | "ACPX routes cannot dispatch to a paired device" | Confirmed, exact text | docs:nodes/node-host.md |
| 5 | Voice wake on macOS 26+, iOS, Android, not Windows | Confirmed. Hub docs and README show push-to-talk and a voice hotkey only | docs:nodes/voicewake.md, docs:platforms/windows.md, Hub README |
| 6 | Windows `computer.act` experimental with listed limits | Confirmed. Added key limits and the single-display advice | docs:nodes/computer-use.md |
| 7 | Every Hub release is pre-release, so the doc's "stable" is wrong | **Refuted.** The first of six release pages shows only pre-releases, but `releases/latest` is non-pre-release v2026.9.8-1 | GitHub API |
| 8 | Tailscale on Windows host only, not both | Confirmed | https://tailscale.com/kb/1295/install-windows-wsl2 |
| 9 | Tailscale SSH server not on Windows or the Standalone Mac client | Confirmed | https://tailscale.com/kb/1193/tailscale-ssh, kb/1065 |
| 10 | Tailscale plans and limits | Confirmed. Added $1 per extra tagged resource | https://tailscale.com/pricing |
| 11 | Serve command and externally managed mode | Confirmed | kb/1242, local help, docs:gateway/tailscale.md |
| 12 | The PC design works with no one signed in | **Gap found.** Run unattended was missing | https://tailscale.com/kb/1088/run-unattended |
| 13 | A7: `tailscale.mode: serve` from `jorah` | **Not safe as written.** Proof file is admin-only. XPC path untested | local `ls -l /Library/Tailscale`; tailscale `safesocket_darwin.go`; kb/1065 |
| 14 | `.wslconfig` and `wsl.conf` keys, `instanceIdleTimeout=-1` | Confirmed. `vmIdleTimeout` is reported ineffective in issue 13416, so its comment changed | wsl-config page, issue 13416 |
| 15 | Issue 13416 open, versions 2.4.13 to 2.7.3. WSL 3.0.3 and 3.0.4 | Confirmed. The fallback's evidence is thin, about 20 minutes | GitHub |
| 16 | WSL kernel USB modules, from the 6.6 config | **Stale.** WSL 3.0.3 ships 6.18.54.1. The same modules are in the 6.18 config, so the conclusion holds | WSL release notes, kernel config |
| 17 | NVENC in WSL doubtful | **Out of date.** 2026 reports show it working with dynamic linking. No official NVIDIA statement | section 4 sources |
| 18 | Free Resolve lost scripting in 21.1 | Confirmed from Blackmagic directly. Scope is disputed. Missed the Studio MCP server and the price | Blackmagic readme, Digital Production, Puget |
| 19 | Fusion on Windows and macOS only | Consistent, but [unverified] from the primary page, which returned 403 | search summary |
| 20 | RTX 5090 about EUR 8,000 | **Overstated or unconfirmed.** The source contradicts itself. Geizhals-based report: EUR 5,243 in September | gpupricehistory, BetterFPS |
| 21 | RTX 5060 Ti 16 GB and 5070 Ti prices | Numbers match the pages. 5060 Ti and 5080 relabelled, because that aggregator is inconsistent | gpupricehistory, gpuprix |
| 22 | BR1500GI as a true-sine UPS | **Refuted, secondary evidence.** Listed as stepped approximation | automa.net, Schneider forum snippet |
| 23 | Mac mini M6 and M5 Pro. EUR 949 is a financing example | Confirmed. Start price still unknown | apple.com/de |
| 24 | Charge Limit in macOS 26.4+ | Confirmed, now from Apple | https://support.apple.com/en-us/102338 |
| 25 | FileVault unlock over SSH on macOS 26 | Consistent with Geerling. Still secondary. Added the tailnet limit | Jeff Geerling, kb/1065 |
| 26 | Windows Update, active hours 18, policy unreliable | Confirmed. Added that a device with no signed-in user is restarted | waas-restart page |
| 27 | Autologon LSA secret, Claude credential paths, Slovak electricity 19.85 ct, CUDA WSL limits | Confirmed. The electricity figure is a secondary site citing Eurostat | Microsoft, Anthropic, euenergyprices, NVIDIA |
| 28 | CLI forms: `connect --commands`, `approvals allowlist add --node`, `backup enable --to --every --keep-*`, `node run`, `openclaw-mac primary set`, `plugins enable cua-computer` | Confirmed in docs or `--help`. Node requirement 26.12.1+ confirmed from `package.json` | bundled docs and CLI |

### Not checked

The WSLg audio claim, Apple's closed-lid pages, the Telegram 24-hour retention line, the BX1600MI row, RX 9070 XT prices and the DDR5 notes were not rechecked. Treat them at the label they carry. Everything the first author marked as a spike remains a spike.
