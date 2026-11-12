"""Read-only preflight for Jorah's iOS builds on the Mac (issue 10).

Run through scripts/mac/ios-preflight.sh as `adam` or as `jorah-build`. It never uses sudo, never
writes, and never reads a key, a certificate's private part or the shared runner key's content:
only names, owners, modes and exit codes. Each line is

  done     the step is in place, checked here
  missing  checked here, and not in place
  unknown  could not be checked from this user (or the check failed); never counted as done
  info     context, not a step

with the runbook step (docs/runbooks/ios-builds.md, "Adam's steps") that fixes it.
Exit code: 0 all done, 1 something missing, 3 nothing missing but something unknown.

Python 3.9 standard library only, like services/ios-runner.
"""

from __future__ import annotations

import grp
import json
import os
import plistlib
import pwd
import stat
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

BUILD_USER = "jorah-build"
HANDOFF_GROUP = "jorah-handoff"
LIBEXEC = "/usr/local/libexec/jorah"
RUNNER_BIN = LIBEXEC + "/ios-runner/bin/jorah-ios-runner"
AGENT_WRAPPER = LIBEXEC + "/ios-runner-agent"
AGENT_LABEL = "com.jorah.ios-runner"
AGENT_PLIST = "/Library/LaunchAgents/" + AGENT_LABEL + ".plist"
ADMIN_CONF = "/Library/Application Support/Jorah"
ALLOWLIST = ADMIN_CONF + "/ios-projects.json"
HANDOFF = "/Users/Shared/jorah-handoff"
PORT = 47820
HEALTH_URL = "http://127.0.0.1:%d/v1/health" % PORT
CONTRACT = "jorah-ios/1"
KEY_REL = ".config/jorah-ios/runner.key"
PROFILES_REL = "Library/Developer/Xcode/UserData/Provisioning Profiles"

DONE, MISSING, UNKNOWN, INFO = "done", "missing", "unknown", "info"


@dataclass
class Result:
    status: str
    what: str
    detail: str = ""
    fix: str = ""


class System:
    """Everything the checks read from the machine. Tests replace it with a fake."""

    def user(self) -> str:
        return pwd.getpwuid(os.getuid()).pw_name

    def home_of(self, name: str) -> Optional[str]:
        try:
            return pwd.getpwnam(name).pw_dir
        except KeyError:
            return None

    def uid_of(self, name: str) -> Optional[int]:
        try:
            return pwd.getpwnam(name).pw_uid
        except KeyError:
            return None

    def group_members(self, group: str) -> Optional[List[str]]:
        """Members from Directory Services; None if the group does not exist."""
        try:
            grp.getgrnam(group)
        except KeyError:
            return None
        code, out = self.run(["/usr/bin/dscl", ".", "-read", "/Groups/" + group, "GroupMembership"])
        if code != 0:
            return []
        return out.replace("GroupMembership:", "").split()

    def is_member(self, user: str, group: str) -> Optional[bool]:
        code, _ = self.run(["/usr/sbin/dseditgroup", "-o", "checkmember", "-m", user, group])
        if code is None:
            return None
        return code == 0

    def stat(self, path: str):
        """os.stat_result, None if absent, or "denied"."""
        try:
            return os.stat(path)
        except FileNotFoundError:
            return None
        except PermissionError:
            return "denied"
        except OSError:
            return "denied"

    def listdir(self, path: str):
        try:
            return os.listdir(path)
        except FileNotFoundError:
            return None
        except OSError:
            return "denied"

    def read_bytes(self, path: str) -> Optional[bytes]:
        """For the allowlist and plists only, never for a key."""
        try:
            with open(path, "rb") as f:
                return f.read()
        except OSError:
            return None

    def run(self, argv: List[str], timeout: int = 30) -> Tuple[Optional[int], str]:
        try:
            p = subprocess.run(argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout,
                               stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired):
            return None, ""
        return p.returncode, p.stdout.decode("utf-8", "replace")

    def http_get(self, url: str) -> Tuple[Optional[int], str]:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:  # loopback only
                return r.status, r.read(4096).decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            return e.code, ""
        except (urllib.error.URLError, OSError, ValueError):
            return None, ""


def owner_mode(st) -> Tuple[int, int, int]:
    return st.st_uid, st.st_gid, stat.S_IMODE(st.st_mode)


def check_user(sys_: System) -> List[Result]:
    out = []
    if sys_.uid_of(BUILD_USER) is None:
        out.append(Result(MISSING, "user jorah-build exists", "", "A2"))
        return out
    out.append(Result(DONE, "user jorah-build exists"))
    admin = sys_.is_member(BUILD_USER, "admin")
    if admin is None:
        out.append(Result(UNKNOWN, "jorah-build is not an admin", "dseditgroup did not answer", "A2"))
    elif admin:
        out.append(Result(MISSING, "jorah-build is not an admin", "it IS an admin: remove it from admin", "A2"))
    else:
        out.append(Result(DONE, "jorah-build is not an admin"))
    dev = sys_.is_member(BUILD_USER, "_developer")
    out.append(Result({True: DONE, False: MISSING, None: UNKNOWN}[dev], "jorah-build is in _developer", "", "A2"))
    code, out_auto = sys_.run(["/usr/bin/defaults", "read", "/Library/Preferences/com.apple.loginwindow",
                               "autoLoginUser"])
    if code is None:
        out.append(Result(UNKNOWN, "automatic login is not jorah-build", "", "A2"))
    elif code == 0 and out_auto.strip() == BUILD_USER:
        out.append(Result(MISSING, "automatic login is not jorah-build", "autologin is set to jorah-build", "A2"))
    else:
        out.append(Result(DONE, "automatic login is not jorah-build"))
    return out


def check_group(sys_: System, adam: Optional[str]) -> List[Result]:
    members = sys_.group_members(HANDOFF_GROUP)
    if members is None:
        return [Result(MISSING, "group jorah-handoff exists", "", "A2")]
    res = [Result(DONE, "group jorah-handoff exists")]
    if adam:
        res.append(Result(DONE if adam in members else MISSING, "%s is in jorah-handoff" % adam, "", "A2"))
    return res


def _root_dir(sys_: System, path: str, what: str, step: str, mode: int = 0o755) -> Result:
    st = sys_.stat(path)
    if st is None:
        return Result(MISSING, what, path, step)
    if st == "denied":
        return Result(UNKNOWN, what, "cannot stat " + path, step)
    uid, gid, m = owner_mode(st)
    if uid == 0 and gid == 0 and m == mode:
        return Result(DONE, what, "root:wheel %o" % m)
    return Result(MISSING, what, "is uid %d gid %d mode %o, want root:wheel %o" % (uid, gid, m, mode), step)


def check_dirs(sys_: System) -> List[Result]:
    res = [_root_dir(sys_, LIBEXEC, "runner directory root-owned", "A2"),
           _root_dir(sys_, ADMIN_CONF, "allowlist directory root-owned", "A2")]
    st = sys_.stat(HANDOFF)
    gid = None
    try:
        gid = grp.getgrnam(HANDOFF_GROUP).gr_gid
    except KeyError:
        pass
    build_uid = sys_.uid_of(BUILD_USER)
    if st is None:
        res.append(Result(MISSING, "handoff folder", HANDOFF, "A2"))
    elif st == "denied":
        res.append(Result(UNKNOWN, "handoff folder", "cannot stat", "A2"))
    else:
        uid, g, m = owner_mode(st)
        ok = build_uid is not None and uid == build_uid and gid is not None and g == gid and m == 0o750
        res.append(Result(DONE if ok else MISSING, "handoff folder jorah-build:jorah-handoff 0750",
                          "" if ok else "uid %d gid %d mode %o" % (uid, g, m), "" if ok else "A2"))
        code, out = sys_.run(["/bin/ls", "-led", HANDOFF])
        if code is None:
            res.append(Result(UNKNOWN, "handoff folder group ACL", "", "A2"))
        else:
            has = ("group:%s allow" % HANDOFF_GROUP) in out and "directory_inherit" in out
            res.append(Result(DONE if has else MISSING, "handoff folder group ACL", "", "" if has else "A2"))
    return res


def _root_file(sys_: System, path: str, what: str, step: str, executable: bool) -> Result:
    st = sys_.stat(path)
    if st is None:
        return Result(MISSING, what, path, step)
    if st == "denied":
        return Result(UNKNOWN, what, "cannot stat " + path, step)
    uid, gid, m = owner_mode(st)
    if uid != 0 or m & 0o022:
        return Result(MISSING, what, "not root-owned or writable by others (uid %d mode %o)" % (uid, m), step)
    if executable and not m & 0o111:
        return Result(MISSING, what, "not executable", step)
    return Result(DONE, what)


def check_runner_install(sys_: System) -> List[Result]:
    res = [_root_file(sys_, RUNNER_BIN, "runner installed, root-owned", "A9", True),
           _root_file(sys_, AGENT_WRAPPER, "agent wrapper installed, root-owned", "A9", True),
           _root_file(sys_, AGENT_PLIST, "LaunchAgent plist installed, root-owned", "A9", False)]
    if res[-1].status == DONE:
        data = sys_.read_bytes(AGENT_PLIST)
        try:
            plist = plistlib.loads(data or b"")
            ok = plist.get("Label") == AGENT_LABEL and plist.get("ProgramArguments") == [AGENT_WRAPPER]
        except Exception:  # noqa: BLE001 - any parse failure is a finding, not a crash
            ok = False
        res.append(Result(DONE if ok else MISSING, "LaunchAgent plist matches the repo", "", "" if ok else "A9"))
    return res


def check_allowlist(sys_: System) -> List[Result]:
    st = sys_.stat(ALLOWLIST)
    if st is None:
        return [Result(MISSING, "allowlist ios-projects.json", ALLOWLIST, "A8")]
    if st == "denied":
        return [Result(UNKNOWN, "allowlist ios-projects.json", "cannot stat", "A8")]
    uid, _, m = owner_mode(st)
    res = []
    if uid != 0 or m & 0o022:
        res.append(Result(MISSING, "allowlist root-owned, not group/other writable", "uid %d mode %o" % (uid, m), "A8"))
    else:
        res.append(Result(DONE, "allowlist root-owned, not group/other writable"))
    raw = sys_.read_bytes(ALLOWLIST)
    if raw is None:
        res.append(Result(UNKNOWN, "allowlist content", "not readable from this user", "A8"))
        return res
    try:
        data = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        res.append(Result(MISSING, "allowlist is valid JSON", "", "A8"))
        return res
    problems = []
    if data.get("contract") != CONTRACT:
        problems.append("contract is not " + CONTRACT)
    text = raw.decode("utf-8")
    if "<" in text and ">" in text:
        problems.append("still has <placeholders>")
    projects = sorted((data.get("projects") or {}).keys())
    if not projects:
        problems.append("no projects")
    if problems:
        res.append(Result(MISSING, "allowlist filled in", "; ".join(problems), "A8"))
    else:
        res.append(Result(DONE, "allowlist filled in", "projects: " + ", ".join(projects) +
                          "; simulators %s, device install %s" % (data.get("simulatorAllowed"), data.get("installAllowed"))))
    res.append(Result(INFO, "full allowlist check", "the runner checks every field when it starts; see runner health"))
    return res


def check_agent_loaded(sys_: System, me: str) -> Result:
    uid = sys_.uid_of(BUILD_USER)
    if uid is None:
        return Result(MISSING, "runner agent loaded for jorah-build", "no such user", "A11")
    if me != BUILD_USER:
        return Result(UNKNOWN, "runner agent loaded for jorah-build", "only visible as jorah-build; health below tells", "A11")
    code, out = sys_.run(["/bin/launchctl", "print", "gui/%d/%s" % (uid, AGENT_LABEL)])
    if code is None:
        return Result(UNKNOWN, "runner agent loaded for jorah-build", "launchctl did not answer", "A11")
    if code != 0:
        return Result(MISSING, "runner agent loaded for jorah-build", "not loaded in this login session", "A11")
    running = "state = running" in out
    return Result(DONE if running else MISSING, "runner agent loaded for jorah-build",
                  "running" if running else "loaded, not running", "" if running else "A11")


def check_health(sys_: System) -> Result:
    code, body = sys_.http_get(HEALTH_URL)
    if code is None:
        return Result(MISSING, "runner answers on 127.0.0.1:%d" % PORT, "nothing listening", "A11")
    try:
        data = json.loads(body)
    except ValueError:
        data = {}
    if code == 200 and data.get("contract") == CONTRACT:
        return Result(DONE, "runner answers on 127.0.0.1:%d" % PORT,
                      "runner %s, busy %s" % (data.get("runner_version"), data.get("busy")))
    return Result(MISSING, "runner answers on 127.0.0.1:%d" % PORT, "HTTP %s, not %s" % (code, CONTRACT), "A11")


def check_signing(sys_: System, me: str, home: Optional[str]) -> List[Result]:
    if me != BUILD_USER:
        return [Result(UNKNOWN, "one Apple Development identity in jorah-build's keychain",
                       "only visible as jorah-build", "A4"),
                Result(UNKNOWN, "no distribution identity in jorah-build's keychain", "only visible as jorah-build", "A4")]
    res = []
    code, out = sys_.run(["/usr/bin/security", "find-identity", "-v", "-p", "codesigning"])
    if code is None:
        res.append(Result(UNKNOWN, "one Apple Development identity in jorah-build's keychain", "security did not answer", "A4"))
    else:
        dev = sum(1 for line in out.splitlines() if '"Apple Development:' in line)
        res.append(Result(DONE if dev == 1 else MISSING, "one Apple Development identity in jorah-build's keychain",
                          "%d found" % dev, "" if dev == 1 else "A4"))
    # Without -v: also expired or untrusted ones. Names only, never the key.
    code, out = sys_.run(["/usr/bin/security", "find-identity", "-p", "codesigning"])
    if code is None:
        res.append(Result(UNKNOWN, "no distribution identity in jorah-build's keychain", "", "A4"))
    else:
        bad = [w for w in ("Apple Distribution", "iPhone Distribution", "Developer ID") if w in out]
        res.append(Result(MISSING if bad else DONE, "no distribution identity in jorah-build's keychain",
                          ("found: " + ", ".join(bad) + ". Delete it from this keychain") if bad else "", "A4" if bad else ""))
    if home:
        code, out = sys_.run(["/usr/bin/security", "show-keychain-info", home + "/Library/Keychains/login.keychain-db"])
        if code is None:
            res.append(Result(UNKNOWN, "login keychain does not auto-lock", "", "A4"))
        else:
            ok = "no-timeout" in out and "lock-on-sleep" not in out
            res.append(Result(DONE if ok else MISSING, "login keychain does not auto-lock", out.strip()[-80:] if not ok else "",
                              "" if ok else "A4"))
        listing = sys_.listdir(os.path.join(home, PROFILES_REL))
        if listing is None or listing == "denied":
            res.append(Result(MISSING, "provisioning profiles installed", "folder absent", "A5"))
        else:
            n = len([f for f in listing if f.endswith(".mobileprovision")])
            res.append(Result(DONE if n >= 4 else MISSING, "provisioning profiles installed",
                              "%d .mobileprovision (4 expected)" % n, "" if n >= 4 else "A5"))
    return res


def check_key(sys_: System, me: str, home: Optional[str]) -> Result:
    what = "runner key file present, private (content never read)"
    if not home:
        return Result(MISSING, what, "no jorah-build home", "A10")
    st = sys_.stat(os.path.join(home, KEY_REL))
    if st == "denied" or (st is None and me != BUILD_USER):
        return Result(UNKNOWN, what, "only visible as jorah-build", "A10")
    if st is None:
        return Result(MISSING, what, "", "A10")
    uid, _, m = owner_mode(st)
    ok = uid == sys_.uid_of(BUILD_USER) and m == 0o600 and st.st_size == 32
    return Result(DONE if ok else MISSING, what,
                  "" if ok else "uid %d mode %o size %d; want jorah-build, 600, 32 bytes" % (uid, m, st.st_size),
                  "" if ok else "A10")


def _devices(sys_: System, tmpdir: str) -> Optional[list]:
    path = os.path.join(tmpdir, "jorah-preflight-devices-%d.json" % os.getpid())
    code, _ = sys_.run(["/usr/bin/xcrun", "devicectl", "list", "devices", "--quiet", "--json-output", path], timeout=60)
    raw = sys_.read_bytes(path)
    try:
        os.unlink(path)
    except OSError:
        pass
    if code is None or raw is None:
        return None
    try:
        return json.loads(raw.decode("utf-8"))["result"]["devices"]
    except (ValueError, KeyError, TypeError, UnicodeDecodeError):
        return None


def check_iphone(sys_: System, me: str, tmpdir: str) -> List[Result]:
    devices = _devices(sys_, tmpdir)
    if devices is None:
        return [Result(UNKNOWN, "iPhone visible to devicectl for %s" % me, "devicectl gave no result", "A6")]
    phones = []
    for d in devices:
        hw = d.get("hardwareProperties") or {}
        if hw.get("reality") != "physical" or hw.get("deviceType") not in (None, "iPhone"):
            continue
        cp = d.get("connectionProperties") or {}
        dp = d.get("deviceProperties") or {}
        phones.append((dp.get("name") or "?", cp.get("pairingState"), cp.get("tunnelState"),
                       cp.get("transportType"), dp.get("developerModeStatus")))
    paired = [p for p in phones if p[1] == "paired"]
    res = []
    who = "for %s" % me
    if paired:
        p = paired[0]
        res.append(Result(DONE, "iPhone paired %s" % who, "transport %s, tunnel %s" % (p[3], p[2])))
        res.append(Result(DONE if p[4] == "enabled" else MISSING, "Developer Mode on", str(p[4]), "" if p[4] == "enabled" else "A6"))
    else:
        res.append(Result(MISSING, "iPhone paired %s" % who, "%d physical iPhone(s) listed" % len(phones), "A6"))
    if me != BUILD_USER:
        res.append(Result(UNKNOWN, "iPhone paired for jorah-build", "run this as jorah-build", "A6"))
    return res


def check_tailscale(sys_: System) -> Result:
    what = "Tailscale Serve forwards tailnet TCP %d to loopback" % PORT
    cli = None
    for c in ("/usr/local/bin/tailscale", "/Applications/Tailscale.app/Contents/MacOS/Tailscale",
              "/opt/homebrew/bin/tailscale"):
        if sys_.stat(c) not in (None, "denied"):
            cli = c
            break
    if not cli:
        return Result(UNKNOWN, what, "tailscale CLI not found", "A13")
    code, out = sys_.run([cli, "serve", "status", "--json"])
    if code != 0:
        return Result(UNKNOWN, what, "tailscale serve status failed", "A13")
    try:
        data = json.loads(out or "{}")
    except ValueError:
        return Result(UNKNOWN, what, "unreadable serve status", "A13")
    tcp = (data.get("TCP") or {}).get(str(PORT)) or {}
    target = tcp.get("TCPForward", "")
    if target in ("127.0.0.1:%d" % PORT, "localhost:%d" % PORT):
        return Result(DONE, what)
    return Result(MISSING, what, "no TCP %d entry" % PORT if not tcp else "forwards to " + target, "A13")


def check_xcode(sys_: System) -> List[Result]:
    res = []
    code, out = sys_.run(["/usr/bin/xcodebuild", "-version"])
    if code == 0:
        res.append(Result(DONE, "Xcode present", " ".join(out.split()[:2])))
    else:
        res.append(Result(MISSING if code is not None else UNKNOWN, "Xcode present", "", "A3"))
    code, _ = sys_.run(["/usr/bin/xcodebuild", "-checkFirstLaunchStatus"])
    res.append(Result({0: DONE, None: UNKNOWN}.get(code, MISSING), "Xcode first-launch packages installed", "",
                      "" if code == 0 else "A3"))
    code, out = sys_.run(["/usr/bin/xcrun", "simctl", "list", "--json", "runtimes"], timeout=60)
    try:
        runtimes = [r for r in json.loads(out)["runtimes"] if r.get("platform") == "iOS" and r.get("isAvailable")]
    except (ValueError, KeyError, TypeError):
        runtimes = None
    if runtimes is None:
        res.append(Result(UNKNOWN, "iOS simulator runtimes", "simctl gave no result", "A3"))
    else:
        res.append(Result(DONE if runtimes else MISSING, "iOS simulator runtimes",
                          ", ".join(r.get("version", "?") for r in runtimes), "" if runtimes else "A3"))
    code, out = sys_.run(["/usr/bin/xcrun", "simctl", "list", "--json", "devices", "available"], timeout=60)
    try:
        n = sum(len(v) for k, v in json.loads(out)["devices"].items() if "iOS" in k)
    except (ValueError, KeyError, TypeError, AttributeError):
        n = None
    if n is None:
        res.append(Result(UNKNOWN, "iOS simulators for this user", "", "A3"))
    else:
        res.append(Result(DONE if n else MISSING, "iOS simulators for this user", "%d available" % n, "" if n else "A3"))
    return res


def collect(sys_: System, tmpdir: str = "/tmp") -> List[Tuple[str, List[Result]]]:
    me = sys_.user()
    adam = None if me == BUILD_USER else me
    home = sys_.home_of(BUILD_USER)
    return [
        ("Account (A2)", check_user(sys_) + check_group(sys_, adam)),
        ("Folders (A2)", check_dirs(sys_)),
        ("Signing (A4, A5)", check_signing(sys_, me, home)),
        ("iPhone (A6)", check_iphone(sys_, me, tmpdir)),
        ("Allowlist (A8)", check_allowlist(sys_)),
        ("Runner (A9 to A11)", check_runner_install(sys_) + [check_agent_loaded(sys_, me), check_health(sys_)]),
        ("Runner key (A10)", [check_key(sys_, me, home)]),
        ("Tailnet (A13)", [check_tailscale(sys_)]),
        ("Xcode and simulators (A3)", check_xcode(sys_)),
    ]


def render(sections, me: str, write: Callable[[str], None]) -> int:
    write("Jorah iOS preflight, as %s. Read-only. Steps: docs/runbooks/ios-builds.md, \"Adam's steps\".\n" % me)
    counts = {DONE: 0, MISSING: 0, UNKNOWN: 0, INFO: 0}
    for title, results in sections:
        write("\n%s\n" % title)
        for r in results:
            counts[r.status] += 1
            line = "  %-8s %s" % (r.status, r.what)
            if r.detail:
                line += "  (%s)" % r.detail
            if r.fix and r.status != DONE:
                line += "  -> step %s" % r.fix
            write(line + "\n")
    write("\n%d done, %d missing, %d unknown.\n" % (counts[DONE], counts[MISSING], counts[UNKNOWN]))
    if counts[MISSING]:
        return 1
    return 3 if counts[UNKNOWN] else 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv:
        sys.stdout.write(__doc__ or "")
        return 0 if argv[0] in ("-h", "--help") else 2
    sys_ = System()
    return render(collect(sys_, os.environ.get("TMPDIR", "/tmp")), sys_.user(), sys.stdout.write)


if __name__ == "__main__":
    sys.exit(main())
