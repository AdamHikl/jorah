#!/usr/bin/env node
// Sync one repo into jorah-github's mirror from the command line, for the project runner
// (services/jorah-projects, docs/plan/11-project-mode.md section 4.1 step 3). The same flow as the
// plugin's github_sync tool: a read-only, one-hour installation token for that one repo, every
// GitHub branch into refs/remotes/github/* of the plugin-owned mirror, nothing else. Never pushes.
//
//   node jorah-github-sync.mjs [sync|clone] --project <folder under ~/work> --repo <owner/name> --app-id <n> --owner <account>
//                              [--key-file <path>] [--mirror-dir <path>] [--work-dir <path>]
//
// `clone` (for a project whose work folder doesn't exist yet) is github_clone's flow: sync the
// mirror, then make <work-dir>/<project> from it with remote "github" reading the mirror and the
// default branch checked out. It refuses if the folder exists.
//
// Prints one JSON line: {"ok":true,"project","repo","mirror","defaultBranch","branches":<count>}
// (clone adds "path" and "branch") or {"ok":false,"error":"..."} with exit code 1. The token is
// never printed or written to disk.

import { pathToFileURL } from "node:url";
import { cloneFlow, settings, syncFlow } from "../github.js";

const FLAGS = new Set(["--project", "--repo", "--app-id", "--owner", "--key-file", "--mirror-dir", "--work-dir"]);
const ACTIONS = new Set(["sync", "clone"]);

export function parseArgs(argv) {
  const out = { action: "sync" };
  let i = 0;
  if (argv.length && !argv[0].startsWith("--")) {
    if (!ACTIONS.has(argv[0])) throw new Error(`usage: [sync|clone] --project P ... (unknown action ${argv[0].slice(0, 20)})`);
    out.action = argv[0];
    i = 1;
  }
  for (; i < argv.length; i += 2) {
    const flag = argv[i];
    const value = argv[i + 1];
    if (!FLAGS.has(flag) || value === undefined || value.startsWith("--")) throw new Error(`usage: [sync|clone] --project P --repo owner/name --app-id N --owner O [--key-file F] [--mirror-dir D] [--work-dir W] (bad ${flag ?? "end"})`);
    out[flag.slice(2)] = value;
  }
  for (const need of ["project", "repo", "app-id", "owner"]) if (!out[need]) throw new Error(`--${need} is required`);
  return out;
}

/** The CLI's whole flow. `fetchImpl` and `remoteBase` are test seams only, never flags. */
export async function main(argv, { fetchImpl = fetch, remoteBase, write = (line) => process.stdout.write(`${line}\n`) } = {}) {
  try {
    const args = parseArgs(argv);
    const config = settings({
      appId: args["app-id"],
      owner: args.owner,
      repos: { [args.project]: args.repo },
      ...(args["key-file"] ? { keyFile: args["key-file"] } : {}),
      ...(args["mirror-dir"] ? { mirrorDir: args["mirror-dir"] } : {}),
      ...(args["work-dir"] ? { workDir: args["work-dir"] } : {}),
    });
    const seams = { fetchImpl, ...(remoteBase ? { remoteBase } : {}) };
    if (args.action === "clone") {
      // The repos map names this folder, so cloneFlow keeps the project's own folder name.
      const { target, synced, cloned } = await cloneFlow(config, args.project, seams);
      write(JSON.stringify({ ok: true, project: target.project, repo: target.repo, mirror: synced.mirror, defaultBranch: synced.defaultBranch ?? cloned.branch ?? null, branches: synced.branches.length, path: cloned.path, branch: cloned.branch }));
      return 0;
    }
    const { target, synced } = await syncFlow(config, args.project, seams);
    write(JSON.stringify({ ok: true, project: target.project, repo: target.repo, mirror: synced.mirror, defaultBranch: synced.defaultBranch ?? null, branches: synced.branches.length }));
    return 0;
  } catch (error) {
    write(JSON.stringify({ ok: false, error: String(error?.message ?? error).split("\n")[0].slice(0, 300) }));
    return 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = await main(process.argv.slice(2));
}
