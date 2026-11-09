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
    shellcheck scripts/*.sh scripts/pc/*.sh scripts/github/*.sh

licenses:
    scripts/check-licenses.sh

supply-chain:
    scripts/check-supply-chain.sh

# Needs no install, model or network.
unit:
    python3 -m unittest discover -s services/jorah-voice/tests
    node --test plugins/jorah-voice-provider/test/ plugins/jorah-github/test/

# Mac only. Builds the mic and speaker client, and checks it against a stand-in server.
mac-ear:
    mkdir -p build
    swiftc -O -swift-version 5 -Xlinker -sectcreate -Xlinker __TEXT -Xlinker __info_plist -Xlinker clients/mac-ear/Info.plist clients/mac-ear/main.swift -o build/mac-ear
    build/mac-ear --self-test-wake
    python3 clients/mac-ear/test_fake_server.py build/mac-ear
