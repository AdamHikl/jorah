// OpenClaw plugin: github_push_branch and github_open_pr for Jorah, each waiting for Adam's approval.
// Plain object entry, the same shape definePluginEntry returns, so it needs no build or install.

import { READ, check, checkProject, describe, mirrorBranch, openPullRequest, pushBranch, repoToken, settings, syncMirror } from "./github.js";

const TOOLS = new Set(["github_push_branch", "github_open_pr"]);
const text = (t, details = {}) => ({ content: [{ type: "text", text: t }], details });

// Only an exact call to one of these tools. A call through the tool-search wrapper (tool_call) runs
// this hook again on the inner tool with its real name, so the wrapper itself is left alone; a
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
  description: "Push jorah/* branches and open pull requests, on Adam's approval.",
  register(api) {
    const config = () => settings(api.pluginConfig ?? {});

    // Every call waits for Adam. Fails closed: a hook error blocks the call.
    api.on("before_tool_call", (event) => {
      const hit = targetTool(event);
      if (!hit) return undefined;
      // Never ask Adam to approve something the prompt can't describe.
      if (!complete(hit.params)) return { block: true, blockReason: "jorah-github: project and branch are required." };
      return {
        requireApproval: {
          title: hit.name === "github_open_pr" ? "Jorah wants to open a pull request" : "Jorah wants to push to GitHub",
          description: describe(hit.name, hit.params, config()),
          severity: "warning",
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
        project: { type: "string", description: "Folder name under ~/work, e.g. mizyun-web" },
        branch: { type: "string", description: "Local branch, must start with jorah/" },
      },
    };

    api.registerTool({
      name: "github_push_branch",
      description: "Push a jorah/<task> branch from ~/work/<project> to its GitHub repo. Adam approves each push. Never pushes main or forces.",
      parameters: params,
      async execute(_id, p) {
        try {
          const cfg = config();
          const target = check(cfg, p);
          const mirrored = await mirrorBranch(cfg, target);
          const result = await pushBranch(cfg, { ...target, ...mirrored }, await repoToken(cfg, target.repo));
          api.logger.info(`jorah-github: pushed ${result.pushed} at ${mirrored.head.slice(0, 7)}`);
          return text(`Pushed ${target.branch} to ${target.repo} (${mirrored.head.slice(0, 7)}). Commits:\n${mirrored.log}`, { ok: true, ...result });
        } catch (error) {
          api.logger.warn(`jorah-github: push refused or failed: ${String(error.message).split("\n")[0]}`);
          return text(`Push didn't happen: ${String(error.message).split("\n")[0]}`, { ok: false });
        }
      },
    });

    api.registerTool({
      name: "github_sync",
      description: "Fetch the latest branches of ~/work/<project>'s GitHub repo into Jorah's local mirror (read-only, no approval needed). Afterwards a Claude Code session in that project runs `git fetch github` and works from github/main.",
      parameters: {
        type: "object",
        additionalProperties: false,
        required: ["project"],
        properties: { project: { type: "string", description: "Folder name under ~/work, e.g. threadfolio" } },
      },
      async execute(_id, p) {
        try {
          const cfg = config();
          const target = checkProject(cfg, p?.project);
          const result = await syncMirror(cfg, target, await repoToken(cfg, target.repo, { permissions: READ }));
          api.logger.info(`jorah-github: synced ${target.repo} (${result.branches.length} branches)`);
          return text(`Synced ${target.repo} into the mirror. Branches:\n${result.branches.join("\n")}\nIn ~/work/${target.project}, run \`git fetch github\` to get them.`, { ok: true, ...result });
        } catch (error) {
          return text(`Sync didn't happen: ${String(error.message).split("\n")[0]}`, { ok: false });
        }
      },
    });

    api.registerTool({
      name: "github_open_pr",
      description: "Open a draft pull request on GitHub from a jorah/<task> branch already pushed. Adam approves each one.",
      parameters: {
        ...params,
        required: ["project", "branch", "title"],
        properties: { ...params.properties, title: { type: "string" }, body: { type: "string" }, base: { type: "string", description: "Target branch; the repo's default if left out" } },
      },
      async execute(_id, p) {
        try {
          const cfg = config();
          const target = check(cfg, p);
          const pr = await openPullRequest(cfg, target, p, await repoToken(cfg, target.repo));
          api.logger.info(`jorah-github: opened PR #${pr.number} on ${target.repo}`);
          return text(`Opened draft pull request #${pr.number} on ${target.repo} into ${pr.base}: ${pr.url}`, { ok: true, ...pr });
        } catch (error) {
          return text(`Pull request not opened: ${String(error.message).split("\n")[0]}`, { ok: false });
        }
      },
    });
  },
};
