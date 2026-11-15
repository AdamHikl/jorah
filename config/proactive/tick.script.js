// Proactive tick: the script payload of the "Proactive tick" automation (docs/runbooks/proactive.md).
// It runs every 2 minutes with no model. proactive_tick (plugins/jorah-proactive) reads new phone
// events, turns the kinds Adam turned on into candidates, decides each one in code, and hands back
// the queued lines; OpenClaw's announce sends `notify` to Adam's chat. Nothing else is reachable:
// the job's tool list is proactive_tick alone, and jorah-guard refuses that tool outside a cron session.
const r = await proactive_tick({});
if (r && typeof r.notify === "string" && r.notify.length > 0) return { notify: r.notify };
return {};
