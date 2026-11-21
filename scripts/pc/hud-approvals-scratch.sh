#!/usr/bin/env bash
# ADR 0007's scratch test: what a non-admin device with operator.approvals can see and answer.
# Starts a throwaway Gateway (profile jorah-hud-test, 127.0.0.1:43187, channels and cron off),
# pairs a fresh test device the way the Mac HUD does, upgrades it to operator.approvals, makes
# test cards and answers them, then stops the Gateway. Never touches the live or jorah-dev profile.
# The Gateway token is generated into a 600 file on the PC and never printed.
# From the Mac:
#   ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 \
#     "wsl -d jorah -u jorah -- bash -s" < scripts/pc/hud-approvals-scratch.sh
set -euo pipefail

[ "$(id -un)" = jorah ] || { echo "Run this as jorah."; exit 3; }

PROFILE=jorah-hud-test
PORT=43187
DIR=/home/jorah/.openclaw-$PROFILE
WORK=$DIR/hud-probe
LOG=$WORK/gateway.out
URL=ws://127.0.0.1:$PORT
OC=(/usr/local/bin/openclaw --profile "$PROFILE")

mkdir -p "$WORK"
chmod 700 "$DIR" "$WORK"
umask 077
[ -s "$WORK/token" ] || head -c 32 /dev/urandom | base64 | tr -d '/+=\n' > "$WORK/token"
OPENCLAW_GATEWAY_TOKEN=$(cat "$WORK/token")
export OPENCLAW_GATEWAY_TOKEN GW_URL=$URL STATE=$WORK/device.json
rm -f "$STATE"

# The scratch profile's own config points the CLI at this port, so calls need no --url and read
# the token from OPENCLAW_GATEWAY_TOKEN instead of the command line.
"${OC[@]}" config set gateway.mode local >/dev/null
"${OC[@]}" config set gateway.port "$PORT" >/dev/null
# The probe connects over loopback, which OpenClaw approves silently by default. The HUD comes in
# through Tailscale Serve and never gets that, so turn it off here to test the real approval flow.
"${OC[@]}" config set gateway.nodes.pairing.autoApproveLocal false >/dev/null

pid() { ss -ltnp 2>/dev/null | grep ":$PORT " | grep -oE 'pid=[0-9]+' | head -1 | cut -d= -f2 || true; }
stop() { local p; p=$(pid); [ -n "$p" ] && kill "$p" && sleep 2; echo "scratch Gateway stopped"; }
trap stop EXIT

if [ -z "$(pid)" ]; then
  OPENCLAW_SKIP_CHANNELS=1 OPENCLAW_SKIP_CRON=1 setsid "${OC[@]}" gateway run --allow-unconfigured \
    --auth token --port "$PORT" --bind loopback >"$LOG" 2>&1 </dev/null &
fi
for _ in $(seq 1 60); do
  if "${OC[@]}" gateway call health --json >/dev/null 2>&1; then break; fi
  sleep 3
done
"${OC[@]}" gateway call health --json >/dev/null 2>&1 || { echo "scratch Gateway not ready; tail of log:"; tail -20 "$LOG"; exit 1; }
echo "scratch Gateway up on $URL"

cat > "$WORK/probe.mjs" <<'JS'
// A device that signs in like the Mac HUD (protocol 4, device auth payload v3).
import crypto from "node:crypto";
import fs from "node:fs";
const [cmd, ...args] = process.argv.slice(2);
const STATE = process.env.STATE;
const state = fs.existsSync(STATE) ? JSON.parse(fs.readFileSync(STATE, "utf8")) : {};
if (!state.pem) {
  const { privateKey } = crypto.generateKeyPairSync("ed25519");
  state.pem = privateKey.export({ type: "pkcs8", format: "pem" });
}
const key = crypto.createPrivateKey(state.pem);
const raw = Buffer.from(crypto.createPublicKey(key).export({ format: "jwk" }).x, "base64url");
const deviceId = crypto.createHash("sha256").update(raw).digest("hex");
const save = () => fs.writeFileSync(STATE, JSON.stringify(state), { mode: 0o600 });

function connect(scopes, useShared) {
  return new Promise((resolve) => {
    const ws = new WebSocket(process.env.GW_URL);
    const pending = new Map();
    const events = [];
    let n = 0;
    const api = {
      events,
      deviceId,
      call: (method, params = {}) => new Promise((res) => {
        const id = `r${++n}`;
        pending.set(id, res);
        ws.send(JSON.stringify({ type: "req", id, method, params }));
        setTimeout(() => { if (pending.delete(id)) res({ ok: false, error: { code: "TIMEOUT" } }); }, 15000);
      }),
      close: () => ws.close(),
    };
    ws.onmessage = (m) => {
      const f = JSON.parse(m.data);
      if (f.type === "event" && f.event === "connect.challenge") {
        const { nonce, ts } = f.payload;
        const token = useShared ? process.env.OPENCLAW_GATEWAY_TOKEN : state.deviceToken;
        const payload = ["v3", deviceId, "gateway-client", "ui", "operator", scopes.join(","), String(Math.trunc(ts)),
          token ?? "", nonce, "macos", "mac"].join("|");
        const signature = crypto.sign(null, Buffer.from(payload), key).toString("base64url");
        ws.send(JSON.stringify({ type: "req", id: "connect", method: "connect", params: {
          minProtocol: 4, maxProtocol: 4,
          client: { id: "gateway-client", displayName: "HUD scratch probe", version: "0.1.0", platform: "macos", deviceFamily: "Mac", mode: "ui" },
          role: "operator", scopes, caps: ["tool-events", "plugin-approvals"],
          auth: useShared ? { token } : { deviceToken: token },
          device: { id: deviceId, publicKey: raw.toString("base64url"), signature, signedAt: Math.trunc(ts), nonce },
        } }));
        return;
      }
      if (f.type === "event") { events.push({ event: f.event, payload: f.payload }); return; }
      if (f.type === "res" && f.id === "connect") {
        if (f.ok && f.payload?.auth?.deviceToken) { state.deviceToken = f.payload.auth.deviceToken; save(); }
        resolve({ ok: f.ok, scopes: f.payload?.auth?.scopes, error: f.error, api });
        return;
      }
      if (f.type === "res" && pending.has(f.id)) { pending.get(f.id)(f); pending.delete(f.id); }
    };
    ws.onerror = () => resolve({ ok: false, error: { code: "SOCKET" }, api });
  });
}
const short = (r) => r.ok ? { ok: true, payload: r.payload } : { ok: false, code: r.error?.details?.code ?? r.error?.code, message: r.error?.message, requestId: r.error?.details?.requestId };
const out = (label, v) => console.log(`${label}: ${JSON.stringify(v)}`);
const READ_WRITE = ["operator.read", "operator.write"];
const WITH_CARDS = [...READ_WRITE, "operator.approvals"];

if (cmd === "pair") {
  const c = await connect(READ_WRITE, true);
  out("first pairing (shared token, read+write)", { ok: c.ok, code: c.error?.details?.code ?? c.error?.code, requestId: c.error?.details?.requestId });
  save(); c.api.close();
} else if (cmd === "paired") {
  const c = await connect(READ_WRITE, true);
  out("after approval (shared token)", { ok: c.ok, scopes: c.scopes, gotDeviceToken: Boolean(state.deviceToken) });
  c.api.close();
} else if (cmd === "list-without-scope") {
  const c = await connect(READ_WRITE, false);
  out("connect with device token, read+write", { ok: c.ok, scopes: c.scopes });
  out("T1 plugin.approval.list without operator.approvals", short(await c.api.call("plugin.approval.list")));
  c.api.close();
} else if (cmd === "upgrade") {
  const c = await connect(WITH_CARDS, false);
  out("T2a device token reconnect asking for +operator.approvals", { ok: c.ok, code: c.error?.details?.code ?? c.error?.code });
  if (c.ok) c.api.close();
  const d = await connect(READ_WRITE, false);
  const req = await d.api.call("device.scopes.requestUpgrade", { scopes: WITH_CARDS });
  out("T2b device.scopes.requestUpgrade over the live connection", short(req));
  out("T2b nothing widened while pending: list", short(await d.api.call("plugin.approval.list")));
  const id = req.payload?.requestId;
  const waiting = id ? d.api.call("device.scopes.waitUpgrade", { requestId: id }) : Promise.resolve(null);
  if (id) {
    const { execFileSync } = await import("node:child_process");
    const oc = ["--profile", "jorah-hud-test"];
    const pend = JSON.parse(execFileSync("openclaw", [...oc, "devices", "list", "--json"], { encoding: "utf8" })).pending ?? [];
    const mine = pend.find((r) => r.requestId === id);
    out("T2b pending request as Adam would see it", mine ? { displayName: mine.displayName, role: mine.role, scopes: mine.scopes, isRepair: mine.isRepair } : "not listed");
    execFileSync("openclaw", [...oc, "devices", "approve", id, "--json"], { encoding: "utf8" });
    console.log("approved on the scratch Gateway: upgrade to operator.approvals");
  }
  const w = await waiting;
  const p = w?.payload ?? {};
  if (p.token) { state.deviceToken = p.token; save(); }
  if (p.deviceToken) { state.deviceToken = p.deviceToken; save(); }
  out("T2b waitUpgrade result (token redacted)", w ? { ok: w.ok, keys: Object.keys(p), status: p.status, scopes: p.scopes, error: w.error?.message } : null);
  d.api.close();
  const e = await connect(WITH_CARDS, false);
  out("T2b reconnect with +approvals after approval", { ok: e.ok, scopes: e.scopes, code: e.error?.details?.code ?? e.error?.code });
  e.api.close();
} else if (cmd === "cards") {
  // Only the agent runtime can name a reviewer device (bindApprovalReviewerDeviceIds), and a
  // chat turn names the device that sent it. Without a model here, the nearest stand-in is two
  // connections of the same device: one asks (as the HUD's turn would), the other answers (the
  // HUD). The asking connection is never a route for its own card. A second surface answering
  // first (Telegram, live) is stood in for by the asking connection.
  const { execFileSync } = await import("node:child_process");
  const admin = (method, params) => {
    try {
      return JSON.parse(execFileSync("openclaw", ["--profile", "jorah-hud-test", "gateway", "call", method, "--params", JSON.stringify(params), "--json"], { encoding: "utf8" }));
    } catch (e) {
      try { return JSON.parse(e.stdout); } catch { return { error: String(e.message).slice(0, 160) }; }
    }
  };
  const hud = await connect(WITH_CARDS, false);
  out("T3 answering connection linked (+approvals, plugin-approvals cap)", { ok: hud.ok, scopes: hud.scopes });
  const asker = await connect(WITH_CARDS, false);
  const ask = async (title) => short(await asker.api.call("plugin.approval.request", {
    title, description: "Scratch card for ADR 0007 [link](https://example.invalid) \u202Eevil", severity: "warning",
    allowedDecisions: ["allow-once", "deny"], timeoutMs: 120000, twoPhase: true, toolName: "toolbox_install" }));
  const B = await ask("Card B");
  const E = await ask("Card E");
  out("cards asked (decision null at once would mean no route)", { B: [B.payload?.id, B.payload?.decision], E: [E.payload?.id, E.payload?.decision] });
  const listed = await hud.api.call("plugin.approval.list");
  const rows = listed.payload ?? [];
  out("T5 list rows as the HUD gets them", { ok: listed.ok, count: rows.length, rowKeys: rows[0] ? Object.keys(rows[0]).sort() : [], requestKeys: rows[0] ? Object.keys(rows[0].request ?? {}).sort() : [] });
  const b = rows.find((r) => r.id === B.payload?.id);
  out("T5 card B as listed (description as the Gateway sanitised it)", b ? { title: b.request.title, description: b.request.description, allowedDecisions: b.request.allowedDecisions, expiresInS: Math.round((b.expiresAtMs - Date.now()) / 1000) } : "not listed");
  out("T3 allow-always on card B", short(await hud.api.call("plugin.approval.resolve", { id: B.payload?.id, decision: "allow-always" })));
  out("T3 allow-once on card B", short(await hud.api.call("plugin.approval.resolve", { id: B.payload?.id, decision: "allow-once" })));
  out("T4 a second answer (deny) on card B", short(await hud.api.call("plugin.approval.resolve", { id: B.payload?.id, decision: "deny" })));
  out("T4 the CLI over the shared token (least-privilege scopes) tries card E", admin("plugin.approval.resolve", { id: E.payload?.id, decision: "deny" }).error?.message ?? "resolved");
  out("T4 another connection (the asker) denies card E first", short(await asker.api.call("plugin.approval.resolve", { id: E.payload?.id, decision: "deny" })));
  out("T4 then the HUD answers card E", short(await hud.api.call("plugin.approval.resolve", { id: E.payload?.id, decision: "allow-once" })));
  const after = (await hud.api.call("plugin.approval.list")).payload ?? [];
  out("T4 B and E gone from the HUD's list", { B: !after.some((r) => r.id === B.payload?.id), E: !after.some((r) => r.id === E.payload?.id) });
  await new Promise((r) => setTimeout(r, 1500));
  out("T4 approval events the HUD connection received", hud.api.events.filter((e) => e.event.startsWith("plugin.approval")).map((e) => ({ event: e.event, id: e.payload?.id, decision: e.payload?.decision, keys: Object.keys(e.payload ?? {}).sort() })));
  hud.api.close(); asker.api.close();
}
JS

probe() { node "$WORK/probe.mjs" "$@"; }
approve_latest() {
  local id
  id=$("${OC[@]}" devices list --json 2>/dev/null | python3 -c '
import json,sys
d=json.load(sys.stdin)
p=[r for r in d.get("pending",[]) if (r.get("displayName") or "")=="HUD scratch probe"]
print(p[-1]["requestId"] if p else "")')
  [ -n "$id" ] || { echo "no pending request for the probe"; return 1; }
  "${OC[@]}" devices list --json 2>/dev/null | python3 -c '
import json,sys
for r in json.load(sys.stdin).get("pending",[]):
  if (r.get("displayName") or "")=="HUD scratch probe": print("pending request:", {k:r.get(k) for k in ("role","scopes","requestedScopes","isRepair")})'
  "${OC[@]}" devices approve "$id" --json >/dev/null && echo "approved on the scratch Gateway: $1"
}
probe pair
approve_latest "first pairing"
probe paired
probe list-without-scope
probe upgrade
probe cards
