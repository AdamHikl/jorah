// Condition script of the "Morning brief" automation (docs/runbooks/proactive.md). Evaluated every
// 5 minutes from 05:00 to 09:55 with no model; the brief's agent turn runs only when the code in
// proactive_due says it is due: alarm stopped on a school day, else 07:30, once a day, never after 10:00.
const r = await proactive_due({ type: "morning_brief" });
if (r && r.due === true) return { fire: true, message: `Why now: ${String(r.reason ?? "").slice(0, 80)}` };
return { fire: false };
