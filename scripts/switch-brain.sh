#!/usr/bin/env bash
# Manually switches Jorah's brain between the Claude CLI login and an Anthropic API key.
#
#   switch-brain.sh status [--probe]   Which route is really active. --probe runs one test turn.
#   switch-brain.sh cli [--dry-run]    Claude Code login (subscription limits). Always allowed.
#   switch-brain.sh api [--dry-run]    Saved API key (API credits, then pay-as-you-go). Needs a key.
#
# Exit codes: 0 ok, 1 failed and rolled back, 2 route inconsistent or unsafe, 3 no API key saved.
#
# The key lives only in OpenClaw's auth store. This script never reads or prints it.
# It changes only agentRuntime.id on anthropic/* model entries, auth.order.anthropic and
# the provider's reference to the saved key (models.providers.anthropic.apiKey).
# Set JORAH_SWITCH_PROFILE to run against another OpenClaw profile (used for testing).
set -euo pipefail

PROFILE="${JORAH_SWITCH_PROFILE:-jorah}"
AGENT="main"
API_PROFILE_ID="${JORAH_API_PROFILE_ID:-anthropic:manual}"
CLI_RUNTIME="claude-cli"
API_RUNTIME="openclaw"
STATE_DIR="$HOME/.openclaw-$PROFILE"
BACKUP_DIR="$STATE_DIR/backups/switch-brain"
# OpenClaw doubles the hyphens of a profile name in its log file name.
LOG_GLOB="/tmp/openclaw/openclaw-${PROFILE//-/--}-*.log"

oc() { openclaw --profile "$PROFILE" "$@"; }
say() { printf '%s\n' "$*"; }
err() { printf 'switch-brain: %s\n' "$*" >&2; }

# Prints the value at a config path as JSON, or null when it is unset.
json_or_null() {
  local out
  if out="$("$@" 2>/dev/null)"; then printf '%s\n' "$out"; else echo null; fi
}
config_json() { json_or_null oc config get "$1" --json; }
stored_order_json() { json_or_null oc models auth order get --provider anthropic --agent "$AGENT" --json; }
profiles_json() { json_or_null oc models auth list --provider anthropic --agent "$AGENT" --json; }
gateway_up() { oc gateway call health --json >/dev/null 2>&1; }

wait_for_gateway() {
  local tries=30
  while [ "$tries" -gt 0 ]; do
    gateway_up && return 0
    sleep 2
    tries=$((tries - 1))
  done
  return 1
}

# Prints the id of the saved API-key profile, or nothing. Only ids and types are read.
api_key_profile() {
  PROFILES="$(profiles_json)" WANT="$API_PROFILE_ID" node -e '
    const list = JSON.parse(process.env.PROFILES)?.profiles ?? [];
    const keys = list.filter((p) => p.provider === "anthropic" && p.type === "api_key");
    const hit = keys.find((p) => p.id === process.env.WANT) ?? keys[0];
    if (hit) console.log(hit.id);
  '
}

# Names (never values) of Anthropic credentials that would reach delegated Claude Code
# through the environment. The ACP adapter inherits the gateway environment.
env_credential_names() {
  local names=""
  names="$(ENV_VARS="$(config_json env.vars)" node -e '
    const vars = JSON.parse(process.env.ENV_VARS) ?? {};
    console.log(Object.keys(vars).filter((k) => /^(ANTHROPIC_(API_KEY|AUTH_TOKEN|OAUTH_TOKEN)|CLAUDE_CODE_OAUTH_TOKEN)/.test(k)).map((k) => `env.vars.${k}`).join(" "));
  ')"
  if [ -f "$STATE_DIR/.env" ]; then
    names="$names $(grep -oE '^(export +)?(ANTHROPIC_(API_KEY|AUTH_TOKEN|OAUTH_TOKEN)|CLAUDE_CODE_OAUTH_TOKEN)[A-Z_]*=' "$STATE_DIR/.env" | sed -E 's/^export +//; s/=$//; s/^/.env:/' | tr '\n' ' ')"
  fi
  printf '%s' "$names" | xargs
}

# Builds the minimal patch for a route, plus its inverse for rollback.
build_plan() {
  local runtime="$1" order="$2" drop_key_ref="$3" key_id="$4"
  DROP_KEY_REF="$drop_key_ref" KEY_REF_STATE="$(provider_key_ref)" KEY_ID="$key_id" \
  AGENTS="$(config_json agents)" PROVIDER_RUNTIME="$(config_json models.providers.anthropic.agentRuntime)" \
  CURRENT_ORDER="$(config_json auth.order.anthropic)" RUNTIME="$runtime" ORDER="$order" node -e '
    const agents = JSON.parse(process.env.AGENTS) ?? {};
    const runtime = process.env.RUNTIME;
    const order = JSON.parse(process.env.ORDER);
    const currentOrder = JSON.parse(process.env.CURRENT_ORDER);
    const providerRuntime = JSON.parse(process.env.PROVIDER_RUNTIME);
    const patch = {}, inverse = {}, changes = [];
    const put = (root, path, value) => {
      let node = root;
      path.slice(0, -1).forEach((key) => (node = node[key] ??= {}));
      node[path.at(-1)] = value;
    };
    const setRuntime = (base, models) => {
      for (const [ref, entry] of Object.entries(models ?? {})) {
        if (!ref.startsWith("anthropic/") || entry?.agentRuntime?.id === runtime) continue;
        const path = [...base, ref, "agentRuntime", "id"];
        put(patch, path, runtime);
        put(inverse, path, entry?.agentRuntime?.id ?? null);
        changes.push(`${base.join(".")}["${ref}"].agentRuntime.id: ${entry?.agentRuntime?.id ?? "(unset)"} -> ${runtime}`);
      }
    };
    setRuntime(["agents", "defaults", "models"], agents.defaults?.models);
    for (const [id, entry] of Object.entries(agents.entries ?? {})) setRuntime(["agents", "entries", id, "models"], entry?.models);
    if (providerRuntime && providerRuntime.id !== runtime) {
      const path = ["models", "providers", "anthropic", "agentRuntime", "id"];
      put(patch, path, runtime);
      put(inverse, path, providerRuntime.id);
      changes.push(`models.providers.anthropic.agentRuntime.id: ${providerRuntime.id} -> ${runtime}`);
    }
    if (JSON.stringify(currentOrder) !== JSON.stringify(order)) {
      put(patch, ["auth", "order", "anthropic"], order);
      put(inverse, ["auth", "order", "anthropic"], currentOrder);
      changes.push(`auth.order.anthropic: ${JSON.stringify(currentOrder)} -> ${JSON.stringify(order)}`);
    }
    if (process.env.DROP_KEY_REF === "1" && process.env.KEY_REF_STATE === "set") {
      // Rollback restores the reference by profile id; config reads only return it redacted.
      put(patch, ["models", "providers", "anthropic", "apiKey"], null);
      if (process.env.KEY_ID) put(inverse, ["models", "providers", "anthropic", "apiKey"], process.env.KEY_ID);
      changes.push("models.providers.anthropic.apiKey: reference -> removed");
    }
    console.log(JSON.stringify({ patch, inverse, changes }));
  '
}

plan_field() { PLAN="$1" FIELD="$2" node -e 'const v = JSON.parse(process.env.PLAN)[process.env.FIELD]; console.log(Array.isArray(v) ? v.join("\n") : JSON.stringify(v));'; }

# Prints "set" or "unset". OpenClaw redacts the value, and it is never printed here.
provider_key_ref() {
  KEY_REF="$(config_json models.providers.anthropic.apiKey)" node -e 'console.log(JSON.parse(process.env.KEY_REF) == null ? "unset" : "set")'
}

# Prints the runtime id the running gateway resolved for the default model, or "unknown".
gateway_runtime() {
  local primary="$1" models
  models="$(oc gateway call models.list --json 2>/dev/null)" || { echo unknown; return; }
  MODELS="$models" PRIMARY="$primary" node -e '
    const list = JSON.parse(process.env.MODELS).models ?? [];
    const id = process.env.PRIMARY.replace(/^anthropic\//, "");
    console.log(list.find((m) => m.provider === "anthropic" && m.id === id)?.agentRuntime?.id ?? "unknown");
  '
}

primary_model() {
  AGENTS="$(config_json agents)" AGENT="$AGENT" node -e '
    const a = JSON.parse(process.env.AGENTS) ?? {};
    const pick = (m) => (typeof m === "string" ? m : m?.primary);
    console.log(pick(a.entries?.[process.env.AGENT]?.model) ?? pick(a.defaults?.model) ?? "");
  '
}

cmd_switch() {
  local route="$1" dry_run="$2" runtime order key_id="" extra drop_key_ref=0
  if [ "$route" = "api" ]; then
    runtime="$API_RUNTIME"
    key_id="$(api_key_profile)"
    if [ -z "$key_id" ]; then
      err "no Anthropic API key is saved, so nothing was changed. The brain stays on its current route."
      err "Save one in your own terminal (it prompts; never paste it into a chat):"
      err "  openclaw --profile $PROFILE models auth paste-api-key --provider anthropic"
      return 3
    fi
    extra="$(env_credential_names)"
    if [ -n "$extra" ]; then
      err "refusing: Anthropic credentials are set in the environment ($extra)."
      err "Delegated Claude Code would inherit them and bill the API. Remove them first."
      return 2
    fi
    order="[\"$key_id\"]"
  else
    runtime="$CLI_RUNTIME"
    # Tested: the key is unreachable only with an empty order AND no provider reference.
    # Either one alone still lets direct API calls use it. Native Claude login is unaffected.
    order="[]"
    drop_key_ref=1
    key_id="$(api_key_profile)"
  fi

  local plan changes stored
  plan="$(build_plan "$runtime" "$order" "$drop_key_ref" "$key_id")"
  changes="$(plan_field "$plan" changes)"
  stored="$(STORED="$(stored_order_json)" node -e 'console.log(JSON.stringify(JSON.parse(process.env.STORED)?.order ?? null))')"

  if [ "$dry_run" = "1" ]; then
    say "Dry run for route '$route'. Nothing was changed."
    if [ -n "$changes" ]; then say "Would back up the config, then set:"; say "$changes"; else say "Config is already on this route."; fi
    [ "$stored" = "null" ] || say "Would clear the stored auth order: $stored"
    return 0
  fi

  if [ -n "$changes" ] || [ "$stored" != "null" ]; then
    mkdir -p "$BACKUP_DIR"
    chmod 700 "$BACKUP_DIR"
    say "Backing up config to $BACKUP_DIR"
    oc backup create --only-config --verify --output "$BACKUP_DIR" >/dev/null
    chmod 600 "$BACKUP_DIR"/* 2>/dev/null || true
  fi

  # A stored per-agent order outranks config, so it must not survive a switch.
  if [ "$stored" != "null" ]; then
    say "Clearing stored auth order (was $stored)"
    oc models auth order clear --provider anthropic --agent "$AGENT" >/dev/null
  fi

  if [ -z "$changes" ]; then
    say "Config is already on route '$route'."
  else
    say "$changes"
    plan_field "$plan" patch | oc config patch --stdin >/dev/null
  fi

  if ! verify_switch "$runtime"; then
    err "verification failed; restoring the previous route."
    if [ -n "$changes" ]; then
      plan_field "$plan" inverse | oc config patch --stdin >/dev/null || err "rollback failed; the backup is in $BACKUP_DIR"
    fi
    return 1
  fi

  say "Route is now '$route'. Confirm with a test turn: $0 status --probe"
  if [ "$route" = "api" ]; then
    say "Billing: requests now draw on the Console org of key '$key_id'. If it runs out, Jorah's requests fail. Nothing moves back on its own."
  fi
}

verify_switch() {
  local runtime="$1" primary actual
  oc config validate >/dev/null || return 1
  [ "${JORAH_SWITCH_TEST_FAIL_VERIFY:-}" != "1" ] || { err "test hook forced a verification failure"; return 1; }
  if ! gateway_up; then
    # A config patch may restart the gateway; give it time before calling it stopped.
    wait_for_gateway || { say "Gateway is not running; the route applies when it next starts."; return 0; }
  fi
  primary="$(primary_model)"
  actual="$(gateway_runtime "$primary")"
  # The file watcher applies the patch shortly after the write.
  local tries=15
  while [ "$tries" -gt 0 ]; do
    [ "$actual" = "$runtime" ] && return 0
    sleep 1
    actual="$(gateway_runtime "$primary")"
    tries=$((tries - 1))
  done
  err "gateway reports runtime '$actual' for $primary, expected '$runtime'."
  return 1
}

last_cli_turn() {
  local log
  log="$(ls -t $LOG_GLOB 2>/dev/null | head -1)"
  [ -n "$log" ] || { echo "no log"; return; }
  LOG="$log" node -e '
    const lines = require("fs").readFileSync(process.env.LOG, "utf8").split("\n");
    for (let i = lines.length - 1; i >= 0; i--) {
      if (!lines[i].includes("cli exec: provider=claude-cli")) continue;
      try {
        const row = JSON.parse(lines[i]);
        const trigger = /trigger=(\S+)/.exec(row["1"])?.[1] ?? "?";
        const model = /model=(\S+)/.exec(row["1"])?.[1] ?? "?";
        console.log(`${row.time} ${model} trigger=${trigger}`);
        process.exit(0);
      } catch {}
    }
    console.log("none in the latest log");
  '
}

run_probe() {
  local key out rc=0
  key="switchprobe-$(date +%s)"
  say "Probe: running one test turn (session $key). This uses the active route's quota or credits."
  out="$(oc agent --agent "$AGENT" --session-key "$key" --timeout 180 --json -m 'Route probe. Reply with exactly: PROBE-OK' 2>&1)" || rc=$?
  OUT="$out" RC="$rc" node -e '
    let d = {};
    const raw = process.env.OUT;
    try { d = JSON.parse(raw.slice(raw.indexOf("{"), raw.lastIndexOf("}") + 1)); } catch {}
    const m = d.result?.meta ?? {};
    const scrub = (s) => String(s ?? "").replace(/sk-ant-[A-Za-z0-9_-]+/g, "<redacted>").slice(0, 300);
    const text = (d.result?.payloads ?? []).map((p) => p.text).join(" ");
    console.log(`  status:      ${d.status ?? "failed"} (cli exit ${process.env.RC})`);
    console.log(`  reply:       ${scrub(text) || scrub(m.error?.message ?? d.error?.message) || "(none)"}`);
    console.log(`  runner:      ${m.executionTrace?.runner ?? "?"}`);
    console.log(`  runtime:     ${m.systemPromptReport?.provider ?? "?"}`);
    console.log(`  harness:     ${m.agentMeta?.agentHarnessId ?? "(none)"}`);
    console.log(`  credential:  ${m.agentMeta?.credentialSource?.kind ?? "(native login or none)"}`);
    console.log(`  fallback:    ${m.executionTrace?.fallbackUsed ?? "?"}`);
  '
  oc sessions delete "agent:$AGENT:$key" --yes >/dev/null 2>&1 || true
  oc memory forget --agent "$AGENT" --session "agent:$AGENT:$key" >/dev/null 2>&1 || true
  return "$rc"
}

cmd_status() {
  local probe="$1" primary key_id file_view gw="unknown" problems=0 credentials stored order key_ref
  primary="$(primary_model)"
  key_id="$(api_key_profile)"
  credentials="$(env_credential_names)"
  stored="$(STORED="$(stored_order_json)" node -e 'console.log(JSON.stringify(JSON.parse(process.env.STORED)?.order ?? null))')"
  order="$(config_json auth.order.anthropic | tr -d ' \n')"
  key_ref="$(provider_key_ref)"
  file_view="$(AGENTS="$(config_json agents)" PRIMARY="$primary" AGENT="$AGENT" CLI="$CLI_RUNTIME" API="$API_RUNTIME" node -e '
    const a = JSON.parse(process.env.AGENTS) ?? {};
    const entries = Object.entries(a.defaults?.models ?? {}).filter(([k]) => k.startsWith("anthropic/"));
    for (const e of Object.values(a.entries ?? {})) entries.push(...Object.entries(e?.models ?? {}).filter(([k]) => k.startsWith("anthropic/")));
    const count = (id) => entries.filter(([, v]) => v?.agentRuntime?.id === id).length;
    const cli = count(process.env.CLI), api = count(process.env.API), total = entries.length;
    const route = total && cli === total ? "cli" : total && api === total ? "api" : "mixed";
    const main = a.entries?.[process.env.AGENT]?.model;
    const fallbacks = (typeof main === "object" && main?.fallbacks) || a.defaults?.model?.fallbacks || [];
    const foreign = fallbacks.filter((f) => !String(f).startsWith("anthropic/"));
    console.log(JSON.stringify({ route, cli, api, total, fallbacks: fallbacks.length, foreign }));
  ')"
  local file_route; file_route="$(VIEW="$file_view" node -e 'console.log(JSON.parse(process.env.VIEW).route)')"

  say "Jorah brain route (profile $PROFILE)"
  if gateway_up; then
    gw="$(gateway_runtime "$primary")"
    say "  gateway reports:  $primary -> $gw"
  else
    say "  gateway reports:  not running"
  fi
  VIEW="$file_view" node -e '
    const v = JSON.parse(process.env.VIEW);
    console.log(`  config file:      ${v.route} (${v.cli} claude-cli, ${v.api} openclaw, of ${v.total} anthropic entries)`);
    console.log(`  fallbacks:        ${v.fallbacks}, non-Anthropic: ${v.foreign.join(", ") || "none"}`);
  '
  say "  auth.order:       ${order}"
  say "  stored order:     ${stored}"
  say "  provider key ref: ${key_ref}"
  say "  API key saved:    ${key_id:-no}"
  say "  env credentials:  ${credentials:-none}"
  say "  last CLI turn:    $(last_cli_turn)"

  local active="$file_route"
  case "$gw" in
    "$CLI_RUNTIME") active="cli" ;;
    "$API_RUNTIME") active="api" ;;
  esac
  if [ "$gw" != "unknown" ] && [ "$active" != "$file_route" ]; then
    say "  PROBLEM: the gateway ($active) and the config file ($file_route) disagree."
    problems=1
  fi
  if [ "$file_route" = "mixed" ]; then
    say "  PROBLEM: runtime entries are mixed. Run '$0 cli' to restore the CLI route."
    problems=1
  fi
  if [ -n "$credentials" ]; then
    say "  PROBLEM: credentials in the environment reach delegated Claude Code and would bill the API."
    problems=1
  fi
  if [ "$active" = "cli" ] && [ -n "$key_id" ] && { [ "$order" != "[]" ] || [ "$key_ref" = "set" ]; }; then
    say "  PROBLEM: a key is saved and not blocked, so direct API calls could use it. Run '$0 cli' to block it."
    problems=1
  fi
  if [ "$stored" != "null" ] && [ "$active" = "cli" ] && [ "$stored" != "[]" ]; then
    say "  PROBLEM: a stored auth order overrides config. Run '$0 cli' to clear it."
    problems=1
  fi
  case "$active" in
    cli) say "ACTIVE ROUTE: cli (Claude Code login, subscription limits)" ;;
    api) say "ACTIVE ROUTE: api (saved API key, Console credits or pay-as-you-go)" ;;
    *) say "ACTIVE ROUTE: unclear ($active)" ;;
  esac
  if [ "$probe" = "1" ]; then
    run_probe || problems=1
  else
    say "This reads config and the gateway's route. Add --probe to prove it with a real test turn."
  fi
  [ "$problems" = "0" ] || return 2
}

usage() { sed -n 2,6p "$0" | sed 's/^# \{0,1\}//'; }

command -v openclaw >/dev/null || { err "openclaw is not installed"; exit 1; }
command -v node >/dev/null || { err "node is not installed"; exit 1; }

action="${1:-}"
[ $# -gt 0 ] && shift
dry_run=0
probe=0
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=1 ;;
    --probe) probe=1 ;;
    *) err "unknown option: $arg"; usage >&2; exit 64 ;;
  esac
done

case "$action" in
  status) cmd_status "$probe" ;;
  cli | api) cmd_switch "$action" "$dry_run" ;;
  *) usage >&2; exit 64 ;;
esac
