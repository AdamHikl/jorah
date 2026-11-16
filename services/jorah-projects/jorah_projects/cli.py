"""Command line: `jorah-projects tick [--project NAME]` (the timer and path units) and `status`."""

import argparse
import json
import sys

from . import config, runner


def main(argv=None):
    parser = argparse.ArgumentParser(prog="jorah-projects", description="Jorah's project runner")
    sub = parser.add_subparsers(dest="command", required=True)
    tick = sub.add_parser("tick", help="run whatever is due: a scheduled slot or a run-now request")
    tick.add_argument("--project", help="only this project")
    sub.add_parser("status", help="registry, schemas, freeze and backoff, read only")
    args = parser.parse_args(argv)
    try:
        settings = config.load_runner_file(config.Settings())
    except (config.ConfigError, OSError, ValueError) as error:
        print(f"runner.json: {error}", file=sys.stderr)
        return 2
    if args.command == "status":
        print(json.dumps(runner.status(settings), indent=2, ensure_ascii=False))
        return 0
    records = runner.Runner(settings).tick(only=args.project)
    # A second pass picks up a request that arrived while this tick ran (the path unit can't start
    # the service again while it is active).
    if any(r.get("outcome") != "skipped" for r in records):
        records += runner.Runner(settings).tick(only=args.project)
    return 0
