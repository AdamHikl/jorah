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
    python3 -m unittest discover -s services/jorah-phone/tests
    python3 -m unittest discover -s services/jorah-projects/tests
    python3 -m unittest discover -s services/ios-runner/tests
    python3 -m unittest discover -s scripts/mac/tests
    python3 -m unittest discover -s packages/contracts/project/tests
    python3 -m unittest discover -s packages/contracts/toolbox/tests
    python3 -m unittest discover -s services/jorah-toolbox/tests
    python3 -m unittest discover -s services/jorah-watchdog/tests
    python3 -m unittest discover -s scripts/pc/tests
    node --test plugins/jorah-voice-provider/test/ plugins/jorah-github/test/ plugins/jorah-ios/test/ plugins/jorah-guard-spike/test/ plugins/jorah-guard/test/ plugins/jorah-sites/test/ plugins/jorah-phone/test/ plugins/jorah-google/test/ plugins/jorah-proactive/test/ services/jorah-site-proxy/test/
    node --test plugins/jorah-projects/test/
    node --test plugins/jorah-errands/test/

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

# Mac only. Builds the Jorah HUD app into build/JorahHUD.app. It is signed with the first
# "Apple Development" certificate in the Keychain (or JORAH_SIGN_ID, a fingerprint), so macOS
# keeps its Microphone and Speech Recognition permissions across rebuilds. With no certificate
# it falls back to ad hoc, and macOS asks for them again after every build.
mac-hud:
    swift build -c release --package-path clients/mac-hud --scratch-path build/mac-hud-spm
    rm -rf build/JorahHUD.app
    mkdir -p build/JorahHUD.app/Contents/MacOS
    cp clients/mac-hud/Info.plist build/JorahHUD.app/Contents/Info.plist
    cp build/mac-hud-spm/release/JorahHUD build/JorahHUD.app/Contents/MacOS/JorahHUD
    mkdir -p build/JorahHUD.app/Contents/Resources
    cp scripts/pc/jorah-power.sh build/JorahHUD.app/Contents/Resources/jorah-power.sh
    cp scripts/pc/jorah-brain.sh build/JorahHUD.app/Contents/Resources/jorah-brain.sh
    id="${JORAH_SIGN_ID:-$(security find-identity -v -p codesigning | awk '/"Apple Development/ {print $2; exit}')}"; \
      if [ -n "$id" ]; then codesign --force --sign "$id" build/JorahHUD.app; else echo "No Apple Development certificate: signing ad hoc"; codesign --force --sign - build/JorahHUD.app; fi
    codesign -d -r- build/JorahHUD.app 2>&1 | tail -1

# Mac only. Opens the HUD with made-up data and no connection, to look at the layout.
mac-hud-demo: mac-hud
    JORAH_HUD_DEMO=1 build/JorahHUD.app/Contents/MacOS/JorahHUD

# Mac only. Copies the HUD to ~/Applications as "Jorah HUD", so Spotlight and Launchpad find it.
# Run it again after each build: the installed copy does not update by itself.
mac-hud-install: mac-hud
    rm -rf "$HOME/Applications/Jorah HUD.app"
    ditto build/JorahHUD.app "$HOME/Applications/Jorah HUD.app"
