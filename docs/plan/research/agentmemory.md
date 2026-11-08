# agentmemory (rohitg00/agentmemory) as Jorah's memory

Evaluated 2026-11-08 for Adam, who likes it. Research by Antigravity (Gemini 4 Argon High) from the
repo, npm and GitHub APIs; Claude checked the deciding claims against the source and the GitHub API.
Argon's popularity numbers were wrong and are corrected here.

## What it is

A self-hosted memory service for coding agents, Apache-2.0, v0.9.32 (2026-11-04), about 30,000 stars,
2,700 forks, 64 contributors (the author has 523 commits), weekly releases. It runs as three
processes: the `iii` Rust engine, two Rust workers fetched from `api.workers.iii.dev`, and a Node
worker. It stores memory in a local `state_store.db`, searches with BM25 plus optional in-process
embeddings (`all-MiniLM-L6-v2` via ONNX, no extra port) and a knowledge graph, and consolidates with
summaries, decay and forgetting. With no LLM provider set it makes no LLM calls; with Anthropic set it
adds about one call per saved turn plus summaries every 2 hours. No telemetry found.

It ships a native OpenClaw plugin [checked in source]: `agentmemory connect openclaw` sets
`plugins.slots.memory = "agentmemory"` (it refuses without `--force` if another memory plugin is
selected) and `allowConversationAccess`. Before every turn it injects up to ~2,000 tokens of recalled
memory, labelled "untrusted background"; after every turn it saves the user and assistant messages.

## What it would add

- Semantic recall that works under Jorah's firewall, because embeddings run in-process. Today
  Jorah's memory search is keyword-only.
- Automatic recall before every turn, deduplication, versioning, decay.
- A benchmark claim of 84.7% recall@5 against 72.1% for plain grep (their own benchmark, unchecked).

## Why not now

1. **It replaces `memory-core`.** Jorah's Markdown memory, `MEMORY.md` and nightly Dreaming run on
   `memory-core`, which owns the memory slot. Taking the slot means migrating or losing that. The only
   way to keep both is MCP-only, which loses the automatic recall that is its main draw.
2. **Supply chain.** Two Rust workers come from `api.workers.iii.dev`, outside npm, with no publish
   date or checksum we can check, so the 7-day rule can't be applied. The current release and the
   `iii` engine are 3 days old today; v0.9.31 would be the pin.
3. **Memory poisoning before the hard gate.** Every turn is saved, including text Jorah quoted from web
   pages, and recalled into later turns automatically. Labelling it untrusted helps, but there is no
   filter. P5's hard-gate tests (SEC-T24 and the injection tests) haven't run yet.
4. **Another plaintext copy of every conversation**, in a second store that backups and deletion
   requests must also cover. Fine on-box, but it's more to protect.
5. **Weight.** Three daemons, about 350 MiB RAM idle, three ports to move into the firewall's ranges,
   and a second consolidation system competing with Dreaming.

## Recommendation

Not as Jorah's memory now. It is an optional plugin in the roadmap, P5b (`10-roadmap.md`). Two steps instead, in order:

1. **Get semantic search in OpenClaw's own memory** (the planned NAT networking fix in the runbook's
   open list), which removes the main gap with no new service.
2. **If recall still feels weak after that,** trial agentmemory on the `jorah-dev` profile after P5:
   pinned to a release at least 7 days old, keyless (`LLM_PROVIDER` unset), local embeddings, ports
   inside 43255-47350, `AGENTMEMORY_SECRET` set, the Rust workers pre-fetched and recorded. Run it
   alongside `memory-core` through MCP first, compare recall on the same questions for two weeks,
   then decide on the slot.
