# Switching Jorah's brain: Claude login or API key

Jorah normally thinks through its own Claude Code login (`~/.claude-jorah`), on your subscription limits. `scripts/switch-brain.sh` moves it to an Anthropic API key and back. Nothing switches by itself: if a route fails, Jorah's requests fail.

## Check the route

```bash
./scripts/switch-brain.sh status
```

Expected on the normal route:

```text
  gateway reports:  anthropic/claude-opus-5-5 -> claude-cli
  auth.order:       []
  provider key ref: unset
ACTIVE ROUTE: cli (Claude Code login, subscription limits)
```

Any line starting `PROBLEM:` says what to run, and the exit code is 2. Add `--probe` to prove the route with one real test turn. It uses a little quota or credit and deletes its test session afterwards. A CLI probe shows `runner: cli`, an API probe shows `runner: embedded`, `harness: openclaw`, `credential: profile`.

## Save a key (once)

1. To use the monthly Max credits, link a Console organization: on claude.ai, go to **Settings > Billing > API credits**, select the organization and accept the terms. You can't change the link yourself afterwards, so choose carefully. The credits appear under **Promotional credits** on the [Console billing page](https://platform.claude.com/settings/billing).
2. In the [Console](https://platform.claude.com/), create an API key in that organization.
3. In your own terminal, run the command below and paste the key at its prompt. Never paste it into a chat, a file or an environment variable.

   ```bash
   openclaw --profile jorah models auth paste-api-key --provider anthropic
   ```

4. Saving a key unblocks it, so block it straight away. `status` shows a `PROBLEM:` line until you do.

   ```bash
   ./scripts/switch-brain.sh cli
   ```

## Switch to the API key

```bash
./scripts/switch-brain.sh api
./scripts/switch-brain.sh status --probe
```

Expected: `ACTIVE ROUTE: api`, `runner: embedded`, `reply: PROBE-OK`. With no key saved, `api` exits 3, changes nothing and prints the paste command.

## Switch back

```bash
./scripts/switch-brain.sh cli
./scripts/switch-brain.sh status --probe
```

Expected: `ACTIVE ROUTE: cli`, `runner: cli`, `reply: PROBE-OK`. Run this whenever you're done with the API. It works with or without a key, and running it twice is harmless.

## Remove the key

```bash
./scripts/switch-brain.sh cli
openclaw --profile jorah models auth logout anthropic:manual --yes
```

Also revoke the key in the Console if you won't use it again.

## Add `--dry-run` to preview

`cli --dry-run` and `api --dry-run` print each change and write nothing. Real switches back up the config first, to `~/.openclaw-jorah/backups/switch-brain/` (private, outside the repo), and restore the previous route if verification fails.

## What to expect

- **Billing:** an API key bills its own Console organization: the monthly plan credits if that organization is linked, then anything you've bought. Max includes $100 a month, which expires at the end of each cycle. When credits run out, requests stop unless you've bought more or turned on auto-reload. Jorah does not fall back to your login, and your plan is never charged.
- **After a billing error:** OpenClaw parks the key for about 10 minutes, and replies fail with `Provider anthropic is in cooldown (billing)`. Running `cli` brings Jorah back immediately. Going back to `api` during that time still fails, even after topping up.
- **Existing chats:** they carry over in both directions. On the API route Jorah receives the saved chat history, so a long chat costs more per turn. Back on the login, Claude Code resumes its own session and is told what was said in between.
- **Extra API use:** background helpers also run on the API route. One visible turn made 2 to 3 API requests in testing.
- **Delegated Claude Code tasks:** these stay on the Claude Code login on both routes, as long as no key is in an environment variable. Never `export ANTHROPIC_API_KEY` in the shell that starts the gateway, or set it in `env.vars` or `~/.openclaw-jorah/.env`: delegated tasks would inherit it and bill the API. `status` checks the config and `.env`, but it cannot see the running gateway's environment.
