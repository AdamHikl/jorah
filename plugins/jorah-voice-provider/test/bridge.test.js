import { test } from "node:test";
import assert from "node:assert/strict";
import { createJorahBridge, settings } from "../bridge.js";

class FakeSocket {
  static last = null;
  constructor(url) {
    this.url = url;
    this.sent = [];
    this.listeners = {};
    FakeSocket.last = this;
    queueMicrotask(() => this.emit("open", {}));
  }
  addEventListener(name, fn) { (this.listeners[name] ??= []).push(fn); }
  emit(name, event) { for (const fn of this.listeners[name] ?? []) fn(event); }
  send(data) { this.sent.push(data); }
  close(code = 1000) { this.closed = code; queueMicrotask(() => this.emit("close", { code })); }
  serverSays(message) { this.emit("message", { data: typeof message === "string" ? message : message instanceof ArrayBuffer ? message : JSON.stringify(message) }); }
}

function harness(overrides = {}) {
  const calls = [];
  const req = {
    providerConfig: {},
    onAudio: (b) => calls.push(["audio", b.length]),
    onClearAudio: (r) => calls.push(["clear", r]),
    onTranscript: (role, text, final) => calls.push(["transcript", role, text, final]),
    onResponseDone: (o) => calls.push(["done", o.status]),
    onReady: () => calls.push(["ready"]),
    onClose: (r) => calls.push(["close", r]),
    onError: (e) => calls.push(["error", e.message]),
    ...overrides,
  };
  const bridge = createJorahBridge(req, { WebSocketImpl: FakeSocket, readTokenImpl: () => "t".repeat(40) });
  return { bridge, calls };
}

async function connected() {
  const h = harness();
  const pending = h.bridge.connect();
  await new Promise((r) => setTimeout(r, 0));
  FakeSocket.last.serverSays({ type: "ready", sample_rate: 24000 });
  await pending;
  return h;
}

test("hello asks for 24 kHz in, barge-in, and that only Talk hangs up", async () => {
  await connected();
  const hello = JSON.parse(FakeSocket.last.sent[0]);
  assert.deepEqual(hello, { type: "hello", token: "t".repeat(40), barge_in: true, input_rate: 24000, client_ends: true });
});

test("standby after a reply completes the response and keeps the call open", async () => {
  const { bridge, calls } = await connected();
  FakeSocket.last.serverSays({ type: "reply", text: "Talk soon." });
  FakeSocket.last.serverSays({ type: "standby", reason: "said goodbye" });
  FakeSocket.last.serverSays({ type: "state", state: "standby" });
  assert.deepEqual(calls.slice(1), [
    ["transcript", "assistant", "Talk soon.", false],
    ["done", "completed"],
  ]);
  assert.equal(bridge.isConnected(), true);
});

test("audio flows both ways once ready", async () => {
  const { bridge, calls } = await connected();
  assert.equal(bridge.isConnected(), true);
  bridge.sendAudio(Buffer.alloc(960));
  assert.equal(FakeSocket.last.sent.at(-1).length, 960);
  FakeSocket.last.serverSays(new ArrayBuffer(480));
  assert.deepEqual(calls.at(-1), ["audio", 480]);
});

test("transcripts are never final, so the relay doesn't write them twice", async () => {
  const { calls } = await connected();
  FakeSocket.last.serverSays({ type: "heard", text: "What time is it?" });
  FakeSocket.last.serverSays({ type: "reply", text: "Ten past four." });
  FakeSocket.last.serverSays({ type: "state", state: "listening" });
  assert.deepEqual(calls.slice(1), [
    ["transcript", "user", "What time is it?", false],
    ["transcript", "assistant", "Ten past four.", false],
    ["done", "completed"],
  ]);
});

test("a cut clears playback", async () => {
  const { calls } = await connected();
  FakeSocket.last.serverSays({ type: "reply", text: "A long answer." });
  FakeSocket.last.serverSays({ type: "cut" });
  assert.deepEqual(calls.slice(-2), [["clear", "barge-in"], ["done", "cancelled"]]);
});

test("barge-in from the host is passed on", async () => {
  const { bridge } = await connected();
  bridge.handleBargeIn();
  assert.deepEqual(JSON.parse(FakeSocket.last.sent.at(-1)), { type: "interrupt" });
});

test("jorah-voice closing the call ends the Talk session once", async () => {
  const { calls } = await connected();
  FakeSocket.last.serverSays({ type: "closed", reason: "said thanks" });
  FakeSocket.last.close(1000);
  await new Promise((r) => setTimeout(r, 0));
  assert.deepEqual(calls.filter((c) => c[0] === "close"), [["close", "completed"]]);
});

test("a dropped connection is an error close", async () => {
  const { calls } = await connected();
  FakeSocket.last.emit("close", { code: 1006 });
  assert.deepEqual(calls.at(-1), ["close", "error"]);
});

test("a busy voice service refuses clearly", async () => {
  const h = harness();
  const pending = h.bridge.connect();
  await new Promise((r) => setTimeout(r, 0));
  FakeSocket.last.emit("close", { code: 4409 });
  await assert.rejects(pending, /another voice session is open/);
});

test("the wrong output rate is refused", async () => {
  const h = harness();
  const pending = h.bridge.connect();
  await new Promise((r) => setTimeout(r, 0));
  FakeSocket.last.serverSays({ type: "ready", sample_rate: 16000 });
  await assert.rejects(pending, /Talk needs 24000/);
});

test("only loopback is allowed", () => {
  assert.throws(() => settings({ url: "ws://100.115.240.14:43210" }), /loopback/);
  assert.throws(() => settings({ url: "wss://rocket.tail1574a5.ts.net:43211" }), /loopback/);
  assert.equal(settings({}).url, "ws://127.0.0.1:43210");
});
