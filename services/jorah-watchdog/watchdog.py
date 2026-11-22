#!/usr/bin/env python3
"""Tells Adam on Telegram when Jorah's Gateway or the project runner is down, without the Gateway.

Jorah's own messages go through the Gateway, so when it is down he can't say so. This runs every five
minutes from jorah-watchdog.timer as the system user jorah-watchdog and talks to Telegram's Bot API
directly, with its own bot (the plan's "rescue bot", docs/plan/02-architecture.md). Adam asked for it
on 2026-11-18.

  check   Look at the Gateway, the runner and the cron watch's report (cronwatch.py, run just
          before by jorah-cron-watch.service), keep track in the state file, send what is due.
          --dry-run prints what it would send and saves nothing.
  daily   Once a day (jorah-daily-watch.timer): OpenClaw's security advisories against what runs
          (advisories.py), and the night's drift report from jorah-drift.service (drift.py).
          --dry-run prints what it would send and saves nothing.
  test    Send one test message, to show the bot and the chat work.
  status  Print the state file. Sends nothing.

Rules: one alert per outage after it has lasted long enough, a reminder every 6 hours while it lasts,
one message when it's over. A check that can't be read counts as down, never as fine. When no check
ran for 30 minutes (the PC or WSL was off or asleep) it says so afterwards; while the PC is off
nothing can be sent at all. The bot token is never printed or logged.
"""

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import advisories  # noqa: E402
import cronwatch  # noqa: E402
import drift  # noqa: E402

DOWN_AFTER = {"gateway": 10 * 60, "runner": 20 * 60, "cron": 10 * 60}
NAMES = {"gateway": "Jorah (the Gateway)", "runner": "the project runner",
         "cron": "the Gateway's scheduler (hourly heartbeats, Dreaming)"}
CRON_UNIT = "jorah-cron-watch.service"
CRON_STALE_AFTER = 15 * 60
SKIP = object()  # not watched, or too early to tell: the state keeps what it had
REMIND_EVERY = 6 * 3600
GAP_AFTER = 30 * 60


def log(line):
    print(line, flush=True)


def systemd_show(unit, props):
    """A unit's properties from systemd, or None if systemd didn't answer."""
    try:
        out = subprocess.run(["systemctl", "show", unit, "-p", ",".join(props)],
                             capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line)


def readyz(port, timeout=5):
    """True when the Gateway's /readyz on loopback says ready."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{int(port)}/readyz", timeout=timeout) as response:
            return json.loads(response.read(65536)).get("ready") is True
    except (OSError, ValueError, urllib.error.URLError):
        return False


def observe(show, ready, cron=None, now=None):
    """{check: what is wrong, or None when fine}. Unreadable counts as wrong. cron is
    (the cron watch's report, whether to watch it only while its unit is installed), or None."""
    found = {}
    gateway = show("openclaw-gateway.service", ["ActiveState", "SubState"])
    if gateway is None:
        found["gateway"] = "systemd didn't answer"
    elif gateway.get("ActiveState") != "active":
        found["gateway"] = f"the service is {gateway.get('ActiveState')} ({gateway.get('SubState')})"
    elif not ready():
        found["gateway"] = "it runs but doesn't say ready"
    else:
        found["gateway"] = None
    for name, problem in (("runner", runner_problem(show)),
                          ("cron", SKIP if cron is None else cron_problem(show, *cron, now))):
        if problem is not SKIP:
            found[name] = problem
    return found


def runner_problem(show):
    timer = show("jorah-projects.timer", ["LoadState", "ActiveState"])
    service = show("jorah-projects.service", ["Result"])
    if timer is not None and timer.get("LoadState") == "not-found":
        return SKIP  # no runner installed, nothing to watch
    if timer is None or service is None:
        return "systemd didn't answer"
    if timer.get("ActiveState") != "active":
        return f"its timer is {timer.get('ActiveState')}"
    if service.get("Result") not in ("success", ""):
        return f"its last tick ended with {service.get('Result')}"
    return None


def cron_problem(show, report, only_if_installed, now):
    """From the cron watch's report: None when fine, SKIP while it says "pending" (or isn't
    installed), otherwise what is wrong. A missing, stale or "unknown" report counts as wrong."""
    if only_if_installed:
        unit = show(CRON_UNIT, ["LoadState"])
        if unit is None:
            return "systemd didn't answer"
        if unit.get("LoadState") == "not-found":
            return SKIP
    if not report:
        return f"unknown: no report from the cron watch ({CRON_UNIT})"
    try:
        checked = float(report.get("checked_at") or 0)
    except (TypeError, ValueError):
        checked = 0
    if not checked or now - checked > CRON_STALE_AFTER:
        return ("unknown: the cron watch's newest report is from "
                f"{clock_text(checked)}" if checked else "unknown: the cron watch's report has no time")
    status, summary = report.get("status"), report.get("summary") or "no details"
    if status == "ok":
        return None
    if status == "pending":
        return SKIP
    if status == "failing":
        return summary
    return f"unknown: {summary}"


def clock_text(ts):
    return time.strftime("%H:%M", time.localtime(ts))


def span_text(seconds):
    minutes = int(seconds // 60)
    if minutes < 90:
        return f"{minutes} min"
    return f"{minutes // 60} h {minutes % 60:02d} min"


def step(state, found, now):
    """Advance the state for one check. Returns the messages that are due, each with what to mark."""
    due = []
    last = state.get("last_check")
    if last is not None and now - last > GAP_AFTER:
        due.append(("gap", None, f"Jorah's watchdog: no check ran from {clock_text(last)} to {clock_text(now)} "
                                  f"({span_text(now - last)}). The PC or its Linux side was probably off or "
                                  f"asleep, so Jorah couldn't be reached then."))
    state["last_check"] = now
    checks = state.setdefault("checks", {})
    for name, problem in found.items():
        entry = checks.setdefault(name, {"since": None, "problem": None, "alerted_at": None})
        if problem:
            if entry["since"] is None:
                entry["since"] = now
            entry["problem"] = problem
            down_for = now - entry["since"]
            if entry["alerted_at"] is None and down_for >= DOWN_AFTER[name]:
                due.append(("alert", name, f"Jorah alert: {NAMES[name]} has been down since "
                                           f"{clock_text(entry['since'])} ({span_text(down_for)}): {problem}."))
            elif entry["alerted_at"] is not None and now - entry["alerted_at"] >= REMIND_EVERY:
                due.append(("alert", name, f"Jorah alert, still: {NAMES[name]} has been down since "
                                           f"{clock_text(entry['since'])} ({span_text(down_for)}): {problem}."))
        else:
            if entry["alerted_at"] is not None:
                due.append(("back", name, f"Back: {NAMES[name]} is up again, after "
                                          f"{span_text(now - entry['since'])} down."))
            else:
                checks[name] = {"since": None, "problem": None, "alerted_at": None}
    return due


def mark_sent(state, kind, name, now):
    if kind == "alert":
        state["checks"][name]["alerted_at"] = now
    elif kind == "back":
        state["checks"][name] = {"since": None, "problem": None, "alerted_at": None}


def send(token, chat_id, text, opener=urllib.request.urlopen):
    """Sends one message. True on success. Never puts the token in a log line."""
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text,
                                   "disable_web_page_preview": "true"}).encode()
    request = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage", data=data)
    try:
        with opener(request, timeout=20) as response:
            return json.loads(response.read(65536)).get("ok") is True
    except urllib.error.HTTPError as error:
        log(f"Telegram answered {error.code}")
    except (OSError, ValueError, urllib.error.URLError) as error:
        log(f"Telegram unreachable: {type(error).__name__}")
    return False


def read_token(path):
    try:
        token = Path(path).read_text().strip()
    except OSError:
        return None
    return token or None


def load_state(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    path = Path(path)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    with open(tmp, "rb") as handle:
        os.fsync(handle.fileno())
    tmp.replace(path)


DRIFT_STALE_AFTER = 36 * 3600
DRILL_REPORT = "/var/lib/jorah-toolbox-drill/last.json"
DRILL_STALE_AFTER = 8 * 24 * 3600


def _drill_checked_at(report):
    checked = report.get("checked_at")
    if isinstance(checked, (int, float)) and not isinstance(checked, bool):
        return float(checked)
    at = report.get("at")
    if isinstance(at, str):
        try:
            return datetime.fromisoformat(at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def drill_step(state, report_path, now):
    """One-line daily message when the toolbox drill failed or is older than 8 days.

    A missing report says nothing. Never includes file paths.
    """
    path = Path(report_path)
    if not path.exists():
        state.pop("toolbox_drill", None)
        return []
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        report = None
    if not isinstance(report, dict):
        line = "Jorah's toolbox drill report couldn't be read."
        key = "unreadable"
    else:
        checked_at = _drill_checked_at(report)
        stale = checked_at is None or (now - checked_at > DRILL_STALE_AFTER)
        failed = not report.get("ok")
        if not failed and not stale:
            state.pop("toolbox_drill", None)
            return []
        names = []
        if failed:
            names = [str(n) for n in (report.get("failed") or []) if isinstance(n, str) and n]
            if not names and isinstance(report.get("cases"), list):
                names = [str(c.get("name")) for c in report["cases"]
                         if isinstance(c, dict) and not c.get("ok") and c.get("name")]
            names = [os.path.basename(n) for n in names]
        since = (time.strftime("%Y-%m-%d", time.gmtime(checked_at))
                 if checked_at is not None else "unknown") if stale else None
        if failed:
            line = f"Jorah's toolbox drill failed ({', '.join(names) if names else 'unknown cases'})" + (
                f"; toolbox drill hasn't run since {since}." if stale else ".")
        else:
            line = f"Jorah's toolbox drill hasn't run since {since}."
        key = json.dumps([checked_at, failed, names, stale], sort_keys=True)
    if state.get("toolbox_drill", {}).get("sent") == key:
        return []
    return [("toolbox-drill", key, line)]


def drift_step(state, report, now):
    """Messages due from the drift report. Unknown after a day without a good report, never 'fine'."""
    due = []
    entry = state.setdefault("drift", {"last_ok": None, "since": None, "alerted_unknown": False,
                                       "sent": None})
    fresh = report.get("ok") and now - float(report.get("checked_at") or 0) <= DRIFT_STALE_AFTER
    if not fresh:
        if entry["since"] is None:
            entry["since"] = now
        why = report.get("error") or ("no report" if not report else "the report is older than 36 hours")
        if not entry["alerted_unknown"] and now - (entry["last_ok"] or entry["since"]) >= 24 * 3600:
            due.append(("drift-unknown", None, f"Jorah's drift check: unknown ({why}). It can't say whether "
                                               f"reviewed files on the PC changed."))
        return due
    if entry["alerted_unknown"]:
        due.append(("drift-readable", None, "Jorah's drift check is reporting again."))
    entry.update({"last_ok": now, "since": None})
    text = drift.report_text(report)
    fingerprint = None if text is None else json.dumps(
        [report["changed"], report["missing"], report["unrecorded"]], sort_keys=True)
    if fingerprint != entry["sent"]:
        if text is not None:
            due.append(("drift", fingerprint, text))
        elif entry["sent"] is not None:
            due.append(("drift", None, "Jorah's drift check: every reviewed file matches its deploy again."))
    return due


def daily_mark(state, kind, key, now):
    if kind == "drift":
        state["drift"]["sent"] = key
    elif kind == "drift-unknown":
        state["drift"]["alerted_unknown"] = True
    elif kind == "drift-readable":
        state["drift"]["alerted_unknown"] = False
    elif kind == "toolbox-drill":
        state["toolbox_drill"] = {"sent": key}
    else:
        advisories.mark_sent(state, kind, key, now)


def merged_installed(read_installed, report, now):
    """openclaw and its bundled plugins, plus the npm-installed plugins from the drift report.
    Raises OSError when that list is missing or stale: those plugins are then unknown."""
    found = {name: [version] for name, version in read_installed().items()}
    fresh = now - float(report.get("checked_at") or 0) <= DRIFT_STALE_AFTER
    if not fresh or not isinstance(report.get("packages"), dict):
        raise OSError("no fresh list of the plugins in Jorah's state folder (jorah-drift's report)")
    for name, versions in report["packages"].items():
        found[name] = sorted(set(found.get(name, [])) | set(versions))
    return found


def daily(args, now, opener, read_installed):
    state = load_state(args.daily_state)
    report = load_state(args.drift_report)
    due = advisories.step(state, now, lambda known: advisories.fetch(known, opener),
                          lambda: merged_installed(read_installed, report, now))
    if state.get("source", {}).get("problem"):
        log(f"advisories: unknown, {state['source']['problem']}")
    else:
        installed = ", ".join(f"{k} {'/'.join(v)}" for k, v in sorted(state.get("installed", {}).items())
                              if k == "openclaw" or k in report.get("packages", {}))
        log(f"advisories: {len(state.get('advisories', {}))} known; checked against {installed}; "
            f"{len(state.get('notified', {}))} told so far")
    due += drift_step(state, report, now)
    due += drill_step(state, args.drill_report, now)
    if args.dry_run:
        for kind, _, text in due:
            log(f"would send ({kind}):\n{text}")
        log(f"{len(due)} message(s) due; dry run, nothing sent or saved")
        return 0
    token = read_token(args.token_file)
    for kind, key, text in due:
        if not token:
            log(f"due but no bot token, not sent: {kind}")
            continue
        if send(token, args.chat_id, text, opener):
            daily_mark(state, kind, key, now)
            log(f"sent: {kind} {key if isinstance(key, str) and kind != 'drift' else ''}".rstrip())
        else:
            log(f"not sent, will try tomorrow: {kind}")
    save_state(args.daily_state, state)
    return 0


def main(argv=None, now=None, show=systemd_show, opener=urllib.request.urlopen,
         read_installed=advisories.installed_packages):
    parser = argparse.ArgumentParser(prog="jorah-watchdog")
    parser.add_argument("command", choices=["check", "daily", "test", "status"], nargs="?", default="check")
    parser.add_argument("--conf", default="/etc/jorah-watchdog/watchdog.conf")
    parser.add_argument("--token-file", default="/etc/jorah-watchdog/telegram.token")
    parser.add_argument("--state", default="/var/lib/jorah-watchdog/state.json")
    parser.add_argument("--daily-state", default="/var/lib/jorah-watchdog/daily.json")
    parser.add_argument("--drift-report", default=drift.REPORT)
    parser.add_argument("--drill-report", default=DRILL_REPORT)
    parser.add_argument("--cron-report", default=None,
                        help=f"default {cronwatch.REPORT}, watched while {CRON_UNIT} is installed; "
                             "a path given here is always watched")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    now = time.time() if now is None else now

    if args.command == "status":
        print(json.dumps(load_state(args.state), indent=2))
        daily_state = load_state(args.daily_state)
        if daily_state:
            print(json.dumps({k: v for k, v in daily_state.items() if k != "advisories"}, indent=2))
        return 0
    try:
        conf = json.loads(Path(args.conf).read_text())
        chat_id, port = str(conf["chat_id"]), int(conf.get("gateway_port", 43181))
    except (OSError, ValueError, KeyError) as error:
        log(f"no usable {args.conf}: {type(error).__name__}")
        return 2
    args.chat_id = chat_id
    if args.command == "daily":
        return daily(args, now, opener, read_installed)
    token = read_token(args.token_file)

    if args.command == "test":
        if not token:
            log(f"no bot token in {args.token_file}: store it with scripts/pc/store-watchdog-token.sh")
            return 3
        ok = send(token, chat_id, "Test from Jorah's watchdog. Alerts about Jorah being down come from this "
                                  "bot, not from Jorah.", opener)
        log("test message sent" if ok else "test message not sent")
        return 0 if ok else 1

    state = load_state(args.state)
    cron_report = load_state(args.cron_report or cronwatch.REPORT)
    cron_report = cron_report if isinstance(cron_report, dict) else {}
    found = observe(show, lambda: readyz(port), (cron_report, args.cron_report is None), now)
    due = step(state, found, now)
    log("checks: " + ", ".join(f"{k} {'ok' if v is None else 'DOWN (' + v + ')'}" for k, v in found.items()))
    if "cron" not in found and cron_report.get("status") == "pending":
        log(f"cron: pending, state kept ({cron_report.get('summary')})")
    if args.dry_run:
        for kind, _, text in due:
            log(f"would send ({kind}):\n{text}")
        log(f"{len(due)} message(s) due; dry run, nothing sent or saved")
        return 0
    for kind, name, text in due:
        if not token:
            log(f"due but no bot token yet, not sent: {kind} {name or ''}".rstrip())
            continue
        if send(token, chat_id, text, opener):
            mark_sent(state, kind, name, now)
            log(f"sent: {kind} {name or ''}".rstrip())
        elif kind == "gap":
            log("not sent: gap")
        else:
            log(f"not sent, will try at the next check: {kind} {name}")
    save_state(args.state, state)
    return 0


if __name__ == "__main__":
    sys.exit(main())
