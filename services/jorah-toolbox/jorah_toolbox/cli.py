"""jorah-toolbox: run-queue | status | check FILE | record-apt ID | forget-apt NAME

run-queue    process every approval (jorah-toolbox.service runs this, as user jorah-toolbox)
status       installed tools, approvals waiting, recent results
check FILE   check a request file against jorah-tool-v1 (prints problems, exit 1 if any)
record-apt   called by scripts/pc/toolbox-apt.sh after it installed a request's Ubuntu packages
forget-apt   called by scripts/pc/toolbox-apt.sh --remove after it purged a tool's packages
"""

import json
import subprocess
import sys

from . import install


def _dpkg_versions(packages):
    out = {}
    for name in packages:
        done = subprocess.run(["/usr/bin/dpkg-query", "-W", "-f=${db:Status-Abbrev} ${Version}", name],
                              capture_output=True, text=True, check=False, env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"})
        status, _, version = done.stdout.partition(" ")
        if done.returncode == 0 and status.startswith("ii"):
            out[name] = version.strip()
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__.strip())
        return 0 if argv else 2
    command, args = argv[0], argv[1:]
    settings = install.Settings()
    try:
        if command == "run-queue":
            results = install.Installer(settings).run_queue()
            return 1 if any(r["status"] == "failed" for r in results) else 0
        if command == "status":
            return install.main_status(settings)
        if command == "check" and len(args) == 1:
            tc = install._load_contract(settings.contract)
            try:
                problems = tc.check(tc.load_file(args[0]), settings.day())
            except (OSError, ValueError) as error:
                problems = [str(error)]
            for line in problems:
                print(line)
            if not problems:
                print("ok")
            return 1 if problems else 0
        if command == "record-apt" and len(args) == 1:
            inst = install.Installer(settings)
            pending = install.read_json(inst.results / f"{args[0]}.json")
            packages = ((pending or {}).get("manifest") or {}).get("packages") or []
            result = inst.record_apt(args[0], _dpkg_versions(packages))
            print(json.dumps({"id": result["id"], "status": result["status"], "packages": result["checks"].get("packages")}))
            return 0
        if command == "forget-apt" and len(args) == 1:
            print(json.dumps(install.Installer(settings).forget_apt(args[0])))
            return 0
    except (install.Refused, ValueError, OSError) as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
    print(__doc__.strip(), file=sys.stderr)
    return 2
