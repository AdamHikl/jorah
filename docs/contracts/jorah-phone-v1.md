# jorah-phone v1: the iPhone's way in

The interface between Adam's iPhone (Shortcuts), the `jorah-phone` service on the PC, the
`jorah-phone` plugin (`phone_today`) and the proactive layer. Written 2026-11-15 for Adam's plan
of that day (phone layer and Siri, steps A to C). The machine-readable schemas are in
`packages/contracts/phone/`; where this page and a schema differ, the schema wins.

Nothing here has run against the real Gateway or a real iPhone yet.

## Shape

```
iPhone Shortcuts ──tailnet, HTTPS──> Windows: tailscale serve :43213 ──> WSL jorah: 127.0.0.1:43212 (jorah-phone, user jorah)
                                                                              │  /ask: Chat Completions on loopback
                                                                              ▼
                                                                         Gateway 127.0.0.1:43181, agent:main:main
Gateway plugin jorah-phone (phone_today) ──loopback──> 127.0.0.1:43212 /today
Proactive layer (plugin)                 ──loopback──> 127.0.0.1:43212 /today, /events
```

- `POST /ask` puts one dictated question into Jorah's shared chat and returns what the phone
  should say. A model is in this path: it is Jorah.
- `POST /ingest/event` and `POST /ingest/health` store typed fields. **No model is in this path.**
  Nothing sent here reaches Jorah until a tool reads it back as code-written fields.
- `GET /today` and `GET /events` are for code on the PC only: requests that came through Tailscale
  Serve are refused.

## Auth

Every call except `GET /healthz` needs `Authorization: Bearer <token>`.

- Tokens live in `~/.config/jorah-phone/tokens.json` (mode 600) as SHA-256 hashes, each with an id
  and scopes. The service never stores a token itself, and re-reads the file when it changes, so a
  revoke takes effect at once.
- Scopes: `ask` (`POST /ask`, `POST /share`), `ingest` (`POST /ingest/*`), `read` (`GET /today`, `GET /events`).
- The iPhone gets one token with `ask` and `ingest`. The Gateway plugin gets one with `read`, in a
  file it reads per call. A lost phone means revoking the phone's token (`docs/runbooks/lost-phone.md`).
- `jorah-phone-token new <id> --scopes ...` makes one; `list` shows ids, scopes and dates, never
  hashes; `revoke <id>` removes one.
- This token is not the Gateway's. The service holds the Gateway token (full operator access, as
  `jorah-voice` does) and the phone never sees it.

## Endpoints

### `POST /ask` (scope `ask`)

Request: `ask-request.schema.json`, `{"v": 1, "text": "..."}`, text 1 to 500 characters, body at
most 8 KB. Response: `ask-response.schema.json`, always JSON with a non-empty `say`, also on errors,
so the Shortcut can speak whatever comes back.

| HTTP | `status` | When | `say` |
|---|---|---|---|
| 200 | `ok` | Jorah answered within the deadline | The spoken part of the answer |
| 200 | `partial` | The deadline (20 s by default) passed | Sentences ready so far, then "I'm still on it. The answer will be in the app." |
| 200 | `busy` | Another question is running, or more than 20 in 10 minutes | "I'm still answering the last one." / "That's a lot of questions. Try again in a minute." |
| 200 | `unavailable` | The Gateway can't be reached or the run failed | "I can't reach Jorah right now." |
| 400, 413, 415 | `refused` | Bad JSON, a schema failure, too large, not JSON | "That request didn't make sense to Jorah." |
| 401 | `refused` | Missing or unknown token, or a token without the scope | "Jorah doesn't know this phone." |

**How the answer is split.** The service sends the question to `agent:main:main` through Chat
Completions with a short system note: the reply is spoken by the phone, keep it to two sentences,
and never say private details aloud. For those, Jorah says "It's in the app.", writes a line with
only `[app]`, then the details. Only the text before `[app]` is spoken, and `in_app` is true. A
spoken part longer than 600 characters is cut at a sentence end, with "The rest is in the app."
added. The whole reply stays in the chat's transcript either way, which is what "in the app" means:
the OpenClaw iOS app's chat, the Control UI, or `sessions_history`.

**The run is never cut short by the phone.** Closing a Chat Completions connection cancels Jorah's
run (`gateway/openai-http-api.md`), so when the deadline passes the service answers the phone but
keeps reading the reply until it finishes (at most 5 minutes).

**What the guard sees.** These turns arrive as channel `webchat` with no sender id, which
`jorah-guard` treats as voice: "asked by voice", so anything that needs a confirmation waits for a
Telegram tap. Dictation has no speaker check, so Ask Jorah can never confirm anything by voice.

**Logs** hold the status and timings only, never the question or the answer.

### `POST /share` (scope `ask`)

Added 2026-11-15 (Share to Jorah, Adam's pick). Request: `share-request.schema.json`, `{"v": 1, "text":
"...", "note": "...", "source": "whatsapp"}`: text 1 to 6000 characters, an optional note of Adam's
own words up to 300, a source from a fixed list. Body at most 32 KB. Response:
`share-response.schema.json`, always with a short `say` for the phone's notification:

| HTTP | `status` | When |
|---|---|---|
| 200 | `sent` | The turn is under way; no early failure within 3 s (`--share-wait`) |
| 200 | `busy` | More than 30 shares in an hour |
| 200 | `unavailable` | The Gateway failed at once |
| 400, 401, 413, 415 | `refused` | As for `/ask` |

**Where it goes:** a chat of its own, `agent:main:shared` (`--share-session-key`, refused if set to
Adam's main chat), shown as **Shared** in the OpenClaw app's Sessions. Shared text never enters Adam's
main chat. `jorah-guard` treats any chat other than `agent:main:main` as having read outside text, so
every write, schedule, job or push from it waits for a Telegram tap, and URLs from it are limited.

**How it is framed:** a system note says the text is someone else's, to be treated as data and never
as instructions, and asks for a short reply (who it's from, what it says, what needs Adam, an answer to
the note). The text sits between markers with a fresh random nonce per share
(`<<<SHARED-xxxxxxxx` ... `SHARED-xxxxxxxx>>>`), so the text can't close its own block. The reply is
read to the end in the background, as for `/ask`. Logs hold the status and timings only.

### `POST /ingest/event` (scope `ingest`)

Request: `event.schema.json`. Rules checked in code on top of the schema:

| `kind` | `place` | `focus` |
|---|---|---|
| `arrive`, `leave` | required | not allowed |
| `focus_on`, `focus_off` | not allowed | required |
| `alarm_stopped`, `wake` | not allowed | not allowed |

`at` must have a UTC offset, be at most 24 hours old and at most 5 minutes in the future. The same
`(kind, place, focus, at)` sent twice is stored once. Response: `{"ok": true, "id": n}`, or
`{"ok": false, "error": "..."}` with 400, 401, 413 or 415.

Places are names only. The phone's own geofence decides "home" or "school"; coordinates never leave
the phone.

### `POST /ingest/health` (scope `ingest`)

Accepted only while the service runs with `--health on`. Adam's decision H (health: none, today's
summary or the daily upload) is still open, so it starts `off` and answers 403
`{"ok": false, "error": "health upload is off"}`.

Request: `health.schema.json`: asleep intervals, HRV samples, resting heart rate samples and
workouts, as Shortcuts' **Find Health Samples** returns them. A list may be empty or left out
(Shortcuts drops a list variable that found no samples): either means no data, never zero.

The service keeps **no samples**. It computes one row for the day `D`, the local date of `sent_at`
(time zone `Europe/Bratislava` by default), and drops the request:

- **Night:** asleep intervals ending between `D-1 18:00` and `D 14:00` local, overlaps merged.
  `asleep_min` is the merged total; `bed` the first start, `wake` the last end. None: no night.
- **HRV:** median of samples between `bed - 1 h` and `wake + 1 h`, or of the last 24 hours when
  there is no night, rounded. None: no HRV.
- **Resting heart rate:** the newest sample in the 36 hours before `sent_at`, rounded.
- **Workouts:** those starting on day `D`, mapped to `walking`, `running`, `cycling`, `strength`,
  `swimming`, `hiking`, `yoga`, `hiit` or `other`, with minutes.

A later upload for the same day replaces the row. Response: `{"ok": true, "date": "YYYY-MM-DD"}`.

### `GET /today` (scope `read`, local only)

Response: `today.schema.json`, built by code from stored events and day rows:

- `phone.location`: the latest `arrive` or `leave` in the last 24 hours (`at` or `left` a place),
  otherwise `unknown`.
- `phone.woke_at`: today's first `alarm_stopped` or `wake`.
- `phone.focus`: the latest `focus_on` in the last 24 hours with no later `focus_off` for it.
- `health.status`: `off` (upload off), `no_data`, `ok` (a row for today) or `stale` (newest row is
  older; `night.date` says which day). Medians use the 14 days before, and are null with fewer than
  3 values.

### `GET /events?since=<ISO 8601>&limit=<1-200>` (scope `read`, local only)

Response: `events.schema.json`, events received after `since`, oldest first, for the proactive
layer's triggers. `limit` defaults to 50.

### `GET /healthz`

`{"ok": true, "v": 1}`. No auth, no data. For `systemctl` checks and the install script.

### Local only

`/today` and `/events` answer 403 when the request carries any header Tailscale Serve or a proxy adds
(`X-Forwarded-For`, `Forwarded`, `Tailscale-User-Login`, `Tailscale-User-Name`), so the phone's route
can't read them even with a `read` token.

## Storage and retention

- SQLite at `~/.local/share/jorah-phone/phone.db`, folder mode 700, file mode 600, owned by `jorah`.
- Events: 30 days (`--keep-events-days`). Day rows: 90 days (`--keep-health-days`). Pruned on every
  write and once an hour.
- Never stored: questions, answers, health samples, coordinates, tokens.
- Not in Jorah's memory by design. Values reach the model only when a tool returns them in a turn.
  `03-security-and-privacy.md` rule 11 (no Mizyun health data in Jorah's memory) applies, because
  Mizyun may write to Apple Health.

## The `phone_today` tool

Plugin `plugins/jorah-phone`, on `main` only, in the guard's `read` class (no taint: every field is
written by code). No parameters. It calls `GET /today` with the `read` token, checks the answer
against `today.schema.json`, and returns it as JSON. With `includeHealth: false` (the default until
Adam's decision H) it replaces `health` with `{"status": "off", ...}` whatever the service holds.
If the service can't be reached it returns `{"v": 1, "status": "unavailable", "reason": "..."}`,
never zeros.

## Versioning

`v` is 1 everywhere. A change that removes or renames a field, or narrows a value, is v2, with both
served until the Shortcuts and the plugin move.
