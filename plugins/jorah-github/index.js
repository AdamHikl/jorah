// OpenClaw plugin: Jorah's GitHub tools. Push and pull request wait for Adam's approval; sync and
// clone only read. Plain object entry, the same shape definePluginEntry returns, so it needs no
// build or install.

import { branchReport, changedFiles, check, cloneFlow, describe, describeWithFiles, listRepos, logProjectPush, prFlow, projectPushBlock, pushFlow, settings, standingGrant, syncFlow } from "./github.js";
import { cloneResult, errorResult, reportResult, syncResult } from "./shape.js";

const TOOLS = new Set(["github_push_branch", "github_open_pr"]);
const text = (t, details = {}) => ({ content: [{ type: "text", text: t }], details });
const firstLine = (error) => String(error?.message ?? error).split("\n")[0];
const LIST_MS = 20000;

// Only an exact call to one of these tools. A call through the tool-search wrapper (tool_call in
// OpenClaw 2026.10.9, dispatch_action from 2026.10.33) runs this hook again on the inner tool with
// its real name, so the wrapper itself is left alone; a
// search whose text mentions a tool name is not a call (2026-11-10: that produced an empty prompt).
function targetTool(event) {
  return TOOLS.has(event?.toolName) ? { name: event.toolName, params: event.params ?? {} } : null;
}

function complete(params) {
  return typeof params?.project === "string" && params.project.length > 0 && typeof params?.branch === "string" && params.branch.length > 0;
}

export default {
  id: "jorah-github",
  name: "Jorah GitHub",
  description: "Clone and sync Adam's repos; push jorah/* branches and open draft pull requests, on Adam's approval.",
  register(api) {
    const config = () => settings(api.pluginConfig ?? {});

    // The commit each push card showed, so the push sends exactly that (project + branch -> head).
    const shown = new Map();
    // Pushes let through by level 2's standing grant (project + branch -> files), for the digest.
    const granted = new Map();
    const listed = new Map(); // project + branch -> the card's file list, for the push log

    // The card lists the files the branch changes. Listing is best effort: if it fails, the card
    // says why and still asks. Never longer than LIST_MS, so a slow disk can't stall the turn.
    async function listing(name, p, cfg) {
      try {
        const target = check(cfg, p);
        const work = changedFiles(cfg, target, { base: p.base, pushed: name === "github_open_pr" });
        const late = new Promise((_, reject) => setTimeout(() => reject(new Error("took too long")), LIST_MS).unref?.());
        return await Promise.race([work, late]);
      } catch (error) {
        return { error: firstLine(error) };
      }
    }

    // Every push and pull request waits for Adam. Fails closed: a hook error blocks the call.
    api.on("before_tool_call", async (event, ctx) => {
      const hit = targetTool(event);
      if (!hit) return undefined;
      // Never ask Adam to approve something the prompt can't describe.
      if (!complete(hit.params)) return { block: true, blockReason: "jorah-github: project and branch are required." };
      const cfg = config();
      // Project mode: a push the runner has blocked is refused before Adam is asked. A name or
      // folder that fails check() still gets a card here and is refused by the tool itself.
      let blocked = null;
      try {
        blocked = projectPushBlock(cfg, check(cfg, hit.params));
      } catch {
        blocked = null;
      }
      if (blocked) return { block: true, blockReason: `jorah-github: ${blocked}` };
      const files = await listing(hit.name, hit.params, cfg);
      const key = `${hit.params.project}\0${hit.params.branch}`;
      if (hit.name === "github_push_branch") {
        if (files.head) shown.set(key, files.head);
        else shown.delete(key);
        if (files.head) listed.set(key, files);
        // Level 2 (WS5): no card when every invariant holds now; the push sends exactly this head.
        let grant = { ok: false };
        try { grant = await standingGrant(cfg, check(cfg, hit.params), files); } catch { grant = { ok: false }; }
        if (grant.ok) {
          granted.set(key, true);
          api.logger.info(`jorah-github: ${grant.project} pushes ${hit.params.branch} under the standing grant`);
          return undefined;
        }
        granted.delete(key);
      }
      const base = describeWithFiles(describe(hit.name, hit.params, cfg), files);
      let description = ctx?.requester?.channel === "voice"
        ? `Say 'yes, go ahead' or tap here.\n${base}`
        : base;
      if (description.length > 512) description = `${description.slice(0, 511)}…`;
      return {
        requireApproval: {
          title: hit.name === "github_open_pr" ? "Jorah wants to open a pull request" : "Jorah wants to push to GitHub",
          description,
          severity: "critical",
          allowedDecisions: ["allow-once", "deny"],
          timeoutMs: 10 * 60 * 1000,
          pluginId: "jorah-github",
        },
      };
    });

    const params = {
      type: "object",
      additionalProperties: false,
      required: ["project", "branch"],
      properties: {
        project: { type: "string", description: "Folder name under ~/work, which is the repo's name, e.g. robot_tour" },
        branch: { type: "string", description: "Local branch, must start with jorah/" },
      },
    };

    api.registerTool({
      name: "github_list_repos",
      // Visible to the model directly, not behind tool search: saves a search step and a failed
      // direct try per GitHub turn (measured 2026-11-11). Needs main's allow list entry.
      catalogMode: "direct-only",
      description: "List Adam's GitHub repos (name, description, private or public), most recently changed first. Read-only, no approval. Use it to find a repo by what it's about, or to match a misheard or misspelt name before github_clone.",
      parameters: { type: "object", additionalProperties: false, properties: {} },
      async execute() {
        try {
          const repos = await listRepos(config());
          const lines = repos.map((r) => `${r.name}${r.private ? " (private)" : ""}${r.description ? ` - ${r.description}` : ""}`);
          return text(`${repos.length} repos:\n${lines.join("\n")}`, { ok: true, repos });
        } catch (error) {
          return text(`Couldn't list repos: ${firstLine(error)}`, { ok: false });
        }
      },
    });

    api.registerTool({
      name: "github_clone",
      // Visible to the model directly, not behind tool search: saves a search step and a failed
      // direct try per GitHub turn (measured 2026-11-11). Needs main's allow list entry.
      catalogMode: "direct-only",
      description: "Clone one of Adam's GitHub repos into ~/work/<repo> (read-only, no approval needed), with remote `github` set up for Claude Code. Refuses if the folder exists: use github_sync then.",
      parameters: {
        type: "object",
        additionalProperties: false,
        required: ["repo"],
        properties: { repo: { type: "string", description: "Repo name, e.g. robot_tour (or AdamHikl/robot_tour)" } },
      },
      async execute(_id, p) {
        try {
          const { target, synced, cloned } = await cloneFlow(config(), p?.repo);
          api.logger.info(`jorah-github: cloned ${target.repo} into ~/work/${target.project}`);
          const r = cloneResult(target, synced, cloned);
          return text(r.text, r.details);
        } catch (error) {
          api.logger.warn(`jorah-github: clone refused or failed: ${firstLine(error)}`);
          const r = errorResult("Clone didn't happen", error);
          return text(r.text, r.details);
        }
      },
    });

    api.registerTool({
      name: "github_push_branch",
      // Visible to the model directly, not behind tool search: saves a search step and a failed
      // direct try per GitHub turn (measured 2026-11-11). Needs main's allow list entry.
      catalogMode: "direct-only",
      description: "Push a jorah/<task> branch from ~/work/<project> to its GitHub repo. Adam approves each push. Never pushes main or forces; refuses a repo whose rulesets aren't set up yet.",
      parameters: params,
      async execute(_id, p) {
        try {
          const key = `${p?.project}\0${p?.branch}`;
          const approvedHead = shown.get(key);
          shown.delete(key);
          const byGrant = granted.get(key) === true;
          granted.delete(key);
          const files = listed.get(key);
          listed.delete(key);
          const cfg = config();
          const { target, mirrored, result } = await pushFlow(cfg, p, { approvedHead });
          api.logger.info(`jorah-github: pushed ${result.pushed} at ${mirrored.head.slice(0, 7)}`);
          try {
            logProjectPush(cfg, target, { head: mirrored.head, base: files?.base, files: files?.files ?? [], by: byGrant ? "standing grant" : "Adam's card" });
          } catch (error) {
            api.logger.warn(`jorah-github: push log not written: ${firstLine(error)}`);
          }
          return text(`Pushed ${target.branch} to ${target.repo} (${mirrored.head.slice(0, 7)}). Commits:\n${mirrored.log}`, { ok: true, ...result });
        } catch (error) {
          api.logger.warn(`jorah-github: push refused or failed: ${firstLine(error)}`);
          return text(`Push didn't happen: ${firstLine(error)}`, { ok: false });
        }
      },
    });

    api.registerTool({
      name: "github_sync",
      // Visible to the model directly, not behind tool search: saves a search step and a failed
      // direct try per GitHub turn (measured 2026-11-11). Needs main's allow list entry.
      catalogMode: "direct-only",
      description: "Fetch the latest branches of ~/work/<project>'s GitHub repo into Jorah's local mirror (read-only, no approval needed). Afterwards a Claude Code session in that project runs `git fetch github` and works from github/main.",
      parameters: {
        type: "object",
        additionalProperties: false,
        required: ["project"],
        properties: { project: { type: "string", description: "Folder name under ~/work, e.g. threadfolio" } },
      },
      async execute(_id, p) {
        try {
          const { target, synced } = await syncFlow(config(), p?.project);
          api.logger.info(`jorah-github: synced ${target.repo} (${synced.branches.length} branches)`);
          const r = syncResult(target, synced);
          return text(r.text, r.details);
        } catch (error) {
          api.logger.warn(`jorah-github: sync refused or failed: ${firstLine(error)}`);
          const r = errorResult("Sync didn't happen", error);
          return text(r.text, r.details);
        }
      },
    });

    api.registerTool({
      name: "github_branch_report",
      // Visible to the model directly, like the other GitHub tools. Needs main's allow list entry.
      catalogMode: "direct-only",
      description: "Facts about a jorah/<task> branch in ~/work/<project>, without reading its files: head, last commit time, commits ahead of and behind GitHub's default branch (as of the last github_sync), the changed file paths, and whether it's pushed. Read-only, no approval. Use it to check what a Claude Code job left, instead of retelling its report.",
      parameters: params,
      async execute(_id, p) {
        try {
          const facts = await branchReport(config(), p);
          const r = reportResult(facts);
          return text(r.text, r.details);
        } catch (error) {
          api.logger.warn(`jorah-github: branch report refused or failed: ${firstLine(error)}`);
          const r = errorResult("No branch report", error);
          return text(r.text, r.details);
        }
      },
    });

    api.registerTool({
      name: "github_open_pr",
      // Visible to the model directly, not behind tool search: saves a search step and a failed
      // direct try per GitHub turn (measured 2026-11-11). Needs main's allow list entry.
      catalogMode: "direct-only",
      description: "Open a draft pull request on GitHub from a jorah/<task> branch already pushed. Adam approves each one. Jorah never merges.",
      parameters: {
        ...params,
        required: ["project", "branch", "title"],
        properties: { ...params.properties, title: { type: "string" }, body: { type: "string" }, base: { type: "string", description: "Target branch; the repo's default if left out" } },
      },
      async execute(_id, p) {
        try {
          const { target, pr } = await prFlow(config(), p);
          api.logger.info(`jorah-github: opened PR #${pr.number} on ${target.repo}`);
          return text(`Opened draft pull request #${pr.number} on ${target.repo} into ${pr.base}: ${pr.url}`, { ok: true, ...pr });
        } catch (error) {
          api.logger.warn(`jorah-github: pull request refused or failed: ${firstLine(error)}`);
          return text(`Pull request not opened: ${firstLine(error)}`, { ok: false });
        }
      },
    });
  },
};
