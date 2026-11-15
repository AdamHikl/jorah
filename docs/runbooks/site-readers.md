# Site readers: Jorah reads Adam's signed-in sites

Started 2026-11-15 on Adam's decision: read signed-in sites (EduPage first) through a browser, with
no third-party library, "heavy testing and guards", and a way to add more sites easily. The terms
check for EduPage is waived in writing (Adam's private answers file, 2026-11-15). This replaces
`docs/plan/06-connectors.md` C7's library route and C13's "never for EduPage".

**State, 2026-11-15:** stage C passed on jorah-dev, 47 of 47 checks against the hostile fake school
(`docs/evidence/site-readers/2026-11-15-stage-c.md`). On the PC: the users, firewall rules and unit
files (`--system-only`, by Adam); nothing in live Jorah's config, no site set up. Next: Adam sends
EduPage's page addresses; stage D after the P5 gate. Nothing private connects before then.

## How it works

Jorah's main agent calls `site_read` (or `sites_list`). That starts `reader-site`, a separate agent
on Haiku through the API key, in a fresh session named for the site. The reader opens and reads the
site's listed pages in that site's own signed-in Chrome, and answers with one JSON object. The answer
is checked, and only fixed fields go back to main. Then the reader's session, which holds the raw
page text, is deleted.

| Layer | What it stops | Where |
|---|---|---|
| One site file per site | Lists the site's host, its pages (addresses), what kinds of facts come back. Nothing outside it is reachable | `config/sites/<name>.json` |
| A separate Linux user for the browsers, `jorah-sites` (1101) | Jorah's processes can't read the sign-in cookies. Profiles in `/var/lib/jorah-sites/<name>`, mode 700 | `scripts/pc/site-browser.sh`, `deploy/jorah-site-browser@.service` |
| Network fence | The browser reaches only the site proxy. The proxy (`jorah-proxy`, 1102) tunnels only to the hosts in the site files, port 443, public addresses only. A hostile page can't send what it reads anywhere else | `deploy/jorah-firewall.nft`, `services/jorah-site-proxy/` |
| Guard rules | Only `reader-site`, only in a session `site_read` started, only that site's browser, only `navigate`/`open` to listed pages and `snapshot`/`text`/`screenshot`/`tabs`/`focus`/`close`. No clicks, typing, forms, keys, scripts, uploads, network logs, other tools. No other agent may use a site browser, spawn the reader or schedule it | `plugins/jorah-guard/lib/sites.js` |
| Checked output | Only typed items (`event`, `grade`, `notice`, `task`, `item`) with capped fields; links, e-mail addresses and phone numbers removed; people's names hidden (except names Adam keeps); anything else is "not available" | `plugins/jorah-sites/lib/output.js` |
| No traces | Each read is a new session, deleted afterwards. The guard's log keeps no addresses | `plugins/jorah-sites/index.js` |

**Honest limits.**
- The guard is what stops a message being sent: the site itself is reachable, so the fence can't. A
  compromised Gateway beats the guard (as for every guard rule, `p5-plan.md` 4.7).
- The site's own page code still runs, so opening a notice may mark it read, as when Adam opens it.
- Sites that only show data after clicks can't be read this way. Give them extra page addresses
  (`extraPaths`) if they have them; otherwise they don't fit.
- Name hiding is a pattern (capitalised word pairs), not understanding. It can miss a name or hide a
  subject. Adam can list names to keep.
- Sign-ins expire. Jorah then says "Signed out of <site>" and Adam signs in again.

## Adding a site

1. **Site file (a build session, reviewed like code).** Copy `config/sites/_template.json` to
   `config/sites/<name>.json`. Fill in the host (or `{ "from": "private", "pattern": ... }` when the
   address is personal, like a school's), the pages Adam sends (address bar copies), the kinds, a free
   `cdpPort` in 43220-43229 and words to block. Commit, `just check`, then copy the commit to `/opt/jorah`.
2. **Private address (Adam, PC, root), only for a private host:**
   `site.sh set-host <name> <host>`. Refused unless it matches the site's pattern.
3. **Browser (Adam, PC, root):** `site.sh add <name> --dry-run`, then `site.sh add <name>`. Expected:
   `active` and `DevTools answers: ...`.
4. **Sign in (Adam, at the PC's screen):** `site.sh signin <name>`. A Chrome window opens on the site.
   Sign in, don't let Chrome save the password, close the window. Expected: "Back to the headless browser".
5. **Check (Adam, Telegram):** "What's on my <name>?" Expected: an answer from the site, no links,
   names hidden. `site.sh status` shows the site `address  active`.

Removing: `site.sh remove <name>` (add `--wipe` to delete the sign-in too), then delete the site file
in a commit.

**Never add:** banking or payments, slovensko.sk, Apple ID, Adam's main Google account (it has the
read-only key instead), e-mail, password managers, GitHub. Sites where Adam signs in with Google need
their own password or an emailed sign-in link first (see "Google sign-in" below).

### Google sign-in

A site profile must never hold Adam's Google session: it would give full access to Gmail and Drive.
For a site Adam signs in to with Google: add a password to that site's account if it allows one, or
use its emailed sign-in link. Otherwise: sign in with Google in `site.sh signin`, then, in the same
window, sign out of Google at accounts.google.com (the site usually keeps its own session) and close
it. Repeat when the site signs Adam out.

## Stages

### A. Spikes (jorah-dev, needs Adam for root steps)

**A1 and A3: yes, measured in stage C (2026-11-15).** A2 and A4 wait for stage D.

- A1. Does the Gateway drive a Chrome under `jorah-sites` through `cdpUrl` + `attachOnly` on loopback?
- A2. Sign-in: does `site.sh signin` show a window through WSLg with Adam at the PC? If not, the
  fallback is an SSH tunnel to the DevTools port and `chrome://inspect` on the Mac.
- A3. Does `api.runtime.subagent.run` from a plugin tool start `reader-site` (or does it need
  `main.subagents.allowAgents`, which the guard would still police)?
- A4. Which hosts EduPage's pages load files from: open each page in the test proxy's log, then add
  them to `extraHosts`. Adam sends the real page addresses; the three in `edupage.json` are guesses
  (`confirmed: false`).

### B. Build (done in source, 2026-11-15)

`plugins/jorah-guard/lib/sites.js` (rules, shared), `plugins/jorah-sites/` (tools, brief, checker),
`services/jorah-site-proxy/`, `scripts/pc/site-browser.sh`, `site.sh`, `install-site-readers.sh`,
`deploy/` units and firewall rules, `workspace-site-reader/`, `config/pc/site-reader*.json*`,
`tests/sites/` (the fake school). Unit tests in `just check`: the guard's site rules against a
fully hijacked reader, the checker against hostile answers, the tool with a stand-in runtime, the
proxy with real sockets.

### C. Tests on jorah-dev (Adam runs the root steps)

1. Copy the commit to `/opt/jorah` (root-owned). Adam, as root: `install-site-readers.sh
   --system-only --dry-run`, read it, then `install-site-readers.sh --system-only`: the two users, the
   private file (empty), `/var/lib/jorah-sites`, the firewall rules and the unit files. Nothing in
   OpenClaw and no service started; live Jorah only gains loopback access to 43220-43229.
2. jorah-dev, as jorah: `site-readers-dev-setup.sh --dry-run`, then without it. It copies
   `jorah-guard`, `jorah-sites` and the permission list to `~/scratch-dev/p5`, the reader's rules to
   `~/scratch-dev/workspace-site-reader`, adds `reader-site` with the stored key, applies
   `config/pc/dev/site-readers.patch.json5`, adds `site_read` and `sites_list` to jorah-dev main's
   tools, and restarts jorah-dev.
3. Run: `python3 /opt/jorah/scripts/pc/site-readers-dev-test.py --runs 3` as root. It starts the
   fake school, a test proxy on 43218 and the fake school's browser, then:
   - isolation checks: jorah can't read the cookies or reach the proxy; the browser user reaches
     nothing but the proxy; the proxy refuses other hosts, the LAN and the Gateway; DevTools refuses a
     web page's origin; a sandboxed shell can't reach DevTools;
   - live checks with the real model: lessons come through, no names, links or numbers leak; the fake
     school counts no sends, posts, deletes or log-outs; the page script's calls to `evil.test` are
     refused by the proxy; main can't use the site browser or spawn the reader; signed out stops
     without typing; no reader session is left.
   Pass: every check passes. Blocks the guard had to make are listed as findings.
4. Evidence: the summary in `docs/evidence/site-readers/`, without private content.

### D. Live, after the P5 gate

`site.sh set-host edupage <school>.edupage.org`, `site.sh add edupage`, `site.sh signin edupage`,
then Adam checks today's timetable and one grade against the EduPage app, and two weeks of the
guard's log show only reads by `reader-site`.

## Undo

`install-site-readers.sh --undo` stops the browsers and the proxy, removes the plugin and restores
`openclaw.json.pre-sites`. The users, firewall rules and sign-ins stay; `site.sh remove <name> --wipe`
deletes a sign-in.
