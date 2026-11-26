# ADR 0012: Drive mode, a command line that types in the Mac HUD while Adam allows it

**Status:** decided by Adam on 2026-11-25 ("Armed by a click (Recommended)"), built on
`claude/hud-drive`.

**Question:** Claude Code build sessions need to test Jorah the way Adam uses it, through the HUD,
without being given computer use (screen control). How can a command line on the Mac talk to Jorah
through the HUD without holding the HUD's device credential, and without becoming a way to approve
cards?

## Decision

The HUD gets a **drive mode**. Adam turns it on with a click; nothing else can.

- **Arming:** menu bar icon > "Let Claude Code drive (30 min)". It ends after 30 minutes, on
  "Stop" (orange bar or menu), when the PC is paused or resumed, when the pairing is forgotten, or
  when the HUD quits. Arming again starts a new 30 minutes. Not offered in the demo.
- **The socket:** while armed, and only then, the HUD listens on a Unix socket,
  `~/Library/Application Support/JorahHUD/drive.sock` (`JorahHUD-<profile>` for a test profile).
  The folder is mode 700 and the socket 600. A connection from another user id is closed unread
  (`getpeereid`). One JSON line in, one JSON line out. The socket is removed when drive mode ends.
- **What it can do** (`DriveRequest` in `clients/mac-hud/Sources/HUDCore/Drive.swift`):
  `status`; `send` text (no pictures) to the conversation open on screen, never the HUD home
  session; `read` the last 1–40 lines; `cards` (unknown is an error, never an empty list); `deny`
  one card, after the same 1.5 s hold and expiry check as a click; `wait` until Jorah has answered
  and stopped, a card shows, or a timeout.
- **What it can't:** allow a card, pair, pause, resume or kill the PC, switch the brain or model,
  open or start a conversation. These have no command; asking for them (`allow`, `approve`,
  `resolve`, `pair`, `power`, `brain`, `model`, …) gets a refusal naming Adam. A request with any
  key its command doesn't take is refused, so `deny` can't carry a decision: the HUD writes
  `"deny"` as a literal (`HUDModel.denyApprovalFromDrive`).
- **Seen by Adam:** an orange bar across the top of the HUD with its end time and a Stop button; a
  "Drive mode on/off" note in the conversation; `⌨ CLAUDE CODE` on every line it typed (also after
  the history reloads), and "(typed by Claude Code)" in a copied transcript.
- **Record:** `drive.log` in the same folder (mode 600): arming, stopping and every send and deny,
  with the first 300 characters of the text.
- **Client:** `scripts/mac/jorah_hud_drive.py` (Python standard library). `send` waits for the
  answer and prints it; exit 3 means a card is waiting, with the `deny` command and "only Adam can
  allow, in the HUD".

## Why this shape

- **Not a script with the HUD's credential.** The device key lives in the HUD's Keychain item. A
  script reading it would be credential use outside the app Adam paired; the HUD acting on a
  request it can see and stop is not.
- **No new authority.** Lines sent this way go through the same `chat.send` as Adam's typing.
  jorah-guard treats HUD typing (`webchat`) like voice today: every guarded call gets a card (ADR
  0011, option A, undecided). So a drive-mode message can make Jorah ask, but never act on a
  guarded step alone, and drive mode can only say no to the card.
- **Deny only.** Saying no can't widen what Jorah does; saying yes can. Allowing stays a click by
  Adam (ADR 0007), or Telegram.
- **Click to arm, time-boxed.** A socket that always listened would let any process running as
  Adam type as him at any time. Arming is a click Adam makes knowing a test is about to run, and it
  lapses on its own.

## Risks left

- While armed, any process running as Adam's macOS user can type in the open conversation as Adam
  and deny cards. That is the same reach such a process already has over Adam's Telegram desktop or
  Terminal; the time box, the orange bar and the log keep it visible and short.
- Jorah sees these turns as Adam's (`senderIsOwner`). Jorah's own rules (`workspace/AGENTS.md`)
  are unchanged by this.

## If ADR 0011 option B or C is ever built

Then HUD typing from the pinned device would count as Adam's clean chat and some guarded steps
would run without a card. Before that ships, drive mode must either stop sending through the HUD's
device, or mark its turns so the guard treats them as not clean (cards as now). Building B or C
without one of these would give a command line card-free writes.

## Undo

Remove the menu item and `armDrive` (or the whole `DriveServer`), rebuild and reinstall the HUD
(`just mac-hud-install`). Nothing runs on the PC and no config changed for this.

## Related

ADR 0007 (HUD answers cards), ADR 0011 (HUD typed-chat trust).
