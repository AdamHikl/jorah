# M0 scope. Lint, types and unit are added by the first issue that adds code.
check: secrets planted guards shellcheck licenses supply-chain
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
    shellcheck scripts/*.sh

licenses:
    scripts/check-licenses.sh

supply-chain:
    scripts/check-supply-chain.sh
