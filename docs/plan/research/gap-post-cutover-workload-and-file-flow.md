# Gap: where heavy jobs run after cutover, and how large files move

Date: 2026-11-02. Research only. Nothing was installed, started or changed.

**Evidence tier of this whole file: source check.** Nothing here has run on a tagged device, in WSL, or on the PC. The brief asks for a transfer method "tested against tagged devices". That test could not be run: there is no PC, no tagged device exists, and Tailscale on this Mac reports `BackendState: NeedsLogin` [verified: local `tailscale status --json`, today]. So the method below is **chosen, not tested**. Section 7 is the test, with pass and fail lines.

**Labels.** M7, M9, M11, M12, M18, M19 and K10 come from the brief. No file in `docs/plan` defines them; a grep found none. I read them as: M7 and K10 are the Lab route spike, M9 is PC cutover, M11 depends on the Lab, M12 is video, M18 is vision, M19 is iOS. If the roadmap means something else, the table still holds and only the labels change.

**Search limit.** The web search budget for this run ran out, so three queries did not run: `sbx` inside WSL, NVENC in WSL, and WSL localhost across Windows users. Direct page reads still worked. Those three items stay open, and section 7 tests them.

---

## 1. Answer

1. **One media store.** Footage lives in ext4 inside the `jorah-gw` distro at `/srv/jorah-media`. The VHDX file can sit on the D: disk. There is no drvfs mount, so `mountFsTab=false` and T17 stay exactly as `security.md` wrote them.
2. **One transfer method: plain OpenSSH SFTP with chrooted, key-only accounts.** `sshd` listens on `127.0.0.1:2222` inside `jorah-gw`, and `tailscale serve --tcp=2222` publishes it from the Windows host. Windows users on the PC use the same port over localhost.
3. **Every media connection is started by a user device toward the tagged PC, or is local on the PC.** No media path starts from a tagged device, and none uses Taildrop or Tailscale SSH, so their tag limits never apply.
4. **GPU work goes through a spool, not a sandbox hole.** Delegated Claude Code writes a validated job file. A separate `jorah-media` systemd service reads it and uses the GPU. The sandbox gets no `excludedCommands` entry. Spike S5 must therefore test NVENC under that service, not in a plain shell.
5. **The Lab does not go under `jorah-desk`.** It gets its own Windows user `jorah-lab`, reached by a typed node-hosted MCP tool with `system.run` still denied. Split K10 in two: the route is testable on the Mac now, and the host only on the PC.
6. **iOS artifacts stay on the Mac.** Adam uploads through Transporter from there anyway, so only JSON results and small logs cross to the PC.

Result: M12 is built once against `$PROJECT/source` and a spool. The only per-OS parts are ingest and the encoder profile. Cost is EUR 0: no purchases or plan changes. It adds local accounts: `jorah-lab` on Windows, `jorah-build` on the Mac, and `jorah-media` plus three SFTP accounts in the distro.

---

## 2. Placement table (after M9)

| Job | Machine | OS user | Boundary | GPU | Why here | If it fails |
|---|---|---|---|---|---|---|
| Brain: Claude CLI, Gateway, memory, channels | PC, `jorah-gw` | Linux `jorah`, distro owned by Windows `jorah-svc` | Main has no `exec`; hardened distro, T17 | No | Topology pick [docs-only: `topology.md` s4] | Rescue bot on Mac, manual only |
| Delegated Claude Code, general | PC, `jorah-gw` | `jorah` | bubblewrap, no network, `failIfUnavailable` | **No**, expected blocked (section 5, item 4) | Native Windows runs it unsandboxed [verified: code.claude.com/docs/en/sandboxing, via `topology.md` fact 1] | No fallback outside the sandbox |
| Delegated Claude Code, iOS repos | Mac | `jorah-build` | Seatbelt, via root-owned `claude-task` wrapper | No | ACPX routes cannot dispatch to a paired device [verified: `docs:nodes/node-host.md`, via `topology.md` fact 5] | Wait for the Mac |
| Video transcription, V1 | PC, `jorah-gw` | `jorah` | bubblewrap | CPU: `faster-whisper` | No config change [docs-only: `creative.md` V3] | n/a |
| Video transcription, long jobs | PC, `jorah-gw` | `jorah-media` | systemd sandbox, `PrivateNetwork=yes` | CUDA | Same spool as render | CPU in the sandbox, slower |
| Video render, final and proxy | PC, `jorah-gw` | `jorah-media` | systemd sandbox, validated EDL only | NVENC if S5 passes | Stays in the hardened distro; no Windows hop | `libx264` in the same unit. **Not** Windows `ffmpeg.exe` |
| Lab: new tools, untrusted code | PC, Windows | **new** `jorah-lab`, standard user, Password task | `sbx` microVM per job, deny-all egress | None [docs-only: `growth.md`] | `sbx` lists Windows 11 with Windows Hypervisor Platform [verified: docs.docker.com/ai/sandboxes/install/]; WSL is not listed there | Mac `sbx` under its own dedicated user, then a Hyper-V Linux VM |
| Code CAD: build123d, gates | PC, `jorah-gw` | `jorah` | bubblewrap | No | Headless, Linux, creative pick | n/a |
| New CAD tools | Lab | `jorah-lab` | microVM | No | Growth tier rule | n/a |
| Fusion | PC, Windows | `jorah-desk`, leased console | Standard user, separate profile; Fusion API route is arbitrary Python [docs-only: `creative.md`] | Native | No Linux desktop build; needs a logged-in GUI [inference] | Mac under a dedicated user |
| Resolve, if ever bought | PC, Windows | `jorah-desk`, leased console | As Fusion | Native | Not in the MVP; manual FCP7 XML finish | Mac |
| iOS build, simulator, archive | Mac | `jorah-build` | Root-owned wrappers, no distribution certificate | n/a | Xcode is Mac-only | Wait for the Mac |
| iMessage bot, rescue bot | Mac | `jorah` | Own account, no builds run here | n/a | `topology.md` s8, narrowed by section 5, item 6 | n/a |
| Vision sidecar | The machine each camera is on | Mac: `adam` or signed app. PC: `jorah-desk` | Frames stay local | Local | `vision.md` V4 | Camera off |
| Robot bridges | Windows or Pi next to the arm | `jorah-desk`, or Pi user | Node-hosted MCP | n/a | `topology.md` s11, `robotics.md` conflict note | n/a |

**PC checks that decide tiers.** Specs are still unknown. Run `Get-PhysicalDisk | select FriendlyName,MediaType,Size`, `winver`, `dxdiag`, `wsl --version`.

| Tier | Disk | Layout |
|---|---|---|
| Minimum | 1 TB free NVMe, one disk | Default distro path. No D: needed |
| Recommended | 2 TB NVMe plus a second SSD | `distributionInstallPath=D:\\wsl` in `jorah-svc`'s `.wslconfig` before the distro is created [verified: learn.microsoft.com/en-us/windows/wsl/wsl-config] |
| Second disk is an HDD | NVMe plus HDD | Distro stays on NVMe. The HDD is Adam's cold archive only, filled from Adam's own Windows session |

One hour at 100 Mbps is about 52 GB per project: 45 source, 2.25 proxy, 4.5 final, 0.1 audio [arithmetic from `creative.md` s4.7].

---

## 3. Data-flow table

| # | From | To | Method | Auth | Crosses tailnet? | Size class |
|---|---|---|---|---|---|---|
| F1 | OBS or camera files on Mac (`adam`) | `/srv/jorah-media/incoming` | SFTP to `pc.<tailnet>.ts.net:2222` | SSH key in `adam`'s home, plus tailnet grant | Yes, user device to tagged PC | Any |
| F2 | OBS or SD card on PC (Windows `adam`) | Same | SFTP to `127.0.0.1:2222` | Separate key | No | Any |
| F3 | iPhone footage | Mac or PC first, then F1 or F2 | AirDrop or USB by Adam | n/a | No | Any. No phone upload in the MVP |
| F4 | `incoming` | `projects/<slug>/source` | `jorah-ingestd`: SHA-256 check, `ffprobe` with no network, move, mode 0440 owned by `jorah-media` | Local Linux users | No | Any |
| F5 | `source` | Delegated Claude Code | Read-only path in the sandbox's `allowRead` | Linux group | No | Any |
| F6 | Claude Code | Worker | `edl.json` plus job file in `spool/<slug>/` | Sandbox `allowWrite`; worker validates schema | No | Small |
| F7 | Worker | `projects/<slug>/render`, `review/<slug>` | Local write | systemd `ReadWritePaths` | No | Any |
| F8 | `review/<slug>` | Adam's iPhone or Mac | HTTPS, `tailscale serve --https=8443` to `127.0.0.1:<review-port>` | Serve identity header **and** a per-review random token | Yes, user device to tagged PC | Proxy, 2.25 GB per hour |
| F9 | `finals/<slug>` | Adam | Download from the review page, or `sftp get` over F1 | Same as F8 or F1 | Yes | About 4.5 GB. YouTube upload stays manual |
| F10 | `jorah-gw` and `jorah-desk` | Fusion or Resolve handoff, both ways | SFTP over localhost; files under 16 MiB may use `file.fetch` and `file.write` | `xfer-desk` key and chroot | No | Mixed |
| F11 | `jorah-gw` and `jorah-lab` | Lab job files, both ways | SFTP over localhost, then `sbx cp`. Output arrives in quarantine and never runs | `xfer-lab` key and chroot | No | Mixed |
| F12 | Mac `jorah-build` | Gateway | JSON result; logs under 16 MiB by `file.fetch` | Node pairing over `wss://` | Yes, user device to tagged PC | Small |
| F13 | Mac `jorah-build` | Mac `adam` | `.ipa` copied to `/Users/Shared/jorah-handoff/<run-id>`; Adam uploads with Transporter | macOS permissions | No | Any |
| F14 | Vision frames | Local sidecar only | Never cross. Only events reach the Gateway | Node or loopback token | Events only | Small |
| F15 | Saved clip for an edit | F1 or F2 | Only when Adam says yes, as an ordinary ingest | As F1 | Yes, if on Mac | Any |
| F16 | Backups, `imsg` wrapper | PC to Mac port 22 | Plain OpenSSH to macOS Remote Login | Restricted key plus grant | Yes, **tagged to user**. The only such path. Holds no media | Small to medium |

**M18 reconciled.** "Only events cross Tailscale" stays true for live perception. Footage for editing is a separate, deliberate action by Adam (F15), so the two rules do not conflict.

**Windows users cannot browse the store.** Distros are per Windows user [docs-only: `docs:platforms/windows.md`, cited at `topology.md` s5], so `\\wsl.localhost\jorah-gw` should not appear for `adam` or `jorah-desk` [inference]. F2, F10 and F11 need the socket path for that reason.

---

## 4. The transfer method

**Pick: OpenSSH SFTP into `jorah-gw`, published by `tailscale serve --tcp`.**

Why:
- SFTP clients ship with macOS and with Windows' OpenSSH [verified: local `man sftp`; learn.microsoft.com openssh-overview]. That page says Windows 10 has the feature as "not installed" and does not list Windows 11, so check `sftp` on the PC.
- Resume is built in: `sftp -a` and `reput` continue a partial upload [verified: local `man sftp`, OpenSSH 10.3p1].
- `internal-sftp` in a chroot gives no shell. Read-only mode and denied requests are available through `-R`, `-P` and `-p` [verified: local `man sshd_config`, `man sftp-server`].
- It depends on no alpha Tailscale feature. Raw TCP forwarding through Serve is documented, and `--bg` survives a reboot [verified: tailscale.com/kb/1242/tailscale-serve; local `tailscale serve --help`].
- It survives S2 failing. If Serve into WSL does not work, topology's fallback puts Tailscale inside WSL, and only the address changes.

```
# Windows, tailnet device owner
tailscale serve --bg --tcp=2222 tcp://127.0.0.1:2222
tailscale serve --bg --https=8443 http://127.0.0.1:<review-port>

# jorah-gw, /etc/ssh/sshd_config.d/jorah-media.conf (shape, untested)
ListenAddress 127.0.0.1:2222
PasswordAuthentication no
AllowUsers xfer-ingest xfer-desk xfer-lab
AuthorizedKeysFile /etc/ssh/keys/%u
Match User xfer-ingest,xfer-desk,xfer-lab
  ChrootDirectory /srv/jorah-media/chroot/%u
  ForceCommand internal-sftp -d /files -P symlink,hardlink
  AllowTcpForwarding no
  X11Forwarding no
  PermitTTY no
```

Grant changes to `topology.md` s6, narrower than its owner-wide rule:

```json5
{ "src": ["adam-mac"],      "dst": ["tag:jorah-pc"], "ip": ["tcp:2222", "tcp:8443"] },
{ "src": ["adam-iphone"],   "dst": ["tag:jorah-pc"], "ip": ["tcp:8443"] },
// tests
{ "src": "adam-mac",        "accept": ["tag:jorah-pc:2222", "tag:jorah-pc:8443"] },
{ "src": "adam-iphone",     "accept": ["tag:jorah-pc:8443"], "deny": ["tag:jorah-pc:2222"] },
{ "src": "tag:jorah-pc",    "deny":   ["adam-mac:2222", "adam-mac:445", "adam-iphone:8443"] }
```

**Adam's use.** A small `jorah-send <file> <slug>` script on the Mac and PC shows size, estimated time and free space on the PC, then uploads only after Adam's yes. It writes the SHA-256 sidecar. Originals stay where they were, and Jorah never deletes them. No watcher or schedule exists on Adam's folders.

**Review page auth.** Serve strips incoming identity headers and adds `Tailscale-User-Login`; those headers are absent for tagged sources [verified: tailscale.com/kb/1312/serve]. The same page warns that other services on the Serve device can still spoof them over localhost. On this PC, that means any Windows user, because WSL's localhost is reachable from Windows [inference]. So the page requires both the header and a random token in the URL. A token in the URL also survives the media player's range requests, where a cookie may not [inference; `apps.md` T14 measures it].

**Rejected:**

| Option | Why not | Evidence |
|---|---|---|
| Taildrop (`tailscale file cp`) | Cannot send to or from tagged nodes; alpha | [verified: tailscale.com/kb/1106/taildrop] |
| Tailscale SSH | No Windows server; tagged to user not permitted; this Mac's Standalone client cannot host it | [verified: tailscale.com/kb/1193/tailscale-ssh; `topology.md` fact 12] |
| Taildrive | Alpha. Tagged devices can be targets, but the share is on Windows, and WSL would still need a mount | [verified: tailscale.com/kb/1369/taildrive] |
| OpenClaw File Transfer | 16 MiB per file | [verified: `docs:nodes/file-transfers.md`] |
| drvfs `D:\jorah-media` by fstab | Needs `mountFsTab=true`, and Microsoft advises against working across file systems | [verified: learn.microsoft.com/en-us/windows/wsl/filesystems] |
| SMB share (`connectors.md`) | Reaches Windows only. WSL would need a root mount, and tailnet port 445 opens | [inference] |
| Second VHDX, `wsl --mount` | Needs administrator; `jorah-svc` is standard. The attach would need elevation at each boot | [verified: learn.microsoft.com/en-us/windows/wsl/wsl2-mount-disk] |
| rsync | macOS has openrsync at protocol 29, Windows has none, and video does not benefit from delta | [verified: local `rsync --version`; Windows part is inference] |
| OpenClaw Portals for review | Meant for dev servers, and prefers managed Serve, which topology ruled out on this PC | [docs-only: `docs:gateway/portals.md`]. Runner-up if S2 changes that |

**Runner-up:** SFTP to Windows OpenSSH on a D: folder, with the WSL worker pulling over the host IP. It adds a Windows service and a firewall opening, so it stays second.

**What would change the pick:**
- Under 30 MB/s on wired LAN in T6. At that speed, 45 GB takes 25 minutes. First check `tailscale ping` for a relayed path, and then consider topology's Tailscale-in-WSL fallback.
- A Windows-side worker becoming necessary.
- ProRes sources, which are hundreds of GB per hour [`creative.md`].

---

## 5. Contradictions settled

| # | Conflict | Winner | Why |
|---|---|---|---|
| 1 | `topology.md` s4 `mountFsTab=true` with a drvfs media folder, against `security.md` `mountFsTab=false` | **security** | The store works without it. **A correction to the brief:** T17 as written tests hand mounts by Jorah's user, so a root-configured fstab line would pass T17. The real conflict is the two `wsl.conf` blocks. Delete topology's fstab line |
| 2 | `topology.md` s13 "Media: D: drive" | **Both, reworded** | "Physically on D:, inside the distro's ext4 VHDX" keeps topology's disk plan and security's boundary |
| 3 | `creative.md` line 179 APFS clones and line 364 "Tailscale file copy" | **This file** | Replace with an `ingest` verb. Mac: `cp -c`. Linux: move plus read-only ownership. ext4 has no reflink copy [inference, from memory], and none is needed. Line 364 becomes SFTP |
| 4 | `creative.md` "NVENC or CUDA under the WSL2 sandbox [unverified]" | **Expected blocked** | `sandbox-runtime` uses `--dev /dev` and skips `/dev/*` paths, [verified: github.com/anthropic-experimental/sandbox-runtime, `linux-sandbox-utils.ts`]. A string search of the full file finds no `dxg`, `nvidia` or `/dev/dri`. That is public source, not Claude Code's own build, and T9 confirms it |
| 5 | `creative.md` `media-worker` as the single `excludedCommands` entry, against `security.md`'s sandbox position | **Spool** | A service reading job files needs no sandbox exception, on Mac or PC. This removes the yes that `creative.md` asks Adam for. A separate service account is still a new capability, so Adam previews the unit |
| 5a | `topology.md` s10 Windows `ffmpeg.exe` if WSL lacks NVENC | **`libx264` in the worker** | `ffmpeg.exe` needs a Windows hop, unsandboxed execution and a file route. CPU encode needs nothing new. Revisit only if T8 fails **and** Adam finds CPU times too slow |
| 6 | `topology.md` Mac `jorah` runs builds, iMessage and rescue, against `security.md` `jorah-build` | **security** | Build scripts run third-party code. They should not share an account with the bot's Messages session or the rescue profile. Cost is one account. It adds no node, because `jorah` needs none |
| 7 | `topology.md` s9 ".ipa over 16 MB goes by restricted SSH" | **Stays on the Mac** | Adam's rule is that Adam uploads from there. F13 removes the crossing |
| 8 | `growth.md` GUI tier in a VM for Fusion, against `topology.md` `jorah-desk` | **topology, for Fusion only** | Signed vendor app in a standard user, and `growth.md` says licensing in a VM was not researched. Unknown GUI apps still use growth's VM tier |
| 9 | `connectors.md` s11 "SMB or rsync, creative owns it" | **This file** | Inbox and outbox with File Transfer stay for small files |
| 10 | `security.md` s11 tags the phone and Mac node, against `topology.md` s6 keeping them user devices | **topology** | Tags are for machines, and Tailscale advises against them on end-user devices [verified: tailscale.com/kb/1068/tags]. A tagged phone would also lose Serve identity headers and break F8 |

---

## 6. K10 and the Lab: the question M7 should ask

**Why not `jorah-desk`** [inference]:
- Its node host needs an interactive session under a lease [verified: `docs:nodes/computer-use.md`, `docs:platforms/windows.md`], so the Lab would stop whenever no console is leased.
- A microVM escape would land next to COM ports, robot bridges and `computer.act`.
- It would make one identity hold every surface.

**Why not `system.run`.** `gateway.nodes.commands.deny` covers all nodes [docs-only: `security.md` s5], and approvals have been bypassed before, in CVE-2026-28466 [`security.md`]. Node-hosted MCP is a separate family: calls go through `mcp.tools.call.v1` [docs-only: `docs:nodes/mcp-and-skills.md`]. So try this:

- Keep `system.run` denied for every node, permanently if it works.
- Publish `jorah_lab` verbs from `jorah-lab`, and `ios_build`, `ios_test`, `ios_archive` from `jorah-build`, as MCP servers with fixed arguments.

**A catch that shapes the spike.** `--commands` disables MCP servers on that node [docs-only: `docs:nodes/node-host.md`]. So an MCP node cannot also shrink its surface that way, and it keeps its default surface minus Gateway denies. The Gateway deny list and per-node approvals have to hold, and T15 proves that. Tool lists can also change live [same doc], so the server must be our own pinned code, with its files owned by an admin.

**A second catch, which needs Adam's yes.** `security.md` s5 sets `gateway.nodes.pluginTools.enabled: false`, and that setting hides node-hosted MCP tools from agents [docs-only: `docs:nodes/mcp-and-skills.md`]. So this route must turn it on, for all nodes. That is safe only if each node publishes only our own servers, and any node that needs nothing else runs with `--commands`. This is a real trade: one global switch on, in exchange for `system.run` staying off.

**Unattended start.** S4U gives no Windows network credentials or access to encrypted files [verified: `docs:platforms/windows.md`]. `sbx` stores secrets and has a per-user daemon, and its docs do not say whether a login session is needed [verified: docs.docker.com/ai/sandboxes/install/, FAQ]. So plan on a Password task and test with nobody logged in.

**Split K10:**

| Spike | Where | Question | Fail means |
|---|---|---|---|
| K10a route | **Mac now**, `jorah` or test node | With `system.run` denied and `pluginTools.enabled: true`, can main on the Claude CLI runtime call a typed node-published MCP tool with no free-form string? `security.md` has a global `tools.deny` on `nodes`: does the tool still appear? | Use `--commands system.run,system.run.prepare` with one allowlisted wrapper on that node. This reopens `system.run` narrowly and needs Adam's yes |
| K10b host | PC, stage C | Does `sbx` 0.50.1+ start, create, run and remove a VM as `jorah-lab`, after a reboot, with nobody signed in? Does the microVM fail to reach `100.x` and `127.0.0.1:2222`? | Mac Lab, then a Hyper-V Linux VM |

**`sbx` inside WSL stays rejected.** The install page lists Ubuntu with KVM, not WSL. Nested virtualization is on by default in WSL [verified: wsl-config], and the FAQ mentions "some WSL setups" for secret storage [verified], so it may work. But an escape would land beside the Gateway's tokens. Reconsider only if K10b fails and Windows is Home.

**Order.** K10a before M7 closes, and K10b in the PC stage. That keeps the PC-before-Lab order and stops M7 from testing `jorah-desk`.

---

## 7. The test (not run)

Needs Adam: Tailscale sign-in, the tag, and the grant preview. Tiers: **P** is policy accepted, **N** is a real network transfer, **D** is Adam's acceptance on the device.

**Stage A, before the PC, about one hour.** Uses a disposable Linux VM or container with an ephemeral node tagged `tag:jorah-test`. Tear down afterwards.

| # | Step | Pass | Tier |
|---|---|---|---|
| T1 | Save the grants and `tests` block | Admin console accepts; deny lines hold | P |
| T2 | Negative control: `tailscale file cp small.bin <tagged>:` from the Mac | **Must fail**. If it works, the KB is out of date; note it and still do not use it | N |
| T3 | On the tagged node: `tailscale serve --bg --tcp=2222 tcp://127.0.0.1:2222`, chrooted `sshd`. From the Mac: `sftp -a -P 2222` a 5 GB file, kill it halfway, resume, compare SHA-256 | Hashes match, and the resume did not restart | N |
| T4 | From the Mac: `ssh -p 2222` to get a shell, make a symlink, escape to `/` | All refused | N |
| T5 | Plain OpenSSH from the tagged node to the Mac port 22, with Remote Login on only for this test and Adam's yes | Connects. This settles whether "tagged can SSH only to tagged" affects plain SSH. Neither `kb/1068` nor `kb/1324` says so [inference that it does not] | N |

If T5 fails, F16 (backup and `imsg`) needs rework. The media flows are unaffected.

**Stage B, on the PC, tied to S2 and S5.**

| # | Step | Pass | Tier |
|---|---|---|---|
| T6 | Mac to `pc:2222`, 45 GB, wired LAN, with `jorah-svc` not signed in, after a reboot | Works; at least 30 MB/s; hashes match; `tailscale ping` shows direct | N |
| T7 | From Windows `adam`, `jorah-desk` and `jorah-lab`: `sftp -P 2222 127.0.0.1` | All connect to their own chroot only. Answers the cross-user localhost question from S2 | N |
| T8 | S5 rewritten: real `h264_nvenc` encode **as a `jorah-media` systemd unit**, with `PrivateNetwork=yes`, `DeviceAllow=/dev/dxg`, `ProtectHome=yes` | Output file plays, and encoder use shows in Task Manager. Record yes or no | N |
| T9 | The same `ffmpeg` and `nvidia-smi` inside a delegated Claude Code run | Expected to **fail**. If it works, section 5 item 4 is wrong | N |
| T10 | T17 in full, after the store and `sshd` exist, plus: `ls /mnt`, `jorah` writing to `source/`, `jorah` writing to `/etc/ssh/keys` | All fail or read-only | N |
| T11 | Review page on iPhone over cellular, 720p proxy, seek at 10 points. Then no token, and then a spoofed header from a Windows localhost client | Seek under `apps.md` T14's limit; both bad cases refused | D |
| T12 | Render at full load while Jorah answers on Telegram | Gateway answers; worker capped by `MemoryMax` | N |
| T13 | Fill the store to the guard limit, then ingest | `jorah-ingestd` refuses and names the free space; Gateway keeps writing | N |
| T14 | One real video through F1 to F9 | Adam accepts the result on the phone | D |

---

## 8. Edits this implies for each track

| File | Change |
|---|---|
| `topology.md` | Delete the fstab line and set `mountFsTab=false`; reword s13 media; add `jorah-lab`, `tcp:2222`, `tcp:8443`; rewrite S5 per T8; split builds into `jorah-build`; drop the `.ipa` SSH route; drop `ffmpeg.exe` as the default fallback |
| `security.md` | Add T7, T9, T10, T13 to the test list; change `pluginTools.enabled` only if K10a passes and Adam agrees; drop the phone and Mac tags from s11; add the `jorah-media`, `xfer-*` and `jorah-lab` accounts to the threat model; record the attempt to keep `system.run` denied |
| `creative.md` | `ingest` verb in place of `cp -c` as the design; spool in place of `excludedCommands`; lines 179 and 364 |
| `growth.md` | PC Lab under `jorah-lab`; route result from K10a; `put` and `get` over F11 |
| `apps.md`, `ux.md` | Review page URL, token and header auth; own service on 8443 |
| `vision.md` | PC sidecar under `jorah-desk`; see the risk below on sessions |
| `connectors.md` | s11 points here for large files |

---

## 9. Risks and what could not be confirmed

| Item | State | Handling |
|---|---|---|
| Cross-user localhost into `jorah-svc`'s WSL | **Unconfirmed**. Microsoft documents host localhost, and says nothing on other Windows users. Search did not run | T7. It is also an S2 dependency for the Gateway itself |
| NVENC on WSL | No NVIDIA statement. The CUDA on WSL guide does not mention NVENC or `/dev/dxg` [verified: docs.nvidia.com/cuda/wsl-user-guide]. Community reports only, from `topology.md` | T8, with `libx264` as the fallback |
| `DeviceAllow` for `/dev/dxg` under WSL cgroups | Unconfirmed [inference] | T8 |
| `sbx` unattended on Windows | Unconfirmed | K10b |
| Node-published MCP on the Claude CLI runtime | Unconfirmed | K10a |
| Serve raw-TCP speed on Windows, through the WSL relay | No benchmark exists here | T6 |
| Media and Gateway state share one volume | Real. A full disk can stop the Gateway. The sftp upload itself is not bounded by the guard. A hard cap (quota or a loop image) is unverified in the WSL kernel | Soft guard first; T13; add a cap if the kernel allows |
| One VHDX holds working footage | A corrupt file loses working copies | Originals stay with Adam; `openclaw backup` excludes media. Keep state backups separate |
| PC camera needs a user session | Windows services run in session 0 [verified: `engineering.md` citing Microsoft], and `jorah-desk` has no autologon | M18's PC camera is live only during a session. Open decision for Adam, topology's runner-up |
| GPU contention: render, models, sidecar | Not measured | Worker runs one GPU job at a time. Check NVIDIA's session limits for Adam's card |
| Grant selector detail | `kb/1324` does not state tag `src` to host alias `dst` for this case; `topology.md` cites the targets page | T1 |

**Evidence tiers now:** source check only. Not installed, not launched, nothing on a signed-in device.

---

## 10. Sources

**Primary, read today:**
[Taildrop](https://tailscale.com/kb/1106/taildrop),
[Tags](https://tailscale.com/kb/1068/tags),
[Tailscale SSH](https://tailscale.com/kb/1193/tailscale-ssh),
[Serve CLI](https://tailscale.com/kb/1242/tailscale-serve),
[Serve](https://tailscale.com/kb/1312/serve),
[Taildrive](https://tailscale.com/kb/1369/taildrive),
[Grants](https://tailscale.com/kb/1324/grants),
[Windows and WSL 2](https://tailscale.com/kb/1295/install-windows-wsl2),
[WSL config](https://learn.microsoft.com/en-us/windows/wsl/wsl-config),
[WSL disk mount](https://learn.microsoft.com/en-us/windows/wsl/wsl2-mount-disk),
[WSL file systems](https://learn.microsoft.com/en-us/windows/wsl/filesystems),
[WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking),
[OpenSSH for Windows](https://learn.microsoft.com/en-us/windows-server/administration/openssh/openssh-overview),
[sbx install](https://docs.docker.com/ai/sandboxes/install/),
[sbx FAQ](https://docs.docker.com/ai/sandboxes/faq/),
[sbx architecture](https://docs.docker.com/ai/sandboxes/architecture/),
[sandbox-runtime Linux source](https://github.com/anthropic-experimental/sandbox-runtime/blob/main/src/sandbox/linux-sandbox-utils.ts),
[CUDA on WSL](https://docs.nvidia.com/cuda/wsl-user-guide/index.html).

**Local:** OpenClaw 2026.10.9 docs at `/opt/homebrew/lib/node_modules/openclaw/docs`: `nodes/file-transfers.md`, `nodes/mcp-and-skills.md`, `nodes/node-host.md`, `nodes/session-hosting.md`, `platforms/windows.md`, `gateway/tailscale.md`, `gateway/portals.md`, `plugins/reference/file-transfer.md`. Commands: `tailscale status --json`, `tailscale serve --help`, `tailscale file --help`, `rsync --version`, `man sftp`, `man sftp-server`, `man sshd_config`, `ssh -V`.

**Peer tracks:** `topology.md`, `security.md`, `creative.md`, `growth.md`, `apps.md`, `vision.md`, `connectors.md`, `engineering.md`, `robotics.md`, `openclaw-fit.md`, `ux.md`.
