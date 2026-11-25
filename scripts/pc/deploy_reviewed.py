#!/usr/bin/env python3
"""Deploys reviewed files from main to the PC and records them for the nightly drift check.

Runs on the Mac, in a checkout whose HEAD is on origin/main. It replaces the hand-typed
`git archive | ssh ... tar -x` of CLAUDE.md's deploy step, and does the SHA-256 comparison with main
that build sessions did by hand, so the manifest on the PC stays current with every deploy.

  deploy PATH...               git archive HEAD PATH... into /opt/jorah, `sync`, then record every
                               deployed file. Recording checks each file on the PC against git.
  record-live REPO=LIVE...     Record a rules file a build session copied into a live workspace, e.g.
                               workspace/AGENTS.md=/home/jorah/workspace/AGENTS.md. Copy it first,
                               with a backup, as before; this only checks and records it.
  forget PATH...               A file deleted from main: remove it from the manifest. Delete the
                               file on the PC yourself.
  baseline [--write]           First run: hash what is on the PC now and find, for each file, the
                               commit on origin/main it came from. Without --write it only prints.
                               Files that match no commit are never recorded: they are drift.

The hashes always come from git on the Mac, never from the PC. The PC refuses to record a file
whose content differs from them (drift.py record).
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys

SSH = ["ssh", "-i", os.path.expanduser("~/.ssh/jorah-pc-setup"), "-o", "IdentitiesOnly=yes",
       "adamh@100.115.240.14"]
TREE = "/opt/jorah"
DRIFT = ["/usr/bin/python3", "-I", f"{TREE}/services/jorah-watchdog/drift.py"]
# Repo rules files and where the agents' live copies are.
LIVE = {f"{d}/{n}": f"/home/jorah/{d}/{n}" for d in ("workspace", "workspace-deep", "workspace-background")
        for n in ("AGENTS.md", "SOUL.md", "IDENTITY.md")}
LIVE["workspace/DEEP.md"] = "/home/jorah/workspace/DEEP.md"  # deep's rules since 2026-11-25


def git(*args, input=None):
    return subprocess.run(["git", *args], check=True, capture_output=True, input=input).stdout


def on_pc(command, input=None):
    """Runs a command as root in the jorah distro. The command is a list; nothing is shell-built."""
    remote = "wsl -d jorah -u root -- " + " ".join(_quote(c) for c in command)
    return subprocess.run([*SSH, remote], input=input, capture_output=True, check=False)


def _quote(word):
    if word and all(c.isalnum() or c in "-_./=:@" for c in word):
        return word
    return "'" + word.replace("'", "'\\''") + "'"


def blobs(commit, paths):
    """{repo path: blob id} of regular files under the paths at the commit. Symlinks are skipped."""
    out = {}
    raw = git("ls-tree", "-r", "-z", commit, "--", *paths)
    for item in raw.split(b"\0"):
        if not item:
            continue
        meta, path = item.split(b"\t", 1)
        mode, kind, blob = meta.split()
        if kind == b"blob" and mode in (b"100644", b"100755"):
            out[path.decode()] = blob.decode()
    return out


def blob_sha256(blob_ids):
    """{blob id: sha256 of its content}, with one `git cat-file --batch`."""
    ids = list(dict.fromkeys(blob_ids))
    if not ids:
        return {}
    data = git("cat-file", "--batch", input=("\n".join(ids) + "\n").encode())
    out, pos = {}, 0
    for blob in ids:
        end = data.index(b"\n", pos)
        header = data[pos:end].split()
        size = int(header[2])
        content = data[end + 1:end + 1 + size]
        out[blob] = hashlib.sha256(content).hexdigest()
        pos = end + 1 + size + 1
    return out


def entries(commit, mapping):
    """{target path: {sha256, source}} for {repo path: target path} at the commit."""
    found = blobs(commit, sorted(mapping))
    missing = sorted(set(mapping) - set(found))
    if missing:
        raise SystemExit(f"not regular files at {commit[:12]}: {', '.join(missing)}")
    sums = blob_sha256(found.values())
    return {mapping[path]: {"sha256": sums[blob], "source": path} for path, blob in found.items()}


def require_main():
    git("fetch", "-q", "origin", "main")
    head = git("rev-parse", "HEAD").decode().strip()
    if subprocess.run(["git", "merge-base", "--is-ancestor", head, "origin/main"]).returncode != 0:
        raise SystemExit("HEAD isn't on origin/main: push first. Only reviewed files from main are deployed.")
    return head


def record(commit, files):
    result = on_pc([*DRIFT, "record"], input=json.dumps({"commit": commit, "files": files}).encode())
    sys.stdout.write(result.stdout.decode())
    sys.stderr.write(result.stderr.decode())
    if result.returncode != 0:
        raise SystemExit("the PC refused to record (see above): nothing was recorded")


def deploy(paths):
    head = require_main()
    files = blobs(head, paths)
    if not files:
        raise SystemExit("nothing to deploy")
    archive = subprocess.run(["git", "-c", "tar.umask=022", "archive", head, "--", *paths],
                             check=True, capture_output=True).stdout
    result = on_pc(["tar", "-x", "--no-same-permissions", "-C", TREE], input=archive)
    if result.returncode != 0:
        raise SystemExit(f"tar on the PC failed: {result.stderr.decode()[-500:]}")
    on_pc(["sync"])
    print(f"deployed {len(files)} file(s) from {head[:12]}")
    record(head, entries(head, {p: f"{TREE}/{p}" for p in files}))
    on_pc(["sync"])


def record_live(pairs):
    head = require_main()
    mapping = {}
    for pair in pairs:
        repo, _, live = pair.partition("=")
        if not live:
            raise SystemExit(f"expected REPO=LIVE, got {pair}")
        mapping[repo] = live
    record(head, entries(head, mapping))
    on_pc(["sync"])


def history_match(path, sha, commits_for, sha_at):
    """The newest commit whose version of path has this sha256, or None."""
    for commit in commits_for(path):
        if sha_at(commit, path) == sha:
            return commit
    return None


def baseline(write):
    head = require_main()
    live = {target: repo for repo, target in LIVE.items()}
    result = on_pc([*DRIFT, "hashes", TREE, *sorted(live)])
    if result.returncode != 0:
        raise SystemExit(f"couldn't hash on the PC: {result.stderr.decode()[-500:]}")
    on_disk = json.loads(result.stdout)
    cache = {}

    def commits_for(path):
        out = git("log", "--format=%H", "origin/main", "--", path).decode().split()
        return out

    def sha_at(commit, path):
        key = (commit, path)
        if key not in cache:
            found = blobs(commit, [path]).get(path)
            cache[key] = blob_sha256([found])[found] if found else None
        return cache[key]

    by_commit, unmatched, refused, untracked, current = {}, [], [], [], 0
    for target, sha in sorted(on_disk.items()):
        if sha == "refused":
            refused.append(target)
            continue
        if sha is None:
            continue
        repo = live.get(target) or os.path.relpath(target, TREE)
        if not commits_for(repo):
            untracked.append(target)
            continue
        commit = history_match(repo, sha, commits_for, sha_at)
        current += commit is not None and commit == commits_for(repo)[0]
        if commit is None:
            unmatched.append(target)
        else:
            by_commit.setdefault(commit, {})[target] = {"sha256": sha, "source": repo}
    matched = sum(len(v) for v in by_commit.values())
    print(f"match a version on main: {matched} ({current} the newest, {matched - current} an older one; "
          f"main is {head[:7]})")
    for label, items in (("MATCHES NO COMMIT (drift, not recorded)", unmatched),
                         ("not in git (not recorded)", untracked), ("secret names, not read", refused)):
        print(f"{label}: {len(items)}")
        for item in items:
            print(f"  {item}")
    if write:
        for commit, files in sorted(by_commit.items()):
            record(commit, files)
        on_pc(["sync"])


def main(argv=None):
    parser = argparse.ArgumentParser(prog="deploy_reviewed.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("deploy").add_argument("paths", nargs="+")
    sub.add_parser("record-live").add_argument("pairs", nargs="+")
    sub.add_parser("forget").add_argument("paths", nargs="+")
    sub.add_parser("baseline").add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "deploy":
        deploy(args.paths)
    elif args.command == "record-live":
        record_live(args.pairs)
    elif args.command == "forget":
        result = on_pc([*DRIFT, "forget", *args.paths])
        sys.stdout.write(result.stdout.decode())
        on_pc(["sync"])
    else:
        baseline(args.write)
    return 0


if __name__ == "__main__":
    sys.exit(main())
