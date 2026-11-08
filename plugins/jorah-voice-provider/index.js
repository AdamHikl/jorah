// OpenClaw plugin: registers "jorah-local" as a realtime Talk provider on the Gateway relay.
// Plain object entry, the same shape definePluginEntry returns, so it needs no build or install.

import { createJorahBridge, RATE, tokenPresent } from "./bridge.js";

const PCM16 = { encoding: "pcm16", sampleRateHz: RATE, channels: 1 };

export default {
  id: "jorah-voice-provider",
  name: "Jorah local voice",
  description: "Talk through jorah-voice on the PC. No audio leaves it.",
  configSchema: { type: "object", additionalProperties: false },
  register(api) {
    api.registerRealtimeVoiceProvider({
      id: "jorah-local",
      label: "Jorah (local voice on the PC)",
      capabilities: {
        transports: ["gateway-relay"],
        inputAudioFormats: [PCM16],
        outputAudioFormats: [PCM16],
        supportsBargeIn: true,
        handlesInputAudioBargeIn: true,
        supportsToolCalls: false,
      },
      isConfigured: ({ providerConfig }) => tokenPresent(providerConfig),
      createBridge: (req) => createJorahBridge(req),
    });
  },
};
