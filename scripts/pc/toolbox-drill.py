#!/usr/bin/env python3
"""Weekly toolbox drill: runs representative requests through the real plugin, installer, and
bubblewrap smoke test on a fresh scratch toolbox, leaving the live toolbox untouched.
"""

import argparse
import copy
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "services" / "jorah-toolbox"))
sys.path.insert(0, str(REPO_ROOT / "services" / "jorah-projects"))

from jorah_projects import config as proj_config  # noqa: E402
from jorah_projects import toolbox as proj_toolbox  # noqa: E402
from jorah_toolbox import install  # noqa: E402

DEFAULT_CASES = REPO_ROOT / "deploy" / "toolbox-drill" / "cases.json"
HARNESS = REPO_ROOT / "scripts" / "pc" / "toolbox-drill.mjs"
SYSTEM_REPORT = Path("/var/lib/jorah-toolbox-drill/last.json")
USER_REPORT = Path.home() / ".jorah-toolbox-drill" / "last.json"


def default_report_path():
    """Return /var/lib/jorah-toolbox-drill/last.json when writable, else ~/.jorah-toolbox-drill/last.json."""
    parent = SYSTEM_REPORT.parent
    if parent.is_dir() and os.access(parent, os.W_OK | os.X_OK):
        if not SYSTEM_REPORT.exists() or os.access(SYSTEM_REPORT, os.W_OK):
            return SYSTEM_REPORT
    return USER_REPORT


def default_scratch_root(now=None):
    now = now or datetime.now(timezone.utc)
    return Path.home() / "sandbox" / "toolbox-drill" / now.strftime("%Y%m%dT%H%M%SZ")


def load_cases(path=DEFAULT_CASES):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict) and "cases" in data:
        data = data["cases"]
    if not isinstance(data, list) or not data:
        raise ValueError(f"{path} must hold a non-empty JSON list of cases")
    return data


def prepare_request(request, today=None):
    """Return a copy of `request`, expanding '$TODAY' to today's ISO date."""
    today = today or datetime.now(timezone.utc).date()
    out = copy.deepcopy(request)
    if out.get("released") == "$TODAY":
        out["released"] = today.isoformat()
    return out


def make_case_dirs(case_root):
    """Create the scratch opt, var, state, work, guard, and smoke-home folders for one case."""
    case_root = Path(case_root)
    opt = case_root / "opt"
    var = case_root / "var"
    state = case_root / "state"
    runner_state = case_root / "runner-state"
    work = case_root / "work"
    guard = case_root / "guard"
    # Keep smoke's tmpfs home under smoke-home/ so it never hides case_root/opt inside bwrap.
    sandbox_dir = case_root / "smoke-home" / "jorah" / "sandbox"
    for sub in ("bin", "tools", ".staging"):
        (opt / sub).mkdir(parents=True, exist_ok=True)
    for sub in ("proposals", "approved", "results", "tested", "downloads"):
        (var / sub).mkdir(parents=True, exist_ok=True)
    for d in (state, runner_state, work, guard, sandbox_dir):
        d.mkdir(parents=True, exist_ok=True)
    return {
        "opt": opt,
        "var": var,
        "state": state,
        "runner_state": runner_state,
        "work": work,
        "guard": guard,
        "registry_file": case_root / "projects.json",
        "sandbox_dir": sandbox_dir,
    }


def compare_outcome(expect, propose_res, install_call, install_res, smoke_res):
    """Compare observed drill results with `expect`. Returns a list of problem strings."""
    problems = []
    propose_res = propose_res if isinstance(propose_res, dict) else {}
    got_propose = propose_res.get("status")
    want_propose = expect.get("propose")
    if got_propose != want_propose:
        detail = propose_res.get("reason") or propose_res.get("problems") or "no details"
        problems.append(f"propose: got {got_propose!r} ({detail}), expected {want_propose!r}")
        return problems

    match = expect.get("match")
    if match is not None:
        raw_probs = propose_res.get("problems") or []
        haystack = "\n".join([*(str(p) for p in raw_probs), str(propose_res.get("reason") or "")])
        if match not in haystack:
            problems.append(f"refusal did not match {match!r} (got {raw_probs or propose_res.get('reason')!r})")

    want_install = expect.get("install")
    if want_install is None:
        if install_call is not None or install_res is not None:
            got_status = (install_res or install_call or {}).get("status")
            problems.append(f"install: expected none, got {got_status!r}")
    else:
        call_status = (install_call or {}).get("status")
        if call_status != "approved":
            reason = (install_call or {}).get("reason") or "not approved"
            problems.append(f"toolbox_install: got {call_status!r} ({reason}), expected 'approved'")
            return problems
        got_install = (install_res or {}).get("status")
        if got_install != want_install:
            err = (install_res or {}).get("error") or "no details"
            problems.append(f"install: got {got_install!r} ({err}), expected {want_install!r}")
            return problems

    want_by_name = bool(expect.get("commandsFoundByName", False))
    got_by_name = bool(((install_res or {}).get("checks") or {}).get("commandsFoundByName"))
    if got_by_name != want_by_name:
        problems.append(f"commandsFoundByName: got {got_by_name}, expected {want_by_name}")

    want_smoke = expect.get("smoke_contains")
    if want_smoke is not None:
        if not isinstance(smoke_res, dict):
            problems.append("smoke: did not run")
        elif not smoke_res.get("ok"):
            problems.append(f"smoke: failed (exit={smoke_res.get('exit')}, error={smoke_res.get('error')})")
        elif want_smoke not in (smoke_res.get("output") or ""):
            problems.append(f"smoke: output missing {want_smoke!r}")
    elif want_install == "installed":
        if not isinstance(smoke_res, dict) or not smoke_res.get("ok"):
            err = (smoke_res or {}).get("error") if isinstance(smoke_res, dict) else "did not run"
            problems.append(f"smoke: failed ({err})")

    return problems


def summarize_case(name, problems, propose_res, install_res, smoke_res):
    """Build a secret-free per-case report record."""
    propose_res = propose_res if isinstance(propose_res, dict) else {}
    checks = (install_res or {}).get("checks") if isinstance(install_res, dict) else None
    checks = checks if isinstance(checks, dict) else {}
    download_bytes = checks.get("downloadBytes")
    return {
        "name": name,
        "ok": not problems,
        "problems": list(problems),
        "download_bytes": download_bytes if isinstance(download_bytes, int) else None,
        "propose": {
            "status": propose_res.get("status"),
            "id": propose_res.get("id"),
            "reason": propose_res.get("reason"),
            "problems": propose_res.get("problems"),
        },
        "install": None if not isinstance(install_res, dict) else {
            "status": install_res.get("status"),
            "error": install_res.get("error"),
            "commandsFoundByName": checks.get("commandsFoundByName"),
            "downloadBytes": download_bytes,
            "installedBytes": checks.get("installedBytes"),
        },
        "smoke": None if not isinstance(smoke_res, dict) else {
            "ok": smoke_res.get("ok"),
            "exit": smoke_res.get("exit"),
            "seconds": smoke_res.get("seconds"),
            "expectFound": smoke_res.get("expectFound"),
            "error": smoke_res.get("error"),
            "output": (smoke_res.get("output") or "")[:600],
        },
    }


def build_report(case_records, started_at, finished_at):
    """Build the full report JSON structure (secret-free)."""
    failed = [c["name"] for c in case_records if not c["ok"]]
    return {
        "v": 1,
        "at": finished_at.isoformat(timespec="seconds"),
        "checked_at": round(finished_at.timestamp(), 3),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 2),
        "ok": bool(case_records) and not failed,
        "failed": failed,
        "total_download_bytes": sum(c.get("download_bytes") or 0 for c in case_records),
        "cases": case_records,
    }


def write_report(path, report):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(report, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp, 0o644)
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


def run_node_harness(dirs, request, *, node_bin=None, harness=HARNESS):
    node = node_bin or shutil.which("node") or "/usr/local/bin/node"
    cmd = [
        node,
        str(harness),
        "--toolbox-dir", str(dirs["opt"]),
        "--toolbox-var", str(dirs["var"]),
        "--state-root", str(dirs["runner_state"]),
        "--registry-file", str(dirs["registry_file"]),
        "--work-root", str(dirs["work"]),
        "--guard-state-dir", str(dirs["guard"]),
    ]
    done = subprocess.run(cmd, input=json.dumps(request), text=True, capture_output=True, timeout=120, check=False)
    if done.returncode != 0:
        err = (done.stderr or done.stdout or f"exit {done.returncode}").strip().splitlines()[-1][:200]
        raise RuntimeError(f"node harness failed: {err}")
    lines = [line for line in done.stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("node harness printed no output")
    return json.loads(lines[-1])


def run_case(case, scratch_root, *, today=None, node_bin=None, harness=HARNESS):
    """Execute one case end-to-end against an isolated scratch directory under `scratch_root`."""
    name = case["name"]
    dirs = make_case_dirs(Path(scratch_root) / name)
    request = prepare_request(case["request"], today=today)
    propose_res = install_call = install_res = smoke_res = None
    problems = []
    try:
        out = run_node_harness(dirs, request, node_bin=node_bin, harness=harness)
        propose_res = out.get("propose")
        install_call = out.get("install")
        approvals = list(dirs["var"].joinpath("approved").glob("*.json"))
        if approvals:
            unsquashfs = shutil.which("unsquashfs") or "/usr/bin/unsquashfs"
            installer = install.Installer(
                install.Settings(
                    opt=dirs["opt"],
                    var=dirs["var"],
                    state_root=str(dirs["state"]),
                    approver=None,
                    unsquashfs=unsquashfs,
                ),
                log=lambda _line: None,
            )
            results = installer.run_queue()
            install_res = results[0] if results else None
            if isinstance(install_res, dict) and install_res.get("status") == "installed":
                tool_name = install_res["name"]
                tool_entry = installer.installed()["tools"][tool_name]
                (dirs["state"] / tool_name).mkdir(parents=True, exist_ok=True)
                runner_settings = proj_config.Settings(
                    toolbox_dir=dirs["opt"],
                    toolbox_var=dirs["var"],
                    toolbox_state=dirs["state"],
                    state_root=dirs["runner_state"],
                    sandbox_dir=dirs["sandbox_dir"],
                    bwrap_bin=shutil.which("bwrap") or "/usr/bin/bwrap",
                )
                smoke_res = proj_toolbox.smoke(runner_settings, tool_entry)
        problems = compare_outcome(case["expect"], propose_res, install_call, install_res, smoke_res)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        problems = [str(error).splitlines()[0][:200]]
    return summarize_case(name, problems, propose_res, install_res, smoke_res)


def select_cases(cases, names):
    if not names:
        return cases
    by_name = {c["name"]: c for c in cases}
    missing = [n for n in names if n not in by_name]
    if missing:
        raise ValueError(f"unknown case(s): {', '.join(missing)}")
    wanted = set(names)
    return [c for c in cases if c["name"] in wanted]


def main(argv=None):
    parser = argparse.ArgumentParser(prog="toolbox-drill", description=__doc__)
    parser.add_argument("--cases", default=str(DEFAULT_CASES), help="Path to cases.json")
    parser.add_argument("--case", action="append", dest="cases_filter", help="Run only the named case (repeatable)")
    parser.add_argument("--scratch-root", default=None, help="Scratch directory root (default ~/sandbox/toolbox-drill/<UTC>)")
    parser.add_argument("--report", default=None, help="Report JSON path")
    parser.add_argument("--keep", action="store_true", help="Keep the scratch directory after running")
    parser.add_argument("--dry-run", action="store_true", help="Print what would run without running anything")
    args = parser.parse_args(argv)

    try:
        all_cases = load_cases(args.cases)
        selected = select_cases(all_cases, args.cases_filter)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    scratch_root = Path(args.scratch_root) if args.scratch_root else default_scratch_root()
    report_path = Path(args.report) if args.report else default_report_path()

    if args.dry_run:
        print(f"scratch root: {scratch_root}")
        print(f"report path:  {report_path}")
        for c in selected:
            req = c["request"]
            target = req.get("url") or ", ".join(req.get("packages") or [])
            exp = c["expect"]
            print(f"- {c['name']}: {req.get('kind')} {req.get('name')} ({target}) -> "
                  f"propose={exp.get('propose')}, install={exp.get('install')}")
        return 0

    started_at = datetime.now(timezone.utc)
    records = []
    try:
        scratch_root.mkdir(parents=True, exist_ok=True)
        for case in selected:
            rec = run_case(case, scratch_root, today=started_at.date())
            records.append(rec)
            if rec["ok"]:
                print(f"{rec['name']}: ok", flush=True)
            else:
                print(f"{rec['name']}: FAIL: {'; '.join(rec['problems'])}", flush=True)
    finally:
        if not args.keep and scratch_root.exists():
            shutil.rmtree(scratch_root, ignore_errors=True)

    finished_at = datetime.now(timezone.utc)
    report = build_report(records, started_at, finished_at)
    write_report(report_path, report)
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
