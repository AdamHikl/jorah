import { test } from "node:test";
import assert from "node:assert/strict";
import { record } from "../index.js";

const ctx = { agentId: "main", sessionKey: "agent:main:main", requester: { channel: "telegram", senderId: "123456789", senderIsOwner: true } };

test("argument values and sender ids stay out of the record by default", () => {
  const r = JSON.stringify(record("before_tool_call", { toolName: "web_fetch", params: { url: "https://example.com/?q=SECRET-CANARY" } }, ctx));
  assert.ok(!r.includes("SECRET-CANARY"));
  assert.ok(!r.includes("123456789"));
  assert.match(r, /"paramKeys":\["url"\]/);
  assert.match(r, /"senderIsOwner":true/);
});

test("the inner tool name of a tool_call wrapper is recorded", () => {
  const r = record("before_tool_call", { toolName: "tool_call", params: { name: "web_search", arguments: { query: "x" } } }, ctx);
  assert.equal(r["param.name"], "web_search");
});

test("results are reduced to their shape and a URL count", () => {
  const r = record("after_tool_call", { toolName: "web_fetch", params: {}, result: { content: [{ type: "text", text: "see https://a.example and https://b.example" }] } }, ctx);
  assert.equal(r.result.urls, 2);
  assert.ok(!JSON.stringify(r).includes("a.example"));
});
