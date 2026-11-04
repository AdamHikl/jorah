# Stage 0 rollback

Use this if stage 0 breaks Jorah or its gate fails. **Then stop: do not start the PC work with the shell open.** Adam decides what happens next, and any override is written down as a waived gate.

Rollback puts the shell, the fallback chain and web back, so Jorah is less safe afterwards. It doesn't undo a token rotation.

**Run the secret steps in a separate Terminal app attached to no agent.** Never print `openclaw.json`.

## Before you start

You need the archive from step 0.15, in `~/.openclaw-jorah/backups/stage0/`. It holds the old config, including the old Telegram token in plaintext, so treat it as a secret.

## Steps

1. **Stop the Gateway.** Press Ctrl-C in its terminal. Check nothing is listening:

   ```bash
   lsof -nP -iTCP:43181 -sTCP:LISTEN
   ```

   Expected: no output.

2. **Extract the archive into a new empty folder.** This activates nothing:

   ```bash
   R="$(mktemp -d)"; openclaw --profile jorah backup restore ~/.openclaw-jorah/backups/stage0/<archive> --target "$R"
   ```

3. **Find the config in it, by name only:**

   ```bash
   find "$R" -name openclaw.json
   ```

4. **Keep a copy of the broken config, then copy the old one back:**

   ```bash
   cp -p ~/.openclaw-jorah/openclaw.json ~/.openclaw-jorah/openclaw.json.stage0-failed
   ```
   ```bash
   cp -p "<path from step 3>" ~/.openclaw-jorah/openclaw.json
   ```

5. **Sort out the Telegram token.** Which case applies depends on how far stage 0 got:

   | Did you rotate at BotFather? | What to do |
   |---|---|
   | No | The restored config's token still works. Go to step 6 |
   | Yes | The restored token is dead. Enter the **new** token at the masked prompt below. Keep the Keychain item too |

   ```bash
   openclaw --profile jorah configure
   ```

6. **Start the Gateway in the foreground,** with the command in the root `README.md`.

7. **Check it works:**
   - In Telegram, send Jorah `Hello`. Expected: a reply.
   - Run the command below. Expected: the fallback chain is back, because that's what the old config held.

   ```bash
   openclaw --profile jorah config get agents.entries.main.model --json
   ```

8. **Delete the extracted copy,** because it holds the old token. Move it to the Trash, and keep the archive.

## Afterwards

- Record what failed in `docs/evidence/security/`, without secrets.
- Remove the copy from step 4 once you've noted what was wrong, because it may hold references you no longer use.
- Tell the next session that stage 0 isn't in place. No private connector, and no move to the PC gate, until it is.

**Dry-run result:** see `docs/evidence/m0/m0-c1-2026-11-04.md`. That run was on `jorah-dev` with channels skipped, so it didn't test Telegram or a real rotation.
