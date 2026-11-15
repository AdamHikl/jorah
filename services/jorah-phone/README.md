# jorah-phone

The iPhone's way in to Jorah, on the PC in the `jorah` WSL distro as user `jorah`, on
`127.0.0.1:43212`, reached only through Tailscale Serve on `:43213`. Contract:
`docs/contracts/jorah-phone-v1.md`. Setup and Shortcut recipes: `docs/runbooks/phone.md`.

- **`POST /ask`** (Ask Jorah): one dictated question into Jorah's main session through the Gateway's
  Chat Completions endpoint on loopback, as `jorah-voice` does; the phone gets the spoken part back.
  The reply is always read to the end, because closing the connection would cancel Jorah's run.
- **`POST /ingest/event`, `POST /ingest/health`**: typed phone events and a daily health summary into
  SQLite. No model in this path, no sample kept. Both off until switched on (`--ingest`, `--health`).
- **`GET /today`, `GET /events`**: for code on the PC only (the `phone_today` plugin, the proactive
  layer).

Python standard library only, no dependencies: `/usr/bin/python3 -I bin/jorah-phone`. Requests and
answers are checked against `packages/contracts/phone/*.schema.json` by `jorah_phone/schema.py`.

| File | What |
|---|---|
| `jorah_phone/server.py` | HTTP routes, tokens and scopes, rate limits, the local-only check, switches |
| `jorah_phone/ask.py` | The Gateway call, the background read, and what is spoken (`[app]` split, caps) |
| `jorah_phone/store.py` | SQLite: events, one health row per day, retention, `/today` and `/events` |
| `jorah_phone/compute.py` | Health samples to one day row: merged night, HRV median, resting rate, workouts |
| `jorah_phone/tokens.py`, `bin/jorah-phone-token` | Tokens as SHA-256 hashes with scopes; make, list, revoke |
| `jorah_phone/schema.py` | The JSON Schema subset the contract uses |

Tests: `python3 -m unittest discover -s services/jorah-phone/tests` (part of `just unit`). They need
no network, no Gateway and no phone.

**Logs** hold outcomes and timings, never what was asked, answered, or reported, nor places or times.

**What it trusts.** It holds the Gateway token (`~/.config/jorah-voice/gateway-token`, shared with
`jorah-voice` and kept current by `scripts/pc/rotate-gateway-token.sh`), which is full operator
access, so it is as trusted as the Gateway. The phone's token is the narrow one.
