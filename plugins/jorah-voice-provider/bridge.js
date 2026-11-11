// The link between OpenClaw's Talk relay and jorah-voice. No OpenClaw imports, so it tests alone.
//
// jorah-voice does the whole turn itself: it recognises speech, sends the words to Jorah's main
// session through the Gateway's Chat Completions endpoint, and speaks the reply as it streams.
// This bridge only moves audio and says what state the call is in. It sends no final transcripts,
// because the relay would append them to the session that jorah-voice has already written to.

import { readFileSync, statSync } from "node:fs";

export const DEFAULTS = Object.freeze({
  url: "ws://127.0.0.1:43210",
  tokenFile: "/home/jorah/.config/jorah-voice/token",
  readyTimeoutMs: 15000,
});

export const RATE = 24000;

export function settings(providerConfig = {}) {
  const url = typeof providerConfig.url === "string" ? providerConfig.url : DEFAULTS.url;
  const parsed = new URL(url);
  // Loopback only: the token is full access to Jorah's voice.
  if (parsed.protocol !== "ws:" || !["127.0.0.1", "[::1]", "localhost"].includes(parsed.hostname)) {
    throw new Error("jorah-local: url must be ws:// on loopback");
  }
  return {
    url,
    tokenFile: typeof providerConfig.tokenFile === "string" ? providerConfig.tokenFile : DEFAULTS.tokenFile,
    readyTimeoutMs: Number.isFinite(providerConfig.readyTimeoutMs) ? providerConfig.readyTimeoutMs : DEFAULTS.readyTimeoutMs,
  };
}

export function readToken(path) {
  const mode = statSync(path).mode;
  if (mode & 0o077) throw new Error("jorah-local: token file must be readable by its owner only");
  const token = readFileSync(path, "utf8").trim();
  if (token.length < 32) throw new Error("jorah-local: token file holds no token");
  return token;
}

export function tokenPresent(providerConfig) {
  try {
    readToken(settings(providerConfig).tokenFile);
    return true;
  } catch {
    return false;
  }
}

export function createJorahBridge(req, { WebSocketImpl = globalThis.WebSocket, readTokenImpl = readToken } = {}) {
  const config = settings(req.providerConfig);
  let ws = null;
  let open = false;
  let closing = false;
  let finished = false;
  let replying = false;

  const finish = (reason) => {
    if (finished) return;
    finished = true;
    open = false;
    req.onClose?.(reason);
  };

  const handle = (raw) => {
    if (typeof raw !== "string") {
      req.onAudio(Buffer.from(raw instanceof ArrayBuffer ? new Uint8Array(raw) : raw));
      return;
    }
    let message;
    try {
      message = JSON.parse(raw);
    } catch {
      return;
    }
    switch (message.type) {
      case "heard":
        req.onTranscript?.("user", String(message.text ?? ""), false);
        break;
      case "reply":
        replying = true;
        req.onTranscript?.("assistant", String(message.text ?? ""), false);
        break;
      case "cut":
        replying = false;
        req.onClearAudio("barge-in");
        req.onResponseDone?.({ status: "cancelled", reason: "barge-in" });
        break;
      case "state":
        if ((message.state === "listening" || message.state === "standby") && replying) {
          replying = false;
          req.onResponseDone?.({ status: "completed" });
        }
        break;
      case "closed":
        // jorah-voice ended the call: only its 30-minute limit, since Talk sends client_ends.
        // Goodbye and thanks put it on standby instead, until Talk hangs up.
        closing = true;
        finish("completed");
        break;
      default:
        break;
    }
  };

  return {
    supportsToolResultContinuation: false,
    supportsToolResultSuppression: false,
    handlesInputAudioBargeIn: true,

    connect() {
      const token = readTokenImpl(config.tokenFile);
      return new Promise((resolve, reject) => {
        let ready = false;
        const timer = setTimeout(() => {
          if (!ready) {
            reject(new Error("jorah-local: jorah-voice did not get ready in time"));
            try { ws?.close(); } catch {}
          }
        }, config.readyTimeoutMs);
        ws = new WebSocketImpl(config.url);
        ws.binaryType = "arraybuffer";
        ws.addEventListener("open", () => {
          // client_ends: only Talk hangs up. The iPhone app takes a session closed from the PC for a
          // dropped line, retries, then falls back to Apple speech and the system voice (2026-11-11).
          ws.send(JSON.stringify({ type: "hello", token, barge_in: true, input_rate: RATE, client_ends: true }));
        });
        ws.addEventListener("message", (event) => {
          if (!ready) {
            let message = null;
            try { message = typeof event.data === "string" ? JSON.parse(event.data) : null; } catch {}
            if (message?.type !== "ready") return;
            clearTimeout(timer);
            if (message.sample_rate !== RATE) {
              reject(new Error(`jorah-local: jorah-voice speaks at ${message.sample_rate} Hz, Talk needs ${RATE}`));
              try { ws.close(); } catch {}
              return;
            }
            ready = true;
            open = true;
            req.onReady?.();
            resolve();
            return;
          }
          handle(event.data);
        });
        ws.addEventListener("error", () => {
          if (!ready) {
            clearTimeout(timer);
            reject(new Error("jorah-local: can't reach jorah-voice"));
          } else {
            req.onError?.(new Error("jorah-local: connection to jorah-voice failed"));
          }
        });
        ws.addEventListener("close", (event) => {
          clearTimeout(timer);
          if (!ready) {
            // 4409: another session (mac-ear) is open. 4401: token refused.
            reject(new Error(event.code === 4409 ? "jorah-local: another voice session is open" : `jorah-local: jorah-voice closed (${event.code})`));
            return;
          }
          finish(closing ? "completed" : "error");
        });
      });
    },

    sendAudio(audio) {
      if (open && ws) ws.send(audio);
    },

    setMediaTimestamp() {},

    handleBargeIn() {
      if (open && ws) ws.send(JSON.stringify({ type: "interrupt" }));
    },

    submitToolResult() {
      // No tools: jorah-voice asks Jorah's main session itself.
    },

    acknowledgeMark() {},

    close() {
      closing = true;
      open = false;
      try { ws?.close(1000, "talk closed"); } catch {}
      finish("completed");
    },

    isConnected() {
      return open;
    },
  };
}
