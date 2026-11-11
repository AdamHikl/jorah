# P5.2 prep: `jorah-dev` gets the API key (2026-11-11, 20:20-20:45)

The scratch profile `jorah-dev` (state `~/.openclaw-jorah-dev`, port 43186, workspace `~/scratch-dev/workspace`, one agent `main`) is where P5's attack and poisoning tests run, so the live Jorah is never broken or polluted. Adam chose this, and to use the same Console key.

- **Key** [measured]: Adam stored it from the Mac's Terminal app (hidden prompt, sent through SSH's input, never on a command line) as `ANTHROPIC_API_KEY_JORAH`, kind secret, in `jorah-dev`'s own store. Stored secrets are write-only, so it could not be copied from the live profile.
- **Profile** [measured]: `secrets apply` (dry run, then applied) gave `jorah-dev`'s `main` the profile `anthropic:jorah-store`, a reference to that stored key, first in its auth order. `secrets audit --check`: clean.
- **Check** [measured]: `jorah-dev`'s Gateway started by hand on 127.0.0.1:43186 with `OPENCLAW_SKIP_CHANNELS=1` and `OPENCLAW_SKIP_CRON=1` (health: "Telegram: not configured"; no Telegram lines in its log), one turn on Haiku 5.5 into `agent:main:key-check` answered `KEY-OK`, then the Gateway was stopped (nothing on 43186 afterwards). The live Gateway on 43181 was not touched.
- `models status --probe` can't confirm a store reference without a running Gateway, and with one it failed on `jorah-dev`'s stale `acpx` entry (plugin not installed there). The real turn is the better check.

**Still to set up before the spikes:** `jorah-dev` dates from 2026-11-06. It has a Telegram block with a stored bot token, so it always starts with channels skipped, and P5.2 removes that block; its `main` is on Opus with none of the live agents, plugins or tool lists. P5.2 mirrors the live config onto it (minus Telegram, approvals to a stand-in, GitHub to a stand-in), previewed.
