# ADR 0012: Drive mode, a command line that types in the Mac HUD while Adam allows it

**Status:** decided by Adam on 2026-11-25 ("Armed by a click (Recommended)"), built on
`claude/hud-drive`. Changed by Adam on 2026-11-26: an on/off button in the top bar instead of a
30-minute window ("make it so that I can toggle it off and on"). Marker added on 2026-11-26,
when Adam made HUD typing count as theirs (ADR 0011, "Same as Telegram (Recommended)").

**Question:** Claude Code build sessions need to test Jorah the way Adam uses it, through the HUD,
without being given computer use (screen control). How can a command line on the Mac talk to Jorah
through the HUD without holding the HUD's device credential, and without becoming a way to approve
cards?

## Decision

The HUD gets a **drive mode**. Adam switches it on with a click; nothing else can.

- **Switch:** the `⌨ CLAUDE CODE` button in the top bar, beside COMMAND (grey when off, orange
  `⌨ CLAUDE DRIVING` when on), or menu bar icon > "Let Claude Code drive". It stays on until Adam
  clicks it off (the button, the bar's SWITCH OFF or the menu), forgets the pairing, or quits the
  HUD. Every launch starts with it off. Not offered in the demo.
- **The socket:** while it's on, and only then, the HUD listens on a Unix socket,
  `~/Library/Application Support/JorahHUD/drive.sock` (`JorahHUD-<profile>` for a test profile).
  The folder is mode 700 and the socket 600. A connection from another user id is closed unread
  (`getpeereid`). One JSON line in, one JSON line out. The socket is removed when drive mode ends.
- **What it can do** (`DriveRequest` in `clients/mac-hud/Sources/HUDCore/Drive.swift`):
  `status`; `send` text (no pictures) to the conversation open on screen, never the HUD home
  session, and not while Jorah is still answering; `read` the last 1–40 lines; `cards` (unknown is an error, never an empty list); `deny`
  one card, after the same 1.5 s hold and expiry check as a click; `wait` until Jorah has answered
  and stopped, a card shows, or a timeout.
- **The marker:** every line it sends starts with `[Typed by Claude Code in HUD drive mode.]`
  (`DriveRules.wireText`). Only these commands go as they are: `/jorah-status`, `/jorah-today`,
  `/jorah-careful` (on, off), `/status`, `/help`, `/commands`, `/whoami`. Any other line starting
  with "/" is refused, so drive mode can't run `/new`, `/model`, `/approve` or `/jorah-freeze`.
  Jorah and the transcript see the marker; the HUD hides it and shows `⌨ CLAUDE CODE` instead.
- **What it can't:** allow a card, pair, pause, resume or kill the PC, switch the brain or model,
  open or start a conversation. These have no command; asking for them (`allow`, `approve`,
  `resolve`, `pair`, `power`, `brain`, `model`, …) gets a refusal naming Adam. A request with any
  key its command doesn't take is refused, so `deny` can't carry a decision: the HUD writes
  `"deny"` as a literal (`HUDModel.denyApprovalFromDrive`).
- **Seen by Adam:** the orange top-bar button, an orange bar across the top of the HUD with the
  time it went on and a SWITCH OFF button; a
  "Drive mode on/off" note in the conversation; `⌨ CLAUDE CODE` on every line it typed (also after
  the history reloads), and "(typed by Claude Code)" in a copied transcript.
- **Record:** `drive.log` in the same folder (mode 600): switching on and off and every send and deny,
  with the first 300 characters of the text.
- **Client:** `scripts/mac/jorah_hud_drive.py` (Python standard library). `send` waits for the
  answer and prints it; exit 3 means a card is waiting, with the `deny` command and "only Adam can
  allow, in the HUD".

## Why this shape

- **Not a script with the HUD's credential.** The device key lives in the HUD's Keychain item. A
  script reading it would be credential use outside the app Adam paired; the HUD acting on a
  request it can see and stop is not.
- **No new authority.** Lines sent this way go through the same `chat.send` as Adam's typing. Since
  2026-11-26 Adam's own HUD typing counts as their clean chat (ADR 0011), but a turn carrying the
  drive marker never does: jorah-guard gives it every card, saying Claude Code typed it. So a
  drive-mode message can make Jorah ask, but never act on a guarded step alone, and drive mode can
  only say no to the card.
- **Deny only.** Saying no can't widen what Jorah does; saying yes can. Allowing stays a click by
  Adam (ADR 0007), or Telegram.
- **A switch Adam clicks.** A socket that always listened would let any process running as Adam
  type as them at any time. Switching on is a click Adam makes knowing a test is about to run. The
  first design lapsed after 30 minutes; Adam chose a plain on/off switch instead, so it stays on
  until they switch it off or quit the HUD, and is off again at every launch.

## Risks left

- While it's on, any process running as Adam's macOS user can type in the open conversation as
  Adam and deny cards. That is the same reach such a process already has over Adam's Telegram
  desktop or Terminal. With no time limit, a switch left on stays open until the HUD quits; the
  orange button and bar and the log keep it visible.
- Jorah's tool hooks see these turns with `senderIsOwner: true`, like Adam's; only the marker sets
  them apart. A process that could send through the HUD without the marker would get Adam's clean
  chat, so the marker is added inside the HUD, not by the client, and the socket has no way to skip
  it. Jorah's own rules (`workspace/AGENTS.md`) are unchanged by this.
- Plugin commands don't count the HUD as Adam. OpenClaw treats a command's sender as owner only
  with `operator.admin` or a match in `commands.ownerAllowFrom`, and the HUD has neither, so the
  guard's commands answered "Only Adam…" from the HUD (seen 2026-11-26,
  `docs/evidence/hud-drive-2026-11-26/`). Adam then chose (2026-11-26, "Yes, do it here") to let
  the two safe-direction ones work there: `/jorah-careful` (on only) and `/jorah-today`. The guard
  recognises the HUD by channel `webchat`, an authorised sender and the `operator.write` scope in
  the command's `gatewayClientScopes` (`typedInOwnApp` in `plugins/jorah-guard/lib/policy.js`).
  So drive mode can turn careful mode on and read the day's count too. `/jorah-careful off` and
  `/jorah-freeze` stay on Telegram, so a line typed in the HUD can't lift careful mode. Voice can't
  run either: its words arrive after "[Spoken turn.", and OpenClaw runs only messages that start
  with "/".

## ADR 0011 option B, built 2026-11-26

This section used to say: before HUD typing counts as Adam's clean chat, drive mode must stop
sending through the HUD's device or mark its turns. It now marks them (above), and jorah-guard sorts
a marked turn as `drive` (`hudKind` in `plugins/jorah-guard/lib/policy.js`), with every card kept.
Removing the marker would give a command line card-free writes, so it stays as long as option B
does.

## Undo

Remove the top-bar button, the menu item and `armDrive` (or the whole `DriveServer`), rebuild and reinstall the HUD
(`just mac-hud-install`). Nothing runs on the PC and no config changed for this. While ADR 0011
option B is on, keep the marker for as long as drive mode exists.

## Related

ADR 0007 (HUD answers cards), ADR 0011 (HUD typed-chat trust).
