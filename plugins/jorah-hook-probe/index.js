// Roadmap step 2.1 (GROW-S13, first half of SEC-T25): does before_tool_call fire on this
// runtime, and can it block? Logs tool names only, never arguments. Remove after the test.

export const PROBE_WORD = "JORAH-HOOK-PROBE-7Q";

export function decide(event) {
  let text = "";
  try { text = JSON.stringify(event?.params ?? {}); } catch {}
  return text.includes(PROBE_WORD)
    ? { block: true, blockReason: "Blocked by jorah-hook-probe (roadmap step 2.1 test)." }
    : undefined;
}

export default {
  id: "jorah-hook-probe",
  name: "Jorah hook probe",
  description: "Test only: before_tool_call fires and blocks.",
  configSchema: { type: "object", additionalProperties: false },
  register(api) {
    api.on("before_tool_call", (event, ctx) => {
      const result = decide(event);
      api.logger.info(`hook-probe: ${result ? "BLOCKED" : "saw"} tool=${event?.toolName} agent=${ctx?.agentId ?? "?"}`);
      return result;
    });
  },
};
