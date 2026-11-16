"""Run Claude Code headless for one project run, and read what its stream says about usage.

- The pinned binary, `CLAUDE_CONFIG_DIR` set to Jorah's Max login, `-p` with stream-json, the
  model and effort, `--max-turns`, and a wall-clock kill (SIGTERM to the process group, then
  SIGKILL after a grace period).
- `--setting-sources ""` loads no user, project or local settings, so only the runner's
  project-settings file applies: the work repo's own `.claude/settings.json` (hooks, permissions)
  and the coding-jobs settings are both ignored. `--strict-mcp-config` with no MCP config loads no
  MCP server, the repo's `.mcp.json` included.
- The brief goes in on stdin, so it never shows in `ps`.
- Nothing from the stream is kept except counters, the exit facts and rate-limit information.

Usage limits (spike S2, read from Claude Code 2.1.300): stream-json carries
`{"type":"rate_limit_event","rate_limit_info":{"status":"allowed|allowed_warning|rejected",
"resetsAt":<epoch s>,"rateLimitType":"five_hour|seven_day|...","utilization":0..1,...}}` whenever the
subscription's limit state changes (never for API-key sessions). `status: rejected` is the usage
limit. Assistant messages may carry `error: "rate_limit"`, and the final `result` message has
`terminal_reason`, `num_turns`, `subtype` and `is_error`. Older builds said
"Claude AI usage limit reached|<epoch>" in the result text, which is matched too.
"""

import json
import os
import re
import signal
import subprocess
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

LIMIT_TEXT = re.compile(r"usage limit reached|hit your (?:usage |session |weekly |5-hour |five-hour )?limit|out of (?:extra )?usage", re.I)
LEGACY_RESET = re.compile(r"usage limit reached\|(\d{9,11})", re.I)


def _iso(epoch):
    try:
        return datetime.fromtimestamp(int(epoch), tz=timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


class StreamReader:
    """Folds stream-json lines into a small summary. Holds no message text."""

    def __init__(self):
        self.lines = 0
        self.bad_lines = 0
        self.assistant_messages = 0
        self.tool_uses = 0
        self.result = None
        self.limited = False
        self.limit_reset = None
        self.limit_type = None
        self.last_rate_info = None
        self.windows = {}
        self.api_errors = set()
        self.session_id = None

    def feed(self, raw):
        self.lines += 1
        try:
            msg = json.loads(raw)
        except ValueError:
            self.bad_lines += 1
            return
        if not isinstance(msg, dict):
            return
        kind = msg.get("type")
        if isinstance(msg.get("session_id"), str) and not self.session_id:
            self.session_id = msg["session_id"][:64]
        if kind == "rate_limit_event":
            self._rate(msg.get("rate_limit_info"))
        elif kind == "assistant":
            self.assistant_messages += 1
            content = (msg.get("message") or {}).get("content")
            if isinstance(content, list):
                self.tool_uses += sum(1 for c in content if isinstance(c, dict) and c.get("type") == "tool_use")
                for c in content:
                    if isinstance(c, dict) and c.get("type") == "text" and isinstance(c.get("text"), str):
                        self._text(c["text"], source="assistant", error=msg.get("error"))
            error = msg.get("error")
            if isinstance(error, str):
                self.api_errors.add(error[:40])
        elif kind == "result":
            self.result = {
                "subtype": str(msg.get("subtype"))[:40] if msg.get("subtype") is not None else None,
                "isError": bool(msg.get("is_error")),
                "numTurns": msg.get("num_turns") if isinstance(msg.get("num_turns"), int) else None,
                "terminalReason": str(msg.get("terminal_reason"))[:40] if msg.get("terminal_reason") is not None else None,
                "durationMs": msg.get("duration_ms") if isinstance(msg.get("duration_ms"), int) else None,
            }
            if isinstance(msg.get("result"), str):
                self._text(msg["result"], source="result", is_error=bool(msg.get("is_error")))

    def _text(self, text, *, source, error=None, is_error=False):
        # Only a short text can be the CLI's own limit notice; a long answer that mentions limits isn't.
        if len(text) > 400:
            return
        legacy = LEGACY_RESET.search(text)
        if legacy:
            self.limited = True
            self.limit_reset = self.limit_reset or _iso(legacy.group(1))
            return
        if not LIMIT_TEXT.search(text):
            return
        if (source == "assistant" and error == "rate_limit") or (source == "result" and is_error):
            self.limited = True

    def _rate(self, info):
        if not isinstance(info, dict):
            return
        status = info.get("status")
        reset = _iso(info.get("resetsAt")) if info.get("resetsAt") is not None else None
        kind = info.get("rateLimitType") if isinstance(info.get("rateLimitType"), str) else None
        util = info.get("utilization") if isinstance(info.get("utilization"), (int, float)) and not isinstance(info.get("utilization"), bool) else None
        self.last_rate_info = {"status": status if isinstance(status, str) else None, "rateLimitType": kind,
                               "utilization": util, "resetsAt": reset}
        windows = info.get("unifiedWindows")
        if isinstance(windows, dict):
            for key, name in (("five_hour", "fiveHour"), ("seven_day", "sevenDay")):
                w = windows.get(key)
                if isinstance(w, dict) and isinstance(w.get("utilization"), (int, float)):
                    self.windows[name] = {"utilization": float(w["utilization"]), "resetsAt": _iso(w.get("resetsAt"))}
        if kind in ("seven_day", "seven_day_opus") and util is not None and "sevenDay" not in self.windows:
            self.windows["sevenDay"] = {"utilization": float(util), "resetsAt": reset}
        if kind == "five_hour" and util is not None and "fiveHour" not in self.windows:
            self.windows["fiveHour"] = {"utilization": float(util), "resetsAt": reset}
        if status == "rejected":
            self.limited = True
            self.limit_reset = reset or self.limit_reset
            self.limit_type = kind

    def usage(self):
        return {"limited": self.limited, "resetsAt": self.limit_reset, "rateLimitType": self.limit_type,
                "last": self.last_rate_info, "windows": self.windows or None}


def build_command(settings, project, *, session_id):
    settings_file = settings.project_settings_web_file if project.web else settings.project_settings_file
    cmd = [
        str(settings.claude_bin), "-p",
        "--output-format", "stream-json", "--verbose",
        "--model", settings.model, "--effort", settings.effort,
        "--max-turns", str(project.limits["maxTurns"]),
        "--setting-sources", "",
        "--settings", str(settings_file),
        "--strict-mcp-config",
        "--session-id", session_id,
    ]
    if not project.web:
        cmd += ["--disallowedTools", "WebFetch", "WebSearch"]
    return cmd


def bench_environment(settings, project):
    """Variables from the bench's env.sh (root-owned, not writable by others), or {}."""
    if not project.bench:
        return {}
    script = Path(settings.bench_env.get(project.bench, ""))
    if not script.is_file():
        raise RuntimeError(f"the {project.bench} bench isn't installed ({script} missing)")
    info = script.stat()
    if settings.require_root_owned_bench and (info.st_uid != 0 or info.st_mode & 0o022):
        raise RuntimeError(f"{script} must be root-owned and not writable by others")
    out = subprocess.run(["/bin/bash", "--noprofile", "--norc", "-c", 'set -e; . "$1" >/dev/null; env -0', "bench", str(script)],
                         capture_output=True, timeout=60, check=True, env={"PATH": "/usr/bin:/bin", "HOME": str(Path(settings.sandbox_dir).parent)})
    env = {}
    for item in out.stdout.decode("utf-8", "replace").split("\0"):
        key, sep, value = item.partition("=")
        if sep and re.match(r"^[A-Za-z_][A-Za-z0-9_]*$", key) and key not in ("HOME", "USER", "LOGNAME", "PWD", "SHLVL", "_", "OLDPWD"):
            env[key] = value
    return env


def build_env(settings, project):
    home = str(Path(settings.sandbox_dir).parent)
    env = {
        "HOME": home,
        "USER": "jorah",
        "LOGNAME": "jorah",
        "PATH": "/usr/local/bin:/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "CLAUDE_CONFIG_DIR": str(settings.claude_config_dir),
        "CLAUDE_CODE_TMPDIR": str(Path(settings.sandbox_dir) / ".tmp"),
        "DISABLE_AUTOUPDATER": "1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
    }
    env.update(bench_environment(settings, project))
    env["CLAUDE_CONFIG_DIR"] = str(settings.claude_config_dir)
    env["HOME"] = home
    return env


def run(settings, project, brief, *, minutes, session_id=None, popen=subprocess.Popen):
    """Run Claude Code to completion or until the wall clock runs out. Returns a summary dict."""
    session_id = session_id or str(uuid.uuid4())
    cmd = build_command(settings, project, session_id=session_id)
    env = build_env(settings, project)
    Path(env["CLAUDE_CODE_TMPDIR"]).mkdir(parents=True, exist_ok=True, mode=0o700)
    reader = StreamReader()
    started = time.monotonic()
    proc = popen(cmd, cwd=str(project.work_dir), env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                 stderr=subprocess.DEVNULL, start_new_session=True)

    def pump():
        for raw in proc.stdout:
            try:
                reader.feed(raw.decode("utf-8", "replace"))
            except Exception:  # noqa: BLE001 - a bad line must never stop the reader
                reader.bad_lines += 1

    thread = threading.Thread(target=pump, daemon=True)
    thread.start()
    try:
        proc.stdin.write(brief.encode("utf-8"))
        proc.stdin.close()
    except BrokenPipeError:
        pass
    timed_out = False
    try:
        proc.wait(timeout=minutes * 60)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill(proc, settings.kill_grace_seconds)
    thread.join(timeout=10)
    proc.stdout.close()
    code = proc.returncode
    return {
        "sessionId": session_id,
        "timedOut": timed_out,
        "code": code if code is not None and code >= 0 else None,
        "signal": signal.Signals(-code).name if code is not None and code < 0 else None,
        "seconds": round(time.monotonic() - started, 1),
        "result": reader.result,
        "usage": reader.usage(),
        "stream": {"lines": reader.lines, "badLines": reader.bad_lines, "assistantMessages": reader.assistant_messages,
                   "toolUses": reader.tool_uses, "apiErrors": sorted(reader.api_errors)},
    }


def _kill(proc, grace):
    for sig, wait in ((signal.SIGTERM, grace), (signal.SIGKILL, 10)):
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            continue
