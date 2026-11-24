# Pictures in the HUD: paste, Jorah looks, Jorah keeps

Built 2026-11-23 on `claude/hud-images`. Adam pastes (⌘V), drops or picks pictures in the Mac
HUD's composer; the HUD sends them with `chat.send`; Jorah looks at them and keeps the ones worth
keeping with `picture_save`, by its own rules, without a card (Adam's call, 2026-11-23).

## What changed

| Part | Where | What |
|---|---|---|
| HUD composer | `clients/mac-hud/Sources/JorahHUD/Views/HUDView.swift` | ⌘V with a picture on the clipboard (screenshot, "Copy Image", image files copied in Finder), drag and drop, and a 📎 button. Chips with thumbnail, size and ✕, and a running total. Up to 20 per message (raised from 4 on 2026-11-24); a message may be pictures only. Text pastes as before. |
| Preparing | `clients/mac-hud/Sources/HUDCore/ImagePrep.swift` | The pictures of one message share 18 MB, each at most 1.95 MB: a batch splits what is left equally, and later pictures get what remains. JPEG, PNG, WebP, GIF within 2048 px and their share go as they are; anything else (HEIC, TIFF, larger, rotated, or over its share) is redrawn (PNG with transparency, else JPEG) and shrunk until it fits. Why these numbers: below. Unit tests: `ImagePrepTests`. |
| Sending | `HUDModel.send()` | `chat.send` `attachments: [{ type: "image", mimeType, fileName, origin: "paste"\|"file", content: <base64>, sizeBytes, width, height }]`, the shape OpenClaw 2026.11.6 takes (`ChatAttachmentSchema`, source read on the PC). |
| Transcript | `HUDModel.line(from:)`, `ChatLineView` | Your sent pictures show as thumbnails; history shows `🖼 N pictures` where the Gateway stored them. |
| Keeping | `plugins/jorah-projects/lib/pictures.js`, tool `picture_save` | Copies a picture Adam sent (an attachment recorded in the same chat, or a file in the inbound-media folders) into `/home/jorah/workspace/files/pictures/<date>-<name>.<ext>` (mode 600, never overwriting) and adds `- <file>: <why>` to `INDEX.md` there. `"last"` is the newer of the chat's last recorded attachment and the newest picture in the inbound folders from the last half hour (a HUD paste may not reach `message_received`). Refuses while frozen. At most 20 per call; the folder stops at 5000 files or 2 GB. |
| Guard | `config/permission-matrix.json` | `picture_save` is in `read`, so no card from the HUD, by voice or after outside text. Why: `pictures.about` in the matrix. |
| Rules | `workspace/AGENTS.md`, "Pictures Adam Sends" | When to keep a picture, what never to keep unasked (health records, ID documents, bank or card details, other people's private messages), the `📎 Kept:` line, and finding pictures again through `INDEX.md`. |

## Why 20 pictures and 18 MB (2026-11-24)

Adam asked for 20 pictures and 40 MB. 20 works; 40 MB in one message doesn't, on OpenClaw 2026.11.6:

- The Gateway's WebSocket takes frames of at most 25 MiB (`maxPayload: 26214400`, fixed in its
  code, not a setting). Pictures travel as base64, a third larger, so one `chat.send` holds about
  19.4 MB of pictures; OpenClaw's own Mac app uses the same cap (19,464,192 bytes). 18 MB leaves room
  for the text and the frame.
- The Gateway hands the model a picture inline only up to 2,000,000 bytes; a bigger one is saved
  and the model gets a reference instead. So each picture stays under 1.95 MB, and Jorah sees all
  of them directly.
- Claude takes pictures up to 2576 px on the long edge and a request up to 32 MB; the HUD's 2048 px
  and 18 MB stay inside both.

Twenty photos at about 0.9 MB each, 2048 px, are what Jorah would see anyway: extra bytes beyond
that add no detail for the model. Kept pictures are these prepared copies, not the originals.

Unchanged: the guard still gives every other guarded call from the HUD a card (ADR 0011). Text in a
picture is outside text to Jorah, by the rules.

## Deploy (the deploy session, on Adam's yes for each step)

Shell setup, as in `deploy-13-24.md`: run from the main checkout with `HEAD` at the commit on
`origin/main` that holds this change.

```bash
cd ~/Documents/jorah && git pull --ff-only && git log -1 --oneline
```

```bash
PC=(ssh -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u root --)
```

### 0. Preflight (read only)

```bash
python3 scripts/pc/deploy_reviewed.py baseline
"${PC[@]}" bash -s <<'EOF'
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
"${OC[@]}" health 2>&1 | tail -1
"${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow
"${OC[@]}" config get plugins.entries.jorah-projects.config.mediaRoots 2>&1 | tail -1
ls -ld /home/jorah/.openclaw-jorah/media/inbound /home/jorah/workspace/files 2>&1
test -f /home/jorah/.jorah-guard/FROZEN && echo FROZEN || echo "not frozen"
EOF
```

Expected: no drift under `plugins/jorah-guard`, `plugins/jorah-projects`,
`config/permission-matrix.json` or `/home/jorah/workspace/AGENTS.md`; health ok; main's list has
no `picture_save`; `mediaRoots` not set (the plugin's default is
`/home/jorah/.openclaw-jorah/media/inbound` and `/home/jorah/workspace/media/inbound`) or set to
folders that include the first; the inbound folder exists (owner `jorah`); not frozen.

### 1. Backups

```bash
"${PC[@]}" bash -s <<'EOF'
set -e
CFG=/home/jorah/.openclaw-jorah/openclaw.json
B=/root/opt-jorah-pre-pictures-$(date +%F).tgz
tar -czf "$B" -C /opt/jorah plugins/jorah-guard plugins/jorah-projects config/permission-matrix.json
[ -f "$CFG.pre-pictures" ] || cp -p "$CFG" "$CFG.pre-pictures"
cp -p /home/jorah/workspace/AGENTS.md /home/jorah/workspace/AGENTS.md.pre-pictures
echo "$B: $(tar -tzf "$B" | wc -l) entries"
EOF
```

### 2. Code and the permission list

```bash
python3 scripts/pc/deploy_reviewed.py deploy plugins/jorah-guard plugins/jorah-projects config/permission-matrix.json
```

Expected: `deployed N file(s)`, all recorded. The Gateway runs the old code until step 5.

### 3. Plugin consent and main's tool list

The plugin declares a new tool, so OpenClaw asks for consent again:

```bash
"${PC[@]}" bash -s <<'EOF'
runuser -u jorah -- /usr/local/bin/openclaw --profile jorah plugins enable jorah-projects --accept-capabilities 2>&1 | tail -3
EOF
```

Main's list, built from the live one plus `picture_save` (dry run first):

```bash
"${PC[@]}" bash -s <<'EOF'
set -e
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
T=$(mktemp -d /tmp/pictures-tools.XXXXXX); chmod 755 "$T"
LIVE=$("${OC[@]}" config get agents.entries.main.tools.sandbox.tools.alsoAllow)
python3 -I - "$LIVE" "$T/p.json5" <<'P'
import json, sys
lst = json.loads(sys.argv[1])
if not isinstance(lst, list) or not lst: sys.exit("main's tool list isn't a list; stopping")
if "picture_save" not in lst: lst.append("picture_save")
json.dump({"agents": {"entries": {"main": {"tools": {"sandbox": {"tools": {"alsoAllow": lst}}}}}}}, open(sys.argv[2], "w"))
print(f"main's list would be ({len(lst)}): " + ", ".join(lst))
P
chmod 644 "$T/p.json5"
"${OC[@]}" config patch --file "$T/p.json5" --dry-run
echo "patch file: $T/p.json5"
EOF
```

Expected: step 0's list plus `picture_save` (count up by exactly 1); `Dry run successful` with one
update. On Adam's yes, run `config patch --file <that patch file>` without `--dry-run`.

### 4. Workspace rules

```bash
git show HEAD:workspace/AGENTS.md | "${PC[@]}" tee /home/jorah/workspace/AGENTS.md >/dev/null
python3 scripts/pc/deploy_reviewed.py record-live workspace/AGENTS.md=/home/jorah/workspace/AGENTS.md
```

Expected: recorded. The rule names `picture_save`, which works after step 5, so go on straight away.

### 5. Gateway restart

```bash
"${PC[@]}" bash -s <<'EOF'
systemctl start --no-block jorah-gateway-recycle.service
EOF
```

When the recycle service has finished:

```bash
"${PC[@]}" bash -s <<'EOF'
OC=(runuser -u jorah -- /usr/local/bin/openclaw --profile jorah)
journalctl -u jorah-gateway-recycle.service -n 5 --no-pager
"${OC[@]}" health 2>&1 | tail -1
"${OC[@]}" plugins list 2>&1 | grep -E "jorah-(guard|projects)"
journalctl -u openclaw-gateway --since "-10 min" --no-pager | grep -oE "jorah-(guard|projects): [^\"]*" | tail -5
"${OC[@]}" sandbox explain --agent main 2>&1 | grep -E "picture_save"
"${OC[@]}" security audit 2>&1 | grep -E "^Summary"
EOF
```

Expected: recycle succeeded, health ok; both plugins loaded with no "requires capability consent";
`jorah-guard: matrix loaded; state ok`; main's sandbox shows `picture_save`; 0 critical.

Undo (steps 2–5): restore the `.tgz` into `/opt/jorah`, `openclaw.json.pre-pictures` (owner
`jorah`, mode 600) and `AGENTS.md.pre-pictures`, recycle the Gateway, then
`deploy_reviewed.py baseline --write`. Kept pictures stay in `/home/jorah/workspace/files/pictures`.

## The HUD (Adam's Mac, on Adam's yes)

Quit the running HUD first (menu bar → Quit Jorah HUD), then:

```bash
cd ~/Documents/jorah && just mac-hud-install
```

Open Jorah HUD from `~/Applications`. Pairing is kept (Keychain).

## Acceptance (Adam, in the HUD)

1. **Paste a screenshot.** ⌃⇧⌘4, drag an area, click the HUD's message box, ⌘V. Expected: a chip
   with the thumbnail, `W×H · size` and ✕. Type "what's on this?" and press Return. Your line shows
   the thumbnail; Jorah describes what's in the picture.
2. **Picture only.** Copy a photo in Finder (⌘C on the file), ⌘V in the box, Send with nothing
   typed. Expected: it sends; Jorah answers about the picture.
3. **Jorah keeps one by itself.** Paste a photo of a receipt or a model plate and say "this is the
   receipt for the kettle". Expected: no card; the reply ends with
   `📎 Kept: files/pictures/2026-…-….jpg`. A one-off screenshot ("what's this error?") is not kept.
4. **Find it again.** Ask "show me the kettle receipt I sent". Expected: Jorah names the file from
   `INDEX.md` and describes it.
5. **Limits.** Pick 22 pictures: 20 attach, and the note says "Attached 20 of 22: at most 20
   pictures per message." The line under the chips shows the total of 18 MB. A HEIC from Photos
   arrives as JPEG. Text paste still pastes text.

On the PC, `ls -l /home/jorah/workspace/files/pictures` shows the kept files at `-rw-------`, and
`INDEX.md` has one line each.

**Unknown until step 1:** Jorah's main brain runs through Claude Code (`claude-cli`). The Gateway
passes the images to that runner; whether the model sees them as pictures or gets file paths it
then reads was not proven by source alone. If Jorah says it can't see the picture, that is the
finding: report it with the time, and the session log line `chat.send` wrote.

## Tiers

Source and unit tests (HUD 41, guard and projects suites) on 2026-11-23. Not yet: PC deploy,
HUD install, launch, and the acceptance above.
