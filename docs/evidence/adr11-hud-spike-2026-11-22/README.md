# ADR 0011 spike: does a plugin hook see the sending device's id? (2026-11-22)

**Answer:** No. OpenClaw 2026.10.9 verifies the paired device's id at `connect` and keeps it for
each `chat.send` turn (`ApprovalReviewerDeviceId`), but it never puts it in the context or event
of `before_tool_call` or `before_agent_run`. So ADR 0011's option C isn't buildable on this
version, and option A stays.

**Tier reached:** source read. No Gateway was started, no profile created, nothing on the PC
touched. The scratch run was skipped because the source settles the question: both the runtime
builders and the public SDK types leave the field out.

**Source:** `/opt/homebrew/lib/node_modules/openclaw/dist` on the Mac, `package.json` version
`2026.10.9` (the version Jorah runs, per the repo README; `config/versions.env` does not exist yet on this branch). File names below carry the build hash of that
install; after an upgrade, search by function name.

## Trace

| Step | File | Function or field | Claim |
|---|---|---|---|
| 1 | `message-handler-a7VR9SDC.mjs` | device check at `connect`: `deriveDeviceIdFromPublicKey`, `device-id-mismatch`, `device-signature-stale`, `device-nonce-mismatch`, `resolveDeviceSignaturePayloadVersion` | The device id must match the public key, and the signature must cover the Gateway's fresh nonce. Can't be forged without the private key [verified: source read] |
| 2 | `gateway-client-identity-C-9Xwi8i.mjs` | `resolveChatSendCallerContext` | Sets `ApprovalReviewerDeviceId = client.connect.device.id`; sets `SenderId = clientInfo.id` (the client's self-declared name) unless the client is an operator UI or synthetic [verified: source read] |
| 3 | `chat-send-handler-B0jivtwJ.mjs` | `chat.send` ctx | Spreads `resolveChatSendCallerContext(client, request.clientInfo, originatingChannel)` into the turn's ctx [verified: source read] |
| 4 | `get-reply-XXltnwYw.mjs`, `reply-tool-authority-DTs080TY.mjs` | `approvalReviewerDeviceId` | Copied into the run's execution snapshot [verified: source read] |
| 5 | `agent-tools-Bpi7xWYy.mjs`, `builtin-openclaw-BxzDR6yL.mjs` | internal `hookContext` / `toolHookContext` | Carries `approvalReviewerDeviceId` next to `requester`. `requester` holds only `channel`, `accountId`, `senderId`, `senderIsOwner`, `roleIds` (same in `host-capability-DhglHzwG.mjs`) [verified: source read] |
| 6 | `agent-tools.before-tool-call-CQkX3nOj.mjs` | `buildToolContext`, then `hookRunner.runBeforeToolCall` | The context handed to plugins copies `toolName`, `toolKind`, `toolInputKind`, `agentId`, `sessionKey`, `sessionId`, `runId`, `abortSignal`, `trace`, `toolCallId`, `channelId`, `requester`. Not the device id. The internal one is used only to route approval cards (`approvalReviewerDeviceIds`) [verified: source read] |
| 7 | `before-agent-run-0bHKoKHh.mjs`, `hook-context-DTNlPqW5.mjs`, `hook-agent-context-vC-cM68i.mjs`, call sites in `cli-runner-*`, `worker-turn-execution-*`, `builtin-openclaw-*` | `runBeforeAgentRunGate`, `buildAgentHookContext` | Event: `prompt`, `messages`, `systemPrompt`, `channelId`, `accountId`, `senderId`, `senderIsOwner`. Context: no device field [verified: source read] |
| 8 | `config-contracts-DzLaG7FV.d.ts` | `PluginHookToolRequesterContext`, `PluginHookToolContext`, `PluginHookAgentContext`, `PluginHookBeforeAgentRunEvent`, every `src/plugins/hook-*.types` region | No "device" anywhere in the hook type regions [verified: source read] |
| 9 | `openai-http-BnzIil8F.mjs`, `http-auth-utils-xEG2Jlr0.mjs`, `openai-tool-choice-dD18Tbw2.mjs` | `/v1/chat/completions` | `messageChannel` from `x-openclaw-message-channel`, default `webchat`; `senderIsOwner` true when the shared secret grants `operator.admin`; no sender id, no device [verified: source read] |
| 10 | `message-channel-AvA3r_Xp.mjs`, `client-info-BgcoFakQ.mjs` | `isOperatorUiClient` | True for `openclaw-control-ui`, `openclaw-browser-copilot`, `openclaw-tui`; those get no `SenderId` [verified: source read] |
| 11 | `message-channel-constants-B3vfipkP.mjs` | `INTERNAL_MESSAGE_CHANNEL` | `"webchat"`: the channel for every `chat.send` turn [verified: source read] |
| 12 | `clients/mac-hud/Sources/JorahHUD/Gateway/GatewayClient.swift` (this repo) | connect params | The HUD connects as `client.id: "gateway-client"`, `mode: "ui"`, role `operator`, with a signed device block [verified: source read] |

## What each caller shows a hook

| Caller | `channel` | `senderId` | `senderIsOwner` | Device id in hook |
|---|---|---|---|---|
| HUD `chat.send` | `webchat` | per step 2, its self-declared `client.id`; P5.4 observed none. Caller-chosen either way | owner if operator with scope | no |
| Control UI `chat.send` | `webchat` | none | owner if admin operator | no (it has its own paired id) |
| Chat Completions | header, default `webchat` | none | true with admin shared secret | no (no device on HTTP) |

## Open points

- [inference] Step 2 suggests a HUD turn could carry `senderId: "gateway-client"`, while the P5.4
  observation saw no sender id. Either way the guard keeps its card (`typedByOwner` needs no
  sender id outside Telegram), and the value is caller-chosen, so it's no trust signal. A live
  log would settle which, but it doesn't change the answer.
- Re-check after every OpenClaw upgrade: search the dist for `approvalReviewerDeviceId` near
  `buildToolContext` and `buildAgentHookContext`, and for "device" in the plugin hook types.

No tokens, device ids or secrets were read or recorded.
