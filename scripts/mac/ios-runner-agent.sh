#!/bin/bash
# launchd wrapper for the Jorah iOS runner. Installed root-owned as
# /usr/local/libexec/jorah/ios-runner-agent by setup-jorah-build.sh --install-runner.
# Runs the runner's HTTP service only for jorah-build; any other user's login exits 0, so
# launchd leaves it stopped. Listens on 127.0.0.1:47820 (contract, "Network").
set -euo pipefail

[ "$(/usr/bin/id -un)" = "jorah-build" ] || exit 0

# The allowlist is admin-owned and outside the build user's reach (contract section 6).
export JORAH_IOS_RUNNER_CONFIG="/Library/Application Support/Jorah/ios-projects.json"
export PATH="/usr/bin:/bin:/usr/sbin:/sbin"
cd "$HOME"
# `serve` is issue 8's HTTP front end for the contract's verbs.
exec /usr/bin/python3 -I /usr/local/libexec/jorah/ios-runner/bin/jorah-ios-runner serve
