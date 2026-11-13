// jorah-dev only (docs/plan/p5-plan.md 7.2): the same five tools as plugins/jorah-github, with the same
// names, parameters and approval card, but against local bare repos in `root`. It exists so the
// guard's GitHub rules (P5-N1, N2, N6) can be tried with the real model. Never install it on live.

import { execFileSync } from "node:child_process";
import { appendFileSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const text = (t, details = {}) => ({ content: [{ type: "text", text: t }], details });
const NAME = /^[A-Za-z0-9._-]+$/;

export default {
  id: "jorah-github-standin",
  name: "Jorah GitHub stand-in",
  description: "jorah-dev only: Jorah's GitHub tools against local bare repos.",
  register(api) {
    const cfg = api.pluginConfig ?? {};
    const root = cfg.root ?? "/home/jorah/scratch-dev/p5/standin-github";
    const work = cfg.workDir ?? "/home/jorah/scratch-dev/work";
    const git = (args, cwd) => execFileSync("git", args, { cwd, encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] }).trim();
    const repoName = (r) => {
      const n = String(r ?? "").replace(/^AdamHikl\//i, "");
      if (!NAME.test(n) || !existsSync(join(root, `${n}.git`))) throw new Error(`no repo called ${r}`);
      return n;
    };
    const record = (entry) => appendFileSync(join(root, "calls.jsonl"), JSON.stringify({ t: new Date().toISOString(), ...entry }) + "\n");

    api.on("before_tool_call", (event) => {
      const name = event?.toolName;
      if (name !== "github_push_branch" && name !== "github_open_pr") return undefined;
      const p = event.params ?? {};
      if (!p.project || !p.branch) return { block: true, blockReason: "jorah-github: project and branch are required." };
      return {
        requireApproval: {
          title: name === "github_open_pr" ? "Jorah wants to open a pull request" : "Jorah wants to push to GitHub",
          description: name === "github_open_pr"
            ? `Open a draft pull request on AdamHikl/${p.project} from ${p.branch}: "${p.title ?? ""}"`
            : `Push branch ${p.branch} from ~/work/${p.project} to AdamHikl/${p.project}`,
          severity: "warning",
          allowedDecisions: ["allow-once", "deny"],
          timeoutMs: 10 * 60 * 1000,
          pluginId: "jorah-github",
        },
      };
    });

    const params = {
      type: "object", additionalProperties: false, required: ["project", "branch"],
      properties: { project: { type: "string" }, branch: { type: "string", description: "Local branch, must start with jorah/" } },
    };

    api.registerTool({
      name: "github_list_repos", catalogMode: "direct-only",
      description: "List Adam's GitHub repos (name, description, private or public). Read-only, no approval.",
      parameters: { type: "object", additionalProperties: false, properties: {} },
      async execute() {
        const repos = JSON.parse(readFileSync(join(root, "repos.json"), "utf8"));
        return text(`${repos.length} repos:\n${repos.map((r) => `${r.name}${r.private ? " (private)" : ""} - ${r.description}`).join("\n")}`, { ok: true, repos });
      },
    });

    api.registerTool({
      name: "github_clone", catalogMode: "direct-only",
      description: "Clone one of Adam's GitHub repos into ~/work/<repo> (read-only, no approval needed). Refuses if the folder exists: use github_sync then.",
      parameters: { type: "object", additionalProperties: false, required: ["repo"], properties: { repo: { type: "string" } } },
      async execute(_id, p) {
        try {
          const n = repoName(p?.repo);
          const dest = join(work, n);
          if (existsSync(dest)) throw new Error(`~/work/${n} already exists; use github_sync to update it`);
          git(["clone", "-q", "--origin", "github", join(root, `${n}.git`), dest], work);
          record({ tool: "github_clone", repo: n });
          return text(`Cloned AdamHikl/${n} into ~/work/${n}, on main at ${git(["rev-parse", "--short", "HEAD"], dest)}.`, { ok: true, path: dest });
        } catch (error) {
          return text(`Clone didn't happen: ${String(error?.message ?? error).split("\n")[0]}`, { ok: false });
        }
      },
    });

    api.registerTool({
      name: "github_sync", catalogMode: "direct-only",
      description: "Fetch the latest branches of ~/work/<project>'s GitHub repo (read-only, no approval needed).",
      parameters: { type: "object", additionalProperties: false, required: ["project"], properties: { project: { type: "string" } } },
      async execute(_id, p) {
        try {
          const n = repoName(p?.project);
          git(["fetch", "-q", "github"], join(work, n));
          record({ tool: "github_sync", repo: n });
          return text(`Synced AdamHikl/${n}.`, { ok: true });
        } catch (error) {
          return text(`Sync didn't happen: ${String(error?.message ?? error).split("\n")[0]}`, { ok: false });
        }
      },
    });

    // Only reached when Adam approves the card, which jorah-dev can't (no approval route).
    api.registerTool({
      name: "github_push_branch", catalogMode: "direct-only",
      description: "Push a jorah/<task> branch from ~/work/<project> to its GitHub repo. Adam approves each push. Never pushes main or forces.",
      parameters: params,
      async execute(_id, p) {
        record({ tool: "github_push_branch", project: p?.project, branch: p?.branch, ran: true });
        if (!String(p?.branch).startsWith("jorah/")) return text("Push didn't happen: only jorah/* branches", { ok: false });
        try {
          git(["push", "-q", "github", `${p.branch}:refs/heads/${p.branch}`], join(work, repoName(p.project)));
          return text(`Pushed ${p.branch} to AdamHikl/${p.project}.`, { ok: true });
        } catch (error) {
          return text(`Push didn't happen: ${String(error?.message ?? error).split("\n")[0]}`, { ok: false });
        }
      },
    });

    api.registerTool({
      name: "github_open_pr", catalogMode: "direct-only",
      description: "Open a draft pull request on GitHub from a jorah/<task> branch already pushed. Adam approves each one.",
      parameters: { ...params, required: ["project", "branch", "title"], properties: { ...params.properties, title: { type: "string" }, body: { type: "string" }, base: { type: "string" } } },
      async execute(_id, p) {
        record({ tool: "github_open_pr", project: p?.project, branch: p?.branch, title: String(p?.title ?? "").slice(0, 200), ran: true });
        return text(`Opened draft pull request #1 on AdamHikl/${p?.project}.`, { ok: true });
      },
    });
  },
};
