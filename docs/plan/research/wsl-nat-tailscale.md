# WSL NAT networking with Tailscale in the distro: research

Research by Antigravity (Gemini 4 Argon High), 2026-11-08, for roadmap step 4 (semantic memory search). Not checked by Claude: shelved the same day, because agentmemory runs its embeddings in-process and needs no networking change. Verify before acting on it.

# Research Report: Moving WSL2 (`jorah`) from Mirrored to NAT Networking with In-Distro Tailscale

---

## 1. Loopback (`127.0.0.1`) Isolation and `localhostForwarding` in NAT Mode

* **Is `127.0.0.1` isolated in both directions?**
  * **Distro $\rightarrow$ Windows (`127.0.0.1`): Isolated.** In `networkingMode=nat` (the WSL2 default), the Linux distribution runs inside a utility VM with its own network namespace. `127.0.0.1` (`lo`) inside the distro refers exclusively to the Linux guest; a Linux process connecting to `127.0.0.1` cannot reach services listening on Windows' `127.0.0.1`. To reach the Windows host from Linux in NAT mode, traffic must target the Windows host's IP address on the `vEthernet (WSL)` switch.
    * *Source:* [Microsoft Learn — Accessing network applications with WSL](https://learn.microsoft.com/en-us/windows/wsl/networking)
  * **Windows $\rightarrow$ Distro (`127.0.0.1`): Not isolated by default** (controlled by `localhostForwarding`).
* **What `localhostForwarding` does and its default:**
  * Configured in `%USERPROFILE%\.wslconfig` under `[wsl2]`.
  * **Default:** `true`.
  * **Behavior:** Specifies whether ports bound to wildcard (`0.0.0.0`) or `localhost` (`127.0.0.1` / `::1`) inside the WSL2 VM are connectable from the Windows host via `localhost:<port>` / `127.0.0.1:<port>`, bridged over Hyper-V sockets (`hvsocket`) by `wslrelay.exe` on Windows. (In `mirrored` mode, `localhostForwarding` has no effect.)
    * *Sources:* [Microsoft Learn — Advanced settings configuration in WSL (`.wslconfig`)](https://learn.microsoft.com/en-us/windows/wsl/wsl-config), [microsoft/WSL#10601](https://github.com/microsoft/WSL/issues/10601)
* **Can Windows still reach a service the distro binds on `127.0.0.1`?**
  * **Yes**, when `localhostForwarding=true` (the default). Services bound to `127.0.0.1:43181` and `127.0.0.1:43210` inside `jorah` remain reachable from Windows at `127.0.0.1:43181` and `127.0.0.1:43210` (unless `localhostForwarding=false` is set, or `wslrelay.exe` encounters a stuck-port/standby bug).
    * *Sources:* [Microsoft Learn — Accessing network applications with WSL](https://learn.microsoft.com/en-us/windows/wsl/networking), [microsoft/WSL#14005](https://github.com/microsoft/WSL/issues/14005)

---

## 2. Tailscale Inside a WSL2 Distro in NAT Mode

* **Supported?**
  * **Yes**, Tailscale documents installing the Linux client inside WSL2, though with an explicit caveat recommending running Tailscale on the Windows host only rather than simultaneously on both Windows and WSL2.
    * *Source:* [Tailscale KB 1165 — Install Tailscale on Windows with WSL 2](https://tailscale.com/kb/1165/wsl2)
* **Needs `systemd`?**
  * Standard Ubuntu/Debian packages install and manage `tailscaled` via `systemd` (`tailscaled.service`), which requires `[boot] systemd=true` in `/etc/wsl.conf` (enabled by default in Ubuntu 24.04 on WSL2). Without `systemd`, `tailscaled` must be supervised manually.
    * *Source:* [Microsoft Learn — Manage Linux services with systemd in WSL](https://learn.microsoft.com/en-us/windows/wsl/systemd)
* **`tun` device available?**
  * **Yes.** The official Microsoft WSL2 kernel includes the TUN driver built-in (`CONFIG_TUN=y`), providing `/dev/net/tun` out of the box so `tailscaled` creates a native `tailscale0` interface without falling back to userspace networking.
    * *Sources:* [Tailscale KB 1165 — WSL 2](https://tailscale.com/kb/1165/wsl2), [microsoft/WSL2-Linux-Kernel](https://github.com/microsoft/WSL2-Linux-Kernel)
* **Known problems:**
  1. **MTU mismatch (`1280` on `eth0`) and MTU drift:**
     * WSL2 frequently initializes or resets guest `eth0` to an MTU of `1280` (especially when a host VPN/Tailscale Wintun adapter with MTU `1280` is active on Windows). Because `tailscale0` also requires a minimum MTU of `1280`, encapsulating WireGuard headers over an `eth0` with MTU `1280` drops large packets (TLS handshakes, SSH, HTTP streams).
     * Tailscale added `fixupWSLMTU` ([tailscale/tailscale#7441](https://github.com/tailscale/tailscale/pull/7441)) to bump `eth0` MTU (to `1360`/`1340`) when `tailscaled` starts. However, `fixupWSLMTU` only runs once at `tailscaled` startup; if `eth0` drifts back to `1280` after host network transitions or sleep/wake, large packets blackhole until `tailscaled` restarts or `ip link set dev eth0 mtu 1360` is re-applied.
     * *Sources:* [Tailscale KB 1165](https://tailscale.com/kb/1165/wsl2), [tailscale/tailscale#4833](https://github.com/tailscale/tailscale/issues/4833), [tailscale/tailscale#7346](https://github.com/tailscale/tailscale/issues/7346), [tailscale/tailscale#21659](https://github.com/tailscale/tailscale/issues/21659)
  2. **DNS conflicts (`/etc/resolv.conf` vs. MagicDNS `100.100.100.100`):**
     * In NAT mode, WSL2 auto-generates `/etc/resolv.conf` pointing to `10.255.255.254` (when `dnsTunneling=true`, default in Windows 11 22H2+) or the `vEthernet (WSL)` gateway `172.x.x.1` (when `dnsTunneling=false`). If Linux `tailscaled` runs with `--accept-dns=true` (default), it overwrites `/etc/resolv.conf` with `100.100.100.100`, clashing with WSL's resolver regeneration or chaining MagicDNS through Windows Tailscale's MagicDNS. Running `tailscale up --accept-dns=false` inside the distro avoids overwriting WSL's `/etc/resolv.conf`.
     * *Sources:* [Microsoft Learn — WSL Networking (DNS Tunneling)](https://learn.microsoft.com/en-us/windows/wsl/networking), [tailscale/tailscale#4833](https://github.com/tailscale/tailscale/issues/4833)
  3. **Duplicate hostnames on the tailnet:**
     * By default, WSL2 inherits the Windows host's hostname, causing the distro node to register on the same tailnet as `<windows-hostname>-1` unless `[network] hostname = jorah` is set in `/etc/wsl.conf` or `tailscale up --hostname=jorah` is used.
     * *Sources:* [Tailscale KB 1165](https://tailscale.com/kb/1165/wsl2), [Microsoft Learn — `wsl.conf`](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)
* **Can `tailscale serve` inside the distro publish `127.0.0.1` services?**
  * **Yes.** `tailscale serve` only proxies to `127.0.0.1` / `localhost` targets and supports multiple HTTPS ports on the node's `.ts.net` name (e.g., port `443` $\rightarrow$ `http://127.0.0.1:43181` and port `8443` $\rightarrow$ `http://127.0.0.1:43210`). OpenClaw also supports `gateway.tailscale.mode: "serve"` with `gateway.bind: "loopback"`.
    * *Sources:* [Tailscale KB 1312 — Tailscale Serve](https://tailscale.com/kb/1312/tailscale-serve), [OpenClaw Docs — Gateway Tailscale](https://docs.openclaw.ai/gateway/tailscale)
* **Unattended start at boot with no Windows user signed in:**
  * Tailscale's `--unattended` flag ([Tailscale KB 1182](https://tailscale.com/kb/1182/run-unattended)) is specific to Windows/macOS GUI clients. On Linux, `tailscaled.service` runs as a system daemon under `systemd` using state in `/var/lib/tailscale/tailscaled.state` and requires no user sign-in once authenticated.
  * Because the existing Windows Scheduled Task (S4U, no sign-in) launches and holds open the `jorah` distro at Windows boot, `systemd` starts inside `jorah` at boot and brings up `tailscaled.service` (including persisted `tailscale serve --bg` rules) without any interactive login.
    * *Sources:* [Tailscale KB 1182 — Run Unattended](https://tailscale.com/kb/1182/run-unattended), [Microsoft Learn — systemd in WSL](https://learn.microsoft.com/en-us/windows/wsl/systemd), [Tailscale KB 1312](https://tailscale.com/kb/1312/tailscale-serve)

---

## 3. Reachability When Both Windows and Distro Run Tailscale (Routing Loops & Subnet Exclusions)

* **Official warning on running both simultaneously:**
  * Tailscale KB 1165 states: *"If you run Tailscale on both the Windows host and inside WSL 2 at the same time, Tailscale encrypted traffic that flows from WSL 2 over Tailscale on the Windows host will not work due to Tailscale packets not being able to fit in Tailscale packets. For this reason it is recommended that users run Tailscale on the Windows host only, and not inside WSL 2."*
    * *Source:* [Tailscale KB 1165 — WSL 2](https://tailscale.com/kb/1165/wsl2)
* **Can the distro node be reached over the tailnet by other nodes (e.g., the Mac) while Windows Tailscale is also running?**
  * **Yes, from third-party tailnet peers (like the Mac), with caveats:**
    * Outer WireGuard UDP packets (or TCP 443 DERP packets) sent by the distro's `tailscaled` to the Mac's physical LAN/WAN IP or DERP server IP are routed by Windows `WinNAT` out the physical network interface — not through the Windows Tailscale `100.64.0.0/10` interface — **as long as Windows Tailscale is not using an Exit Node** (`--exit-node`) and `eth0` MTU inside WSL2 is kept above `1280` (`fixupWSLMTU` / `1360`+).
    * **Where double-encapsulation fails:** Traffic routed **between the WSL2 Tailscale node and the Windows host's own Tailscale IP**, or all WSL2 Tailscale traffic when the Windows host uses a Tailscale **Exit Node**, flows as inner Tailscale packets inside outer Windows Tailscale packets (`1280` inside `1280` MTU) and stalls/drops on large payloads.
    * *Sources:* [Tailscale KB 1165](https://tailscale.com/kb/1165/wsl2), [tailscale/tailscale#4833](https://github.com/tailscale/tailscale/issues/4833), [tailscale/tailscale#7346](https://github.com/tailscale/tailscale/issues/7346)
* **Any routing loops or need to exclude the WSL subnet?**
  * WSL2 NAT allocates a dynamic subnet from `172.16.0.0/12` (commonly a `/20`) on `vEthernet (WSL)`. Neither Tailscale instance advertises this subnet by default.
  * **When a routing conflict occurs:** If another node on the tailnet advertises a subnet route overlapping `172.16.0.0/12` (or `10.0.0.0/8` when `10.255.255.254` DNS tunneling is used) and either Windows Tailscale or distro Tailscale has `--accept-routes=true`, Tailscale's routing table (table `52` on Linux) can hijack local `vEthernet (WSL)` or DNS tunneling traffic. Keeping `--accept-routes=false` (the Linux default) on the distro node and avoiding overlapping `172.16.0.0/12` subnet advertisements prevents this without manual route exclusions.
    * *Sources:* [tailscale/tailscale#14995](https://github.com/tailscale/tailscale/issues/14995), [tailscale/tailscale#19313](https://github.com/tailscale/tailscale/issues/19313)

---

## 4. Firewall Impact in NAT Mode (Host/LAN Reachability and `nftables` Rules)

* **Can the distro reach the Windows host or LAN in NAT mode, and through which address?**
  * **Windows host:** **Yes.** In NAT mode, the distro reaches the Windows host via the `vEthernet (WSL)` switch IP (the default gateway shown by `ip route show | grep default`, typically `172.x.x.1` in `172.16.0.0/12`), as well as via the Windows host's physical LAN IPs (`192.168.x.x` / `10.x.x.x`) and Windows' Tailscale IP (`100.x.y.z`) if Windows Firewall permits inbound traffic from `vEthernet (WSL)`.
  * **LAN:** **Yes.** Outbound packets from the distro to LAN addresses (`192.168.0.0/16`, `10.0.0.0/8`, `172.16.0.0/12`) are NATed by Windows (`WinNAT`) onto the physical network and reach LAN hosts directly.
    * *Source:* [Microsoft Learn — Accessing network applications with WSL](https://learn.microsoft.com/en-us/windows/wsl/networking)
* **What an `nftables` rule in the distro needs to block/allow for the agent service user (`meta skuid <agent_uid>`):**
  * **Allow before blocking:**
    1. **Loopback (`lo`):** Allow all outbound on `oifname "lo"` (`127.0.0.0/8`, `::1`). Because NAT mode isolates `lo` from Windows, the agent can freely reach OpenClaw Gateway (`43181`), voice (`43210`), and random `llama.cpp` loopback ports without port-range restrictions.
    2. **Established/related traffic:** `ct state established,related accept` so responses to inbound requests over `tailscale0` (or `lo` from `tailscaled`'s `serve` proxy) succeed.
    3. **DNS resolver endpoint:** Allow outbound `udp dport 53` and `tcp dport 53` to the active WSL DNS stub (`10.255.255.254` when `dnsTunneling=true`, or the `172.x.x.1` gateway when `dnsTunneling=false`, or `100.100.100.100` if using MagicDNS).
    4. **Its own tailnet node:** Allow outbound to the distro's own Tailscale IPv4 (`100.x.y.z/32`), own Tailscale IPv6 (`fd7a:115c:a1e0::.../128`), and optionally `100.100.100.100` (Quad100 local service IP). *(Note: `tailscaled` itself runs as `root`, so filtering `meta skuid <agent_uid>` in `output` does not block `tailscaled` from talking to `controlplane.tailscale.com`, DERP servers, or peer UDP endpoints, nor does it block `tailscaled` from connecting as `root` to `127.0.0.1:43181` and `127.0.0.1:43210` for `tailscale serve`.)*
  * **Block (`drop` / `reject`) for `meta skuid <agent_uid>` in the `output` chain:**
    1. **Other tailnet devices (including the Windows host's Tailscale IP and Mac):** Block destination `100.64.0.0/10` and `fd7a:115c:a1e0::/48` (or `oifname "tailscale0"` for new outbound connections not matching the distro's own Tailscale IPs).
    2. **Windows host (`vEthernet (WSL)`) and RFC1918 / Link-Local LAN:** Block destination `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, multicast `224.0.0.0/4`, and IPv6 local/link-local/multicast `fc00::/7`, `fe80::/10`, `ff00::/8` (plus any global IPv6 `/64` LAN prefix if IPv6 is enabled on `eth0`).
  * **Internet:** Allowed by default after the above drops because outbound internet packets on `eth0` carry public destination IPs (`ip daddr` is the remote internet host, even though the L2 next-hop is the `172.x.x.1` gateway).
    * *Sources:* [Tailscale KB 1325 — Reserved IP addresses (`100.64.0.0/10`, `fd7a:115c:a1e0::/48`)](https://tailscale.com/kb/1325/reserved-ip-addresses), [Tailscale KB 1286 — Quad100 (`100.100.100.100`)](https://tailscale.com/kb/1286/quad100), [Microsoft Learn — WSL Networking](https://learn.microsoft.com/en-us/windows/wsl/networking)

---

## 5. Impact of Switching Modes on `wsl --shutdown`, GPU/CUDA (`/usr/lib/wsl`), and `systemd`

* **Does switching modes need `wsl --shutdown`?**
  * **Yes.** Changes to `%USERPROFILE%\.wslconfig` are global VM settings and only take effect after a full utility VM restart via `wsl --shutdown` (or waiting at least 8 seconds after all WSL processes exit).
    * *Source:* [Microsoft Learn — Advanced settings configuration in WSL ("The 8 second rule")](https://learn.microsoft.com/en-us/windows/wsl/wsl-config)
* **Does it affect GPU access (CUDA via `/usr/lib/wsl`)?**
  * **No.** GPU paravirtualization in WSL2 uses the VMBus device `/dev/dxg` (`dxgkrnl`) and host driver mounts under `/usr/lib/wsl/lib` (`libcuda.so`), which are completely independent of the `networkingMode` (`nat` vs. `mirrored`) virtual switch subsystem. (Any active GPU processes inside the distro are terminated during `wsl --shutdown` and re-attach to `/dev/dxg` on next boot.)
    * *Sources:* [Microsoft Learn — Enable NVIDIA CUDA on WSL](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gpu-accelerated-ml), [microsoft/WSL#12909](https://github.com/microsoft/WSL/issues/12909)
* **Does it affect `systemd` services?**
  * **No** for `systemd` itself (which is controlled by `/etc/wsl.conf` `[boot] systemd=true`), except that `wsl --shutdown` stops the VM and all running units; when the Windows scheduled task restarts the distro, `systemd` boots fresh and starts enabled units. Services that bind specifically to `127.0.0.1` continue to start normally.
    * *Source:* [Microsoft Learn — Manage Linux services with systemd in WSL](https://learn.microsoft.com/en-us/windows/wsl/systemd)

---

## 6. Newer WSL Options (2026) to Keep a Private Loopback in Mirrored Mode (and In-Place Alternatives)

* **Official `.wslconfig` option to disable `127.0.0.1` sharing in `networkingMode=mirrored`: Not found.**
  * As of 2026, Microsoft's `.wslconfig` specification has **no setting** to disable `127.0.0.1` host-guest loopback mirroring while keeping `networkingMode=mirrored` (`localhostForwarding` is ignored in mirrored mode, and `hostAddressLoopback` only expands loopback sharing to non-`127.0.0.1` host IPs).
    * *Sources:* [Microsoft Learn — `.wslconfig`](https://learn.microsoft.com/en-us/windows/wsl/wsl-config), [Microsoft Learn — WSL Networking](https://learn.microsoft.com/en-us/windows/wsl/networking)
* **Documented WSL2 mirrored-mode mechanics / workarounds that solve the problem without leaving mirrored mode:**
  1. **Match `oifname "loopback0"` (or `ip rule` table `127`) instead of blocking `lo` in `nftables`:**
     * Under `networkingMode=mirrored`, WSL2 bridges guest-to-host `127.0.0.1` traffic by installing policy routing rules (`ip rule`) that route host-destined `127.0.0.1` packets through routing **`table 127`** over a synthetic interface named **`loopback0`** (via a `169.254.x.x` next-hop), whereas purely Linux-local loopback sockets use `lo` (or can be forced to stay in `table local` via `ip rule`). Blocking the agent user on `oifname "loopback0"` (while allowing `oifname "lo"`) or overriding `table 127` policy routing prevents reaching Windows `127.0.0.1` services while allowing all Linux-local `127.0.0.1` ports — though this relies on WSL's internal `loopback0` implementation detail rather than a documented `.wslconfig` toggle.
     * *Sources:* [microsoft/WSL#14063](https://github.com/microsoft/WSL/issues/14063), [microsoft/WSL#10855](https://github.com/microsoft/WSL/issues/10855)
  2. **Other `127.0.0.0/8` addresses (`127.0.0.2`, etc.) are not mirrored to Windows:**
     * Per [microsoft/WSL#11766](https://github.com/microsoft/WSL/issues/11766) and [microsoft/WSL#41116](https://github.com/microsoft/WSL/issues/41116), mirrored mode only mirrors `127.0.0.1` to the Windows host, not the rest of `127.0.0.0/8` (though OpenClaw's managed `localService` pins `127.0.0.1`).
  3. **OpenClaw static embedding port (`baseUrl` without managed `localService`):**
     * Per OpenClaw's `llama-cpp` plugin documentation, OpenClaw only picks a random loopback port when `models.providers.llama-cpp.localService` manages the `llama-server` lifecycle. Running `llama-server` as an explicit systemd service on a fixed loopback port inside the already-allowed firewall range (`43181–43199` or `43255–47350`) and setting `models.providers.llama-cpp.baseUrl` (omitting `localService`) avoids random ports in mirrored mode.
     * *Source:* [OpenClaw Docs — llama.cpp Plugin](https://docs.openclaw.ai/plugins/llama-cpp)

---

## 7. Risks and Expected Order of Steps

### Key Risks
1. **Remote lockout during the switch:** The Mac reaches the PC via SSH over Windows Tailscale. Editing `.wslconfig` and running `wsl --shutdown` will terminate any active shell inside `jorah`, though the SSH session to Windows itself stays up as long as Windows Tailscale is unaffected.
2. **MTU blackholing (`eth0` resetting to `1280`):** With Windows Tailscale and distro Tailscale both running, if `eth0` in `jorah` resets to `1280` after startup (`tailscale/tailscale#21659`), HTTPS responses from `tailscale serve` inside `jorah` can stall mid-handshake.
3. **Firewall ordering lockout:** If the new `nftables` rules blocking RFC1918 (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`) and CGNAT (`100.64.0.0/10`) are applied broadly rather than scoped to the service user (`meta skuid <agent_uid>`), or if they block the WSL DNS stub (`10.255.255.254` / `172.x.x.1` port 53), either `tailscaled` or the agent will lose DNS/network connectivity.
4. **Windows `wslrelay.exe` fragility (if relying on Windows Tailscale Serve + NAT `localhostForwarding`):** If keeping Tailscale Serve on Windows in NAT mode instead of inside the distro, `wslrelay.exe` has known bugs after sleep/Modern Standby or abrupt service restarts (`microsoft/WSL#14005`, `microsoft/WSL#10601`).

### Expected Order of Steps (for moving to NAT + In-Distro Tailscale)
1. **Pre-stage inside `jorah` (while still in mirrored mode):**
   * Verify `[boot] systemd=true` and set a distinct hostname (e.g., `[network] hostname=jorah`) in `/etc/wsl.conf`.
   * Install the Linux Tailscale package inside `jorah`, enable `tailscaled.service`, and prepare (but do not yet activate over mirrored mode) the updated `nftables` configuration file that:
     * Allows all `oifname "lo"` for the service user (`meta skuid <agent_uid>`),
     * Allows `ct state established,related`, DNS (`udp/tcp dport 53` to `10.255.255.254` and `172.16.0.0/12`), and the distro's own Tailscale IPs,
     * Blocks `meta skuid <agent_uid>` outbound to `100.64.0.0/10`, `fd7a:115c:a1e0::/48`, `10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, `169.254.0.0/16`, `fc00::/7`, and `fe80::/10`.
2. **Switch WSL networking mode on Windows:**
   * From an SSH session to the Windows host (not inside `jorah`), update `%USERPROFILE%\.wslconfig` to set `networkingMode=nat` (and optionally `localhostForwarding=false` if Windows should not have localhost relay access into `jorah`).
   * Run `wsl --shutdown`, wait >8 seconds, and start `jorah` (`wsl -d jorah` or trigger the boot scheduled task).
3. **Verify NAT isolation and GPU/systemd health:**
   * Inside `jorah`, confirm `ip addr` shows standard `lo` and `eth0` (`172.x.x.x`, no `loopback0`), confirm `systemd` is PID 1, and verify `/dev/dxg` + `/usr/lib/wsl/lib/nvidia-smi` work.
4. **Bring up in-distro Tailscale and `tailscale serve`:**
   * Run `sudo tailscale up --accept-dns=false --accept-routes=false --hostname=jorah` and authenticate the new node.
   * Check `ip link show eth0` to confirm `fixupWSLMTU` raised `eth0` MTU above `1280` (e.g., `1360`).
   * Configure `tailscale serve` inside `jorah` for `http://127.0.0.1:43181` and `http://127.0.0.1:43210` with `--bg` (and remove any duplicate Windows `tailscale serve` mappings for those ports).
5. **Apply updated `nftables` rules and enable OpenClaw semantic memory search:**
   * Load the updated `nftables` ruleset inside `jorah`.
   * Verify from the service user account that:
     * Arbitrary loopback ports (`127.0.0.1:<random>`) succeed (allowing `llama.cpp` embeddings to start),
     * Public internet HTTPS and DNS succeed,
     * Connections to the Windows host (`172.x.x.1`), LAN (`192.168.x.x`), and other tailnet nodes (`100.x.y.z` for Windows/Mac) are rejected,
     * The Mac can reach `43181` and `43210` over HTTPS on `jorah`'s `.ts.net` hostname.
6. **Verify unattended reboot persistence:**
   * Reboot Windows with no interactive sign-in, confirm the S4U scheduled task boots `jorah`, and verify from the Mac that both `Windows` (SSH) and `jorah` (`tailscale serve` HTTPS ports) come online automatically.

---
