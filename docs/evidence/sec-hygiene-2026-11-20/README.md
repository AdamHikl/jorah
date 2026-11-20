# Advisory watch, drift check, install policy: PC install, 2026-11-20

Tier reached: install and run on the PC (source and tests were 9a9532e, 2069279, 74d581c).
Not reached: Adam confirming the Telegram message arrived; the live install policy (step 4).
Commands ran as root in the `jorah` distro over the setup key. Output trimmed; nothing secret was read.

## Deploy (deploy_reviewed.py)

    deployed 20 file(s) from 9260a08bea19
    recorded 20 file(s) from 9260a08bea19
    deployed 2 file(s) from 74d581ccf950      (range fix)
    recorded 2 file(s) from 74d581ccf950

## Leftovers archived, then removed

    opt/jorah/.deployed-commit
    opt/jorah/.commit-site-readers
    opt/jorah/config/pc/max-lane.patch.json5.pre-2026-11-16
    opt/jorah/scripts/pc/._setup-permissions.sh
    -rw------- 1 root root 786 Nov 20 13:45 /root/opt-jorah-leftovers-2026-11-20.tgz
    removed 4, archive verified

## Baseline

    match a version on main: 588 (558 the newest, 30 an older one; main is 9260a08)
    MATCHES NO COMMIT (drift, not recorded): 0
    not in git (not recorded): 0
    secret names, not read: 0
    (--write: 40 commits recorded)
    checked 588 files: 0 changed, 0 missing, 0 unrecorded
    packages: @openclaw/acpx 2026.10.9, @openclaw/duckduckgo-plugin 2026.10.9,
              @openclaw/fs-safe 0.26.0, @openclaw/fs-safe-linux-x64-gnu 0.26.0

## Daily watch

First dry run (before 74d581c): "30 OpenClaw advisories match"; 29 were npm space or `||`
ranges the parser couldn't read (e.g. `>=2026.1.14-1 <2026.2.12`), all ending before
2026.10.9. After the fix, run against the live list as jorah-watchdog:

    723 advisories, 719 ranges, 0 unreadable
    HIT GHSA-pw3x-g8v8-fvj2 [('openclaw', '>= 2026.9.2, < 2026.10.33', True)]

Install and run:

    NEXT                        LEFT UNIT
    Sat 2026-11-21 03:40:55 CET  13h jorah-daily-watch.timer
    checked 588 files: 0 changed, 0 missing, 0 unrecorded
    advisories: 723 known; checked against ... openclaw 2026.10.9; 0 told so far
    sent: advisory GHSA-pw3x-g8v8-fvj2

The message sent:

    OpenClaw security advisory GHSA-pw3x-g8v8-fvj2 (high) affects what Jorah runs: openclaw 2026.10.9.
    OpenClaw delegation could skip approval for restricted agents
    Fixed in: 2026.10.33, 2026.11.4.
    https://github.com/openclaw/openclaw/security/advisories/GHSA-pw3x-g8v8-fvj2

No repeat (dry run with the real state afterwards):

    advisories: 723 known; ...; 1 told so far
    0 message(s) due; dry run, nothing sent or saved

## Install policy (files and scratch test only; live config untouched)

    wrote /etc/jorah/install-allowlist.json (empty)
    policy says: {"protocolVersion": 1, "decision": "block", "reason": "Jorah's install policy blocks plugin 'jorah-probe' (local-path): not on /etc/jorah/install-allowlist.json. ..."}
    scratch policy enabled: true
    --- linked plugin install (must be blocked)
    Install blocked by policy   Plugin: jorah-errands
    --- local skill install (must be blocked)
    Install blocked by policy   Skill: policy-probe
    --- doctor --deep: Install policy enabled for: skill, plugin; the deep check reached the
        policy command and the policy blocked the synthetic request
    scratch test: both installs blocked

Afterwards: no /home/jorah/.openclaw-policy-scratch, no probe folder; on the live profile
`security.installPolicy.enabled` is still unset (dry-run validation only: "8 update(s) validated").
