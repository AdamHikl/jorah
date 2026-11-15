// The phone service on loopback (docs/contracts/jorah-phone-v1.md): GET /today and GET /events with
// the read-only token, kept in a file of mode 600 and read on every call so a revoke takes effect
// at once. This is the plugin's only network use, and only to 127.0.0.1. Any problem comes back as
// { ok: false, reason }, never as an empty or zero answer.

import { readFileSync, statSync } from "node:fs";
import { request } from "node:http";
import { Invalid, loadSchema, validate } from "./contract.js";

const MAX_BYTES = 256 * 1024;

export function readToken(file) {
  const info = statSync(file);
  if (info.mode & 0o077) throw new Error("the token file must be readable by its owner only");
  const token = readFileSync(file, "utf8").trim();
  if (!token) throw new Error("the token file is empty");
  return token;
}

export function loopbackUrl(raw) {
  const url = new URL(raw);
  if (url.protocol !== "http:" || !["127.0.0.1", "localhost", "[::1]"].includes(url.hostname) || (url.pathname !== "/" && url.pathname !== "") || url.search || url.username) {
    throw new Error("serviceUrl must be http://127.0.0.1:<port> with no path");
  }
  return url;
}

function get(url, path, token, timeoutMs) {
  return new Promise((resolve, reject) => {
    const req = request({
      host: url.hostname.replace(/^\[|\]$/g, ""), port: url.port || 80, path, method: "GET",
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

export class PhoneClient {
  constructor({ serviceUrl = "http://127.0.0.1:43212", tokenFile, contractsDir, timeoutMs = 5000, logger } = {}) {
    this.tokenFile = tokenFile;
    this.timeoutMs = timeoutMs;
    this.logger = logger;
    this.problem = null;
    try {
      this.url = loopbackUrl(serviceUrl);
      this.schemas = { today: loadSchema(contractsDir, "today"), events: loadSchema(contractsDir, "events") };
    } catch (error) {
      this.problem = String(error?.message ?? error).split("\n")[0].slice(0, 160);
    }
  }

  async call(path, schemaName) {
    if (this.problem) return { ok: false, reason: `the phone link isn't set up: ${this.problem}` };
    let token;
    try {
      token = readToken(this.tokenFile);
    } catch (error) {
      this.logger?.warn?.(`jorah-proactive: phone token: ${error?.code ?? error?.message}`);
      return { ok: false, reason: "the phone service's token can't be read" };
    }
    let answer;
    try {
      answer = await get(this.url, path, token, this.timeoutMs);
    } catch (error) {
      this.logger?.warn?.(`jorah-proactive: ${path.split("?")[0]}: ${String(error?.message ?? error).slice(0, 80)}`);
      return { ok: false, reason: "the phone service isn't answering" };
    }
    if (answer.status !== 200) return { ok: false, reason: `the phone service answered ${answer.status}` };
    try {
      return { ok: true, body: validate(this.schemas[schemaName], JSON.parse(answer.body)) };
    } catch (error) {
      this.logger?.warn?.(`jorah-proactive: ${path.split("?")[0]} failed its schema${error instanceof Invalid ? ` (${error.path})` : ""}`);
      return { ok: false, reason: "the phone service's answer failed its check" };
    }
  }

  today() {
    return this.call("/today", "today");
  }

  events(since, limit = 200) {
    const q = new URLSearchParams({ since: new Date(since).toISOString(), limit: String(Math.min(200, Math.max(1, limit))) });
    return this.call(`/events?${q}`, "events");
  }
}
