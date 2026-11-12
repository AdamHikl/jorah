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

# Mac only, needs Xcode. A real build-sim of the fixture app through the runner's HTTP front end
# on loopback, as the current user, with state in a new temp folder.
ios-runner-sample:
    python3 services/ios-runner/tools/sample_over_http.py

# The same, then boot, install, launch, screenshot and shut down on a real iOS Simulator
ios-runner-sample-sim:
    python3 services/ios-runner/tools/sample_over_http.py --simulator

# Mac only, needs Xcode and a shut-down iPhone simulator. plugins/jorah-ios against the real runner
# on loopback, outside the Gateway: build, simulator steps, refusals, wrong key, runner stopped.
ios-e2e-local:
    node plugins/jorah-ios/e2e/loopback.mjs
