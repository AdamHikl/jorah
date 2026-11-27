# Files from Jorah in the HUD, and Shift-Return (2026-11-27)

Commit `cee9876`: the HUD shows files Jorah sends (`MEDIA:` lines) as cards that open a viewer
window and save to the Mac; Shift-Return in the composer inserts a line; Jorah's rules gain
"Sending Adam Files". Adam's yes: "Yes, build both", then "Yes, deploy rule".

## Source and tests

| Check | Result |
|---|---|
| `swift test` (HUD) | 67 tests, 0 failures, including 13 new (`SentFilesTests`, `MarkdownBlocksTests`) |
| `just check` | passed (exit 0) |
| `workspace/AGENTS.md` | 35,996 UTF-16 chars, under the 36,000 budget test |
| Reply mode | `messages.visibleReplies` unset, so direct HUD chats use automatic final replies and a standalone `MEDIA:` line attaches |

## Rules deploy

| Step | Result |
|---|---|
| Preflight | live `workspace/AGENTS.md` matched `2c23647`/`0caf008` (sha256 `b9bf3b03…`) |
| Backup | `/home/jorah/workspace/AGENTS.md.pre-hud-files` (`cp -p`, then mode 600; jorah:jorah, 35996 bytes) |
| File | piped from `origin/main` (`cee9876`) to `tee` as root at 20:49, then `sync`; live sha256 `f732f70b…`, matching `cee9876`; jorah:jorah 644 (36013 bytes); `record-live`: recorded from `cee9876` |
| Restart | none; takes effect from Adam's next `/new` |

Undo: as root, `cp -p /home/jorah/workspace/AGENTS.md.pre-hud-files /home/jorah/workspace/AGENTS.md && sync`,
then `deploy_reviewed.py baseline --write`.

## HUD install and launch

After Adam said his coding job had finished: `just mac-hud-install` from `1173692` (release build,
signed with the Apple Development certificate, `codesign -v` passes); the old HUD (PID 6060) quit
through AppleScript, the new one opened as PID 6695 and holds TCP links to the PC on `:443` (Serve,
the Gateway) and `:43231` (PC stats). That shows launch, not that the cards work.

## Open

- Signed-in acceptance: after `/new`, Jorah sends a PDF, a Markdown file and a picture; each shows as a
  card, opens in the viewer and saves to Downloads. Shift-Return adds a line.
