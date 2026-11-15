// OpenClaw plugin: phone_today (docs/contracts/jorah-phone-v1.md).
//
// Reads GET /today from the jorah-phone service on loopback with a read-only token kept in a file,
// checks the answer against packages/contracts/phone/today.schema.json, and hands Jorah exactly
// those fields. Every value was written by code from typed phone events and day rows, so the guard
// lists the tool as a plain read (no taint). Health fields pass only with includeHealth, which
// stays off until Adam's decision H. If anything is wrong, Jorah gets "unavailable" with a reason,
// never zeros. Plain object entry, the same shape definePluginEntry returns, so it needs no build.

import { readFileSync, statSync } from "node:fs";
import { request } from "node:http";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { Invalid, loadSchema, validate } from "./lib/schema.js";

const HERE = dirname(fileURLToPath(import.meta.url));
const CONTRACTS = join(HERE, "..", "..", "packages", "contracts", "phone");
const MAX_BYTES = 64 * 1024;
export const HEALTH_OFF = Object.freeze({ status: "off", received_at: null, night: null, hrv_ms: null, resting_bpm: null, workouts: [] });

const text = (body, details = {}) => ({ content: [{ type: "text", text: JSON.stringify(body) }], details });
const unavailable = (reason) => text({ v: 1, status: "unavailable", reason }, { status: "unavailable" });

export function readToken(file) {
  const info = statSync(file);
  if (info.mode & 0o077) throw new Error("the token file must be readable by its owner only");
  const token = readFileSync(file, "utf8").trim();
  if (!token) throw new Error("the token file is empty");
  return token;
}

export function loopbackUrl(raw) {
  const url = new URL(raw);
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost"].includes(url.hostname) || (url.pathname !== "/" && url.pathname !== "")) {
    throw new Error("serviceUrl must be http://127.0.0.1:<port> with no path");
  }
  return url;
}

function get(url, token, timeoutMs) {
  return new Promise((resolve, reject) => {
    const req = request({
      host: url.hostname, port: url.port || 80, path: "/today", method: "GET",
      headers: { Authorization: `Bearer ${token}`, Accept: "application/json" }, timeout: timeoutMs,
    }, (res) => {
      const chunks = [];
      let size = 0;
      res.on("data", (c) => {
        size += c.length;
        if (size > MAX_BYTES) { req.destroy(new Error("answer too large")); return; }
        chunks.push(c);
      });
      res.on("end", () => resolve({ status: res.statusCode, body: Buffer.concat(chunks).toString("utf8") }));
      res.on("error", reject);
    });
    req.on("timeout", () => req.destroy(new Error("timed out")));
    req.on("error", reject);
    req.end();
  });
}

export default {
  id: "jorah-phone",
  name: "Jorah phone",
  description: "phone_today: what Adam's iPhone reported today, as fields written by code.",
  register(api) {
    const cfg = api.pluginConfig ?? {};
    const tokenFile = cfg.tokenFile ?? "/home/jorah/.config/jorah-phone/read-token";
    const includeHealth = cfg.includeHealth === true;
    const timeoutMs = Number.isInteger(cfg.timeoutMs) ? Math.min(20000, Math.max(500, cfg.timeoutMs)) : 5000;
    let schema = null;
    let setupProblem = null;
    let url = null;
    try {
      url = loopbackUrl(cfg.serviceUrl ?? "http://127.0.0.1:43212");
      schema = loadSchema(cfg.contractsDir ?? CONTRACTS, "today");
    } catch (error) {
      setupProblem = String(error?.message ?? error).split("\n")[0].slice(0, 160);
      api.logger.warn(`jorah-phone: ${setupProblem}`);
    }

    api.registerTool({
      name: "phone_today",
      label: "Today from Adam's phone",
      description: "What Adam's iPhone has reported today, as fields written by code: where Adam is (at or left home, school "
        + "or other, by geofence name only), when Adam woke (alarm stopped), the current Focus, and, only if Adam turned health on, "
        + "last night's sleep, HRV, resting heart rate and today's workouts with 14-day medians. Missing data is null with a "
        + "status, never zero; say it's unknown rather than guessing. health.status \"off\" means Adam hasn't turned health on. "
        + "Never save these values to memory, and never say health numbers aloud through Siri: say \"It's in the app.\"",
      parameters: { type: "object", additionalProperties: false, properties: {} },
      async execute() {
        if (setupProblem) return unavailable(`phone_today isn't set up: ${setupProblem}`);
        let token;
        try {
          token = readToken(tokenFile);
        } catch (error) {
          api.logger.warn(`jorah-phone: token: ${error?.code ?? error?.message}`);
          return unavailable("the phone service's token can't be read");
        }
        let answer;
        try {
          answer = await get(url, token, timeoutMs);
        } catch (error) {
          api.logger.warn(`jorah-phone: /today: ${String(error?.message ?? error).slice(0, 80)}`);
          return unavailable("the phone service isn't answering");
        }
        if (answer.status !== 200) {
          api.logger.warn(`jorah-phone: /today answered ${answer.status}`);
          return unavailable(`the phone service answered ${answer.status}`);
        }
        let body;
        try {
          body = validate(schema, JSON.parse(answer.body));
        } catch (error) {
          api.logger.warn(`jorah-phone: /today failed its schema${error instanceof Invalid ? ` (${error.path})` : ""}`);
          return unavailable("the phone service's answer failed its check");
        }
        if (!includeHealth) body = { ...body, health: { ...HEALTH_OFF } };
        return text(body, { status: "ok", phone: body.phone.status, health: body.health.status });
      },
    });
  },
};
