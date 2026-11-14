"""Print each recent agent run's timing and token use from OpenClaw's own records. No message text.

Run on the PC as jorah, read-only:
  python3 runs.py [hours]          (default: the last 48 hours)

Reads `trajectory_runtime_events` in every agent's database and prints, per run: when it started,
the agent, the channel (`webchat` is voice through the Chat Completions endpoint), and seconds from
the run's start to each prompt submission, model completion and the end, with the tokens each model
call read from cache, wrote to cache, and produced (thinking included).
"""

import datetime
import glob
import json
import os
import sqlite3
import sys
import time

KEEP = ("prompt.submitted", "model.completed", "session.ended")


def main():
    hours = float(sys.argv[1]) if len(sys.argv) > 1 else 48
    since = int((time.time() - hours * 3600) * 1000)
    runs = {}
    for path in glob.glob(os.path.expanduser("~/.openclaw-jorah/agents/*/agent/openclaw-agent.sqlite")):
        agent = path.split("/")[-3]
        db = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        rows = db.execute("select run_id, event_json, created_at from trajectory_runtime_events "
                          "where created_at > ? order by created_at", (since,))
        for run_id, event_json, created in rows:
            event = json.loads(event_json)
            data = event.get("data", {})
            run = runs.setdefault(run_id, {"agent": agent, "events": []})
            if event["type"] == "session.started":
                run["channel"] = data.get("messageProvider")
                run["trigger"] = data.get("trigger")
            note = ""
            if event["type"] == "model.completed":
                usage = data.get("usage", {})
                note = f" read={usage.get('cacheRead')} wrote={usage.get('cacheWrite')} new={usage.get('input')} out={usage.get('output')}"
            run["events"].append((created, event["type"], note))
    for run_id, run in sorted(runs.items(), key=lambda item: item[1]["events"][0][0]):
        start = run["events"][0][0]
        when = datetime.datetime.fromtimestamp(start / 1000).strftime("%m-%d %H:%M:%S.%f")[:-3]
        steps = " ".join(f"{kind.split('.')[0]}+{(at - start) / 1000:.2f}{note}"
                         for at, kind, note in run["events"] if kind in KEEP)
        print(f"{when} {run['agent']:<10} {str(run.get('channel')):<9} {str(run.get('trigger')):<9} {run_id[:17]:<17} {steps}")


if __name__ == "__main__":
    main()
