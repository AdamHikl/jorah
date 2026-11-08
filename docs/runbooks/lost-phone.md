# Lost or stolen phone

Roadmap 2.14, written before the iPhone is paired. SEC-T16 is the drill that tests it.
Commands checked against `openclaw --help` on the PC (OpenClaw 2026.10.9), 2026-11-08.

**Goal:** within minutes, the lost phone can't talk to Jorah, approve anything, read Telegram or
reach the tailnet. Do the steps in order. Each one stands alone, so stop at none.

Run the `openclaw` commands from the Mac, in a Terminal attached to no agent, through:

```bash
ssh -t -i ~/.ssh/jorah-pc-setup -o IdentitiesOnly=yes adamh@100.115.240.14 wsl -d jorah -u jorah -- bash -l
```

If the Mac isn't at hand, step 1 and steps 5 to 7 work from any browser or another device.

## 1. Lock and locate (any device)

1. **Find My** at icloud.com/find, or the Find My app on the Mac: **Mark As Lost**. That locks the
   phone with a passcode and shows a message.
2. If it won't come back: **Erase This Device**. Do it after steps 2 to 7 if you want its location first.

## 2. Remove the phone from the Gateway

```bash
openclaw --profile jorah devices list
```

Find the phone's entry (name, platform iOS, last seen). Note its device id. Then, for each role it
holds (`operator`, and `node` if it was paired as one):

```bash
openclaw --profile jorah devices revoke --device <id> --role operator
openclaw --profile jorah devices revoke --device <id> --role node
openclaw --profile jorah devices remove <id>
```

If it appears as a node:

```bash
openclaw --profile jorah nodes remove --node <id>
```

Expected: `devices list` no longer shows the phone. Revoking a setup link does **not** revoke a
paired device, so this step is needed even if the pairing code expired long ago.

## 3. Replace the Gateway token (if the phone was paired Full)

A Full pairing can hold `operator.admin`. Replace the shared token too:

```bash
bash -l /opt/jorah/scripts/pc/rotate-gateway-token.sh
```

It asks first, never prints the token, and updates jorah-voice's copy. Then restart, as root:

```bash
wsl -d jorah -u root -- systemctl restart openclaw-gateway jorah-voice
```

Expected: Telegram still answers; the browser and `mac-ear` need the new token (the script says how).

## 4. Check what happened

```bash
openclaw --profile jorah logs --limit 2000 --local-time
```

(`logs` has no time filter in 2026.10.9; raise `--limit` to reach back far enough.) Look for approvals, sends or Talk sessions from the phone's device id after you lost it. Anything
there goes to Claude as evidence, with private content removed, in `docs/evidence/lost-phone/`.

## 5. Telegram (any device)

Telegram on the Mac or web.telegram.org: **Settings, Privacy and Security, Active Sessions**, terminate
the phone's session. If the phone could have messaged Jorah's bot, also BotFather: `/revoke` for the
bot's token, then store the new one (`docs/runbooks/cutover.md`, the token step).

## 6. Tailnet (any device)

login.tailscale.com, **Machines**: find the phone, **Remove** (or **Disable key expiry** off and
**Expire key**). Expected: it disappears from `tailscale status` on the Mac.

## 7. Apple account (any device)

appleid.apple.com: change the Apple Account password, check **Devices** and remove the phone.

## Afterwards

- Pair the new phone only after this list is done, with a fresh setup code.
- Record the date and which steps ran in `docs/evidence/lost-phone/`.
- SEC-T16 passes when, after steps 2 and 3, the old phone's app can no longer connect or approve.
