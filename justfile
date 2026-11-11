# M0 scope. Lint, types and unit are added by the first issue that adds code.
check: secrets planted guards shellcheck licenses supply-chain unit
ci: check

# Commits, then uncommitted and staged changes, so a token fails before it's committed.
secrets:
    gitleaks git . --config .gitleaks.toml --redact --no-banner --log-level warn
    gitleaks git . --pre-commit --config .gitleaks.toml --redact --no-banner --log-level warn
    gitleaks git . --staged --config .gitleaks.toml --redact --no-banner --log-level warn

planted:
    scripts/test-planted-secret.sh

guards:
    scripts/test-guards.sh

shellcheck:
    shellcheck scripts/*.sh scripts/pc/*.sh scripts/github/*.sh scripts/mac/*.sh

licenses:
    scripts/check-licenses.sh

supply-chain:
    scripts/check-supply-chain.sh

# Needs no install, model or network.
unit:
    python3 -m unittest discover -s services/jorah-voice/tests
    python3 -m unittest discover -s services/ios-runner/tests
    node --test plugins/jorah-voice-provider/test/ plugins/jorah-github/test/ plugins/jorah-ios/test/ plugins/jorah-guard-spike/test/ plugins/jorah-guard/test/

# Mac only. Builds the mic and speaker client, and checks it against a stand-in server.
mac-ear:
    mkdir -p build
    swiftc -O -swift-version 5 -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker clients/mac-ear/Info.plist clients/mac-ear/main.swift -o build/mac-ear
    build/mac-ear --self-test-wake
    python3 clients/mac-ear/test_fake_server.py build/mac-ear

# Mac only, needs Xcode. A real build-sim of the fixture app, as the current user, with state in a temp folder.
ios-runner-sample:
    #!/usr/bin/env bash
    set -euo pipefail
    dir="$(mktemp -d -t jorah-ios-runner)"
    python3 - "$dir" "$PWD/services/ios-runner/tests/fixtures/Sample" <<'PY'
    import json, os, sys
    state, fixture = sys.argv[1:]
    config = {"schema": 1, "state_dir": state + "/state", "handoff_dir": state + "/handoff",
              "path": ["/usr/bin", "/bin", "/usr/sbin", "/sbin"],
              "projects": {"sample": {"path": fixture, "project": "Sample.xcodeproj", "scheme": "Sample",
                                      "configuration": "Debug", "bundle_id": "dev.jorah.fixture.sample"}}}
    with open(state + "/projects.json", "w") as f:
        json.dump(config, f)
    os.chmod(state + "/projects.json", 0o600)
    PY
    JORAH_IOS_RUNNER_CONFIG="$dir/projects.json" services/ios-runner/bin/jorah-ios-runner build-sim sample
