"""Entry point.

  jorah-ios-runner serve                  HTTP front end on the allowlist's loopback port
  jorah-ios-runner call <verb> [<json>]   one verb, same checks, no HTTP; builds wait to finish
  jorah-ios-runner health

The allowlist path comes from $JORAH_IOS_RUNNER_CONFIG, default
~/.config/jorah-ios-runner/projects.json. Nothing else is read from the caller.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import threading
from pathlib import Path

from .auth import Verifier, read_key
from .config import ConfigError, load_config
from .core import Runner, envelope, error_dict
from .server import VERBS, Server


def config_path() -> Path:
    return Path(os.environ.get("JORAH_IOS_RUNNER_CONFIG",
                               os.path.expanduser("~/.config/jorah-ios-runner/projects.json")))


def emit(obj, code):
    print(json.dumps(obj, sort_keys=True))
    return code


def serve(config) -> int:
    runner = Runner(config, background=True)
    runner.mark_stale()
    if read_key(config.key_file) is None:
        sys.stderr.write("warning: the key file is missing or not private (mode 600, this user); "
                         "every signed request will get 401 until it is fixed\n")
    server = Server(runner, Verifier(config.key_file))

    def stop(signum, frame):
        runner.cancel_all()
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    host, port = server.server_address[:2]
    sys.stderr.write(f"jorah-ios-runner listening on {host}:{port}\n")
    sys.stderr.flush()
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] not in ("serve", "call", "health"):
        return emit(envelope(False, error_dict("BAD_ARGUMENT", "Use: serve | call <verb> [<json>] | health")), 2)
    try:
        config = load_config(config_path())
    except ConfigError as e:
        return emit(envelope(False, error_dict("RUNNER_ERROR", f"Allowlist: {e}")), 2)
    if argv[0] == "serve":
        if len(argv) != 1:
            return emit(envelope(False, error_dict("BAD_ARGUMENT", "serve takes no arguments")), 2)
        return serve(config)
    runner = Runner(config, background=False)
    if argv[0] == "health":
        return emit(runner.health(), 0)
    if len(argv) not in (2, 3) or argv[1] not in VERBS:
        return emit(envelope(False, error_dict("BAD_ARGUMENT", "Unknown verb.")), 2)
    try:
        body = json.loads(argv[2]) if len(argv) == 3 else {}
    except ValueError:
        return emit(envelope(False, error_dict("BAD_ARGUMENT", "The body is not JSON.")), 2)
    result = runner.dispatch(argv[1], body)
    return emit(result, 0 if result["ok"] else 1)
