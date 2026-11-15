// Runs gog (v0.48.0) read-only for the Google readers. No shell: one fixed binary, fixed flags first
// (--readonly --no-input --json and a gog account alias), then the command, then "--" before any
// value the model chose, so a value can never be read as a flag. GOG_READONLY=1 as well, so gog
// refuses any mutating request before it leaves the machine, on top of the read-only grant.
// gog's stderr is only classified, never passed on or logged: it can hold addresses.

import { execFile } from "node:child_process";
import { readFileSync, statSync } from "node:fs";

const MAX_BUFFER = 4 * 1024 * 1024;
export const ALIAS = /^[a-z0-9][a-z0-9._-]{0,39}$/;
const SIGNED_OUT = /invalid_grant|token (has been )?(expired|revoked)|unauthori[sz]ed|\b401\b|no (refresh )?token|re-?auth|login required|not authenticated|no account|keyring/i;

export function readSecretFile(file) {
  const info = statSync(file);
  if (info.mode & 0o077) throw new Error("must be readable by its owner only");
  const value = readFileSync(file, "utf8").replace(/\r?\n$/, "");
  if (!value) throw new Error("is empty");
  return value;
}

export function classify(error, stderr = "") {
  if (error?.code === "ENOENT") return { status: "not_set_up", reason: "gog isn't installed on the PC" };
  if (error?.killed || error?.signal === "SIGTERM") return { status: "unavailable", reason: "Google didn't answer in time" };
  if (SIGNED_OUT.test(String(stderr))) return { status: "signed_out", reason: "the Google sign-in needs renewing: Adam runs scripts/pc/google-grant.sh" };
  return { status: "unavailable", reason: "Google couldn't be read just now" };
}

/**
 * @param {{gogPath: string, gogHome: string, passwordFile: string, account: string, timeoutMs?: number}} cfg
 * @param {string[]} command  e.g. ["calendar", "events", "--today"]
 * @param {string[]} [values] model-chosen values, passed after "--"
 * @returns {Promise<{ok: true, json: any} | {ok: false, status: string, reason: string}>}
 */
export function runGog(cfg, command, values = []) {
  if (!ALIAS.test(String(cfg.account ?? ""))) return Promise.resolve({ ok: false, status: "not_set_up", reason: "no gog account alias is configured" });
  let password;
  try {
    password = readSecretFile(cfg.passwordFile);
  } catch {
    return Promise.resolve({ ok: false, status: "not_set_up", reason: "the Google keyring password file can't be read" });
  }
  const argv = ["--readonly", "--no-input", "--json", "--account", cfg.account, ...command, ...(values.length ? ["--", ...values] : [])];
  const env = {
    GOG_HOME: cfg.gogHome,
    GOG_KEYRING_BACKEND: "file",
    GOG_KEYRING_PASSWORD: password,
    GOG_READONLY: "1",
    HOME: cfg.gogHome,
    PATH: "/usr/bin:/bin",
    LANG: "C.UTF-8",
  };
  return new Promise((resolve) => {
    execFile(cfg.gogPath, argv, { env, timeout: cfg.timeoutMs ?? 20000, maxBuffer: MAX_BUFFER, windowsHide: true }, (error, stdout, stderr) => {
      if (error) return resolve({ ok: false, ...classify(error, stderr) });
      try {
        resolve({ ok: true, json: JSON.parse(stdout) });
      } catch {
        resolve({ ok: false, status: "unavailable", reason: "gog's answer wasn't JSON" });
      }
    });
  });
}
