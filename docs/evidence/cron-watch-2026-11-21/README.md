# Cron watch: PC install, 2026-11-21

Tier reached: install and timer-driven run on the PC, with cron healthy (source and tests were
5e41e21 and fb5ba77). Not reached: a real cron outage alert on Telegram (unit tests cover it).
On Adam's yes ("Yes, deploy it"). Commands ran as root in the `jorah` distro over the setup key.
Output trimmed. Nothing secret was read, and the Gateway was neither touched nor restarted.

## Deploy (deploy_reviewed.py)

    deployed 12 file(s) from 5e41e21efd71
    recorded 12 file(s) from 5e41e21efd71
    deployed 2 file(s) from fb5ba777cd2a      (the Gateway's wall-clock start in messages)
    recorded 2 file(s) from fb5ba777cd2a

## Dry run (install-cron-watch.sh --dry-run)

    units verify clean
    --- how jorah-watchdog.service changes:
    -After=network-online.target
    -Wants=network-online.target
    +After=network-online.target jorah-cron-watch.service
    +Wants=network-online.target jorah-cron-watch.service
    (plus the comment and Description lines)
    --- the check, in a throwaway unit with 11 sandbox settings:
    cron: ok: newest heartbeat: heartbeat-deep at 07:46; no cron error in the journal since the Gateway started at 07:43
      "heartbeats": heartbeat-main 07:46:28 ok, heartbeat-background 07:46:39 ok, heartbeat-deep 07:46:43 ok
      "journal": null, "errors": {}, "gateway": {"since": 1795243438.0 (07:43:58), ...}
    --- the watchdog's check on that report, as jorah-watchdog, dry run:
    checks: gateway ok, runner ok, cron ok
    0 message(s) due; dry run, nothing sent or saved

The first dry run, from 5e41e21, said "started at 07:44": the uptime comes from the monotonic clock,
which ran about 3 % slow (1,667 s against about 1,716 s). fb5ba77 shows systemd's
`ActiveEnterTimestamp` instead.

## Install (install-cron-watch.sh)

    cron: ok: newest heartbeat: heartbeat-deep at 07:46; no cron error in the journal since the Gateway started at 07:43
    Finished jorah-cron-watch.service - Jorah: cron watch, does the Gateway's scheduler still run jobs.

    SHA-256, /etc/systemd/system = /opt/jorah/deploy = git (fb5ba77):
    56cb6cf6c05f4d70bbe73ee0dfc03e5ef7898acc1788182a475a80a23dfd7440  jorah-cron-watch.service
    7983b03733cf2e96125aadf02e18abe2f9ae3d1e74b6b5da18117ad917b29389  jorah-watchdog.service
    systemctl show jorah-watchdog.service: Wants= and After= list jorah-cron-watch.service
    /var/lib/jorah-cron-watch/report.json  root 644

## First timer-driven run (jorah-watchdog.timer)

    08:18:50 python3: cron: ok: newest heartbeat: heartbeat-deep at 07:46; no cron error in the journal since the Gateway started at 07:43
    08:18:50 systemd: Finished jorah-cron-watch.service
    08:18:50 python3: checks: gateway ok, runner ok, cron ok
    08:18:50 systemd: Finished jorah-watchdog.service

## Across the 08:20 Gateway restart (jorah-gateway-recycle)

    08:20:05 gateway-recycle.sh: try 1: idle, restarting openclaw-gateway.service
    08:20:34 gateway-recycle.sh: ready after 25 s
    ActiveEnterTimestamp=@1795245607 (08:20:07), a new InvocationID
    08:24:06 python3: cron: ok: newest heartbeat: heartbeat-deep at 07:46; no cron error in the journal since the Gateway started at 08:20
    08:24:06 python3: checks: gateway ok, runner ok, cron ok

The journal search followed the new start. Nothing was sent.
