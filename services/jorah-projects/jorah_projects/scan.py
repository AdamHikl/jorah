"""gitleaks on a run's commits (PM-T5). Fails closed: a scan that can't run counts as a finding.

- `--redact`, always. The JSON report goes to a private temp file and only rule ids, file names
  and commit SHAs are kept from it; the file is deleted.
- The repo's own `.gitleaks.toml` and `.gitleaksignore` are ignored: a run could add either to hide
  what it committed. The runner's config (`services/jorah-projects/gitleaks.toml`) and an empty
  ignore file are passed explicitly.
- git inside gitleaks gets the same pinned, hook-free config as the runner's own git.
- `-m --first-parent` makes `git log -p` show a merge commit's whole change, so content added while
  resolving a conflict can't slip past.
"""

import json
import os
import subprocess
import tempfile

from .gitsafe import base_env


def scan(settings, project, start, end):
    """{"ran": bool, "findings": [{rule, file, commit}], "error": str|None}."""
    if not start or not end or start == end:
        return {"ran": True, "findings": [], "error": None}
    with tempfile.TemporaryDirectory(prefix="jorah-gitleaks-") as tmp:
        os.chmod(tmp, 0o700)
        report = os.path.join(tmp, "report.json")
        ignore = os.path.join(tmp, "gitleaksignore")
        open(ignore, "w").close()
        cmd = [
            settings.gitleaks_bin, "git", str(project.work_dir),
            "--config", str(settings.gitleaks_config),
            "--gitleaks-ignore-path", ignore,
            "--redact", "--no-banner", "--log-level", "error",
            "--report-format", "json", "--report-path", report,
            "--exit-code", "2",
            f"--log-opts=-m --first-parent {start}..{end}",
        ]
        env = base_env(tmp)
        env["PATH"] = "/usr/local/bin:/usr/bin:/bin"
        try:
            result = subprocess.run(cmd, capture_output=True, env=env, timeout=600, check=False)
        except (OSError, subprocess.TimeoutExpired) as error:
            return {"ran": False, "findings": [], "error": f"gitleaks couldn't run: {type(error).__name__}"}
        if result.returncode not in (0, 2):
            return {"ran": False, "findings": [], "error": f"gitleaks exited {result.returncode}"}
        try:
            with open(report, encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, ValueError):
            raw = None
        if result.returncode == 2 and not raw:
            return {"ran": True, "findings": [{"rule": "unknown", "file": None, "commit": None}], "error": "gitleaks found something but wrote no report"}
        findings = []
        for item in raw or []:
            if isinstance(item, dict):
                findings.append({
                    "rule": str(item.get("RuleID", "unknown"))[:60],
                    "file": str(item.get("File", ""))[:200] or None,
                    "commit": str(item.get("Commit", ""))[:40] or None,
                })
        if result.returncode == 2 and not findings:
            findings.append({"rule": "unknown", "file": None, "commit": None})
        return {"ran": True, "findings": findings, "error": None}
