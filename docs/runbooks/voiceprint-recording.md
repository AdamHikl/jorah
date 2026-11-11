# Recording Adam's voiceprint (P5, spike G-S8)

For the speaker check in `docs/plan/p5-plan.md` 4.3. About two minutes of recording in all. **The recordings never go in the repo or anywhere online.** Claude copies them to the PC into `jorah-voice`'s private folder (mode 600), deletes the Mac copies after checking them, and they're in the PC's encrypted backups like the other voice files.

## How to record

- **Where:** a quiet room, the way you'd normally talk to Jorah. Normal voice, normal speed. Don't read like a newsreader.
- **App:** Voice Memos or QuickTime Player (File → New Audio Recording) on the Mac.
- **Two setups, the whole script once in each:**
  1. **Mac mic:** sitting at the Mac, about an arm's length away. File name `mac.m4a`.
  2. **AirPods:** connected to the Mac (Control Centre → Sound → AirPods as input). File name `airpods.m4a`.
- **Save both in** `~/Documents/jorah-voiceprint/` (a new folder, outside the repo). Then tell Claude they're there.
- A slip or restart in the middle is fine: just say the sentence again and carry on.

## The script

Pause for a second between the parts.

**Part 1, talking (about 40 seconds):**

> Hey Jorah, it's Adam. I'm recording this so you can tell my voice apart from anyone else's in the room.
> This morning I want to finish the robot arm notes, check the pull request on threadfolio, and go for a run before it gets dark.
> If the weather in Bratislava is bad, remind me to take the bus instead of the bike.
> The quick brown fox jumps over the lazy dog, while seven tired engineers argue about the warmest jacket.
> Please keep the summary short, skip the jokes for now, and tell me only what changed since yesterday.

**Part 2, the words you'll confirm with (about 30 seconds):**

> Yes. Yes, do it. Confirm. Go ahead. No. Cancel that. Stop.
> Yes, push it. Yes, save that. Yes, start the job.
> Zero, one, two, three, four, five, six, seven, eight, nine.
> The code is four, seven, one, nine. The code is zero, two, eight, three. The code is six, six, five, zero.

**Part 3, a few questions as you'd really ask them (about 20 seconds):**

> Jorah, what's on my list for today?
> Can you clone partaci and get Claude Code on the login bug?
> Remember that the test plant needs water on Fridays.

**Optional, if you also speak Slovak to Jorah:**

> Ahoj Jorah, tu je Adam. Dnes chcem dokončiť poznámky k robotickej ruke a večer si ísť zabehať.

## Afterwards

Claude checks each file's length and quality, without playing it back to anyone, builds the voiceprint on the PC, and then runs G-S8: 300 tries from other voices (public speech recordings, the TV, Jorah's own voice), which must all be refused, and 20 of your own answers through each setup, which should pass at least 19 times in 20. Those 20 answers come later as a separate short recording, with prompts Claude gives you then.
