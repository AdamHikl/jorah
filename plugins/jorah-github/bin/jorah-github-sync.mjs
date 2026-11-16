#!/usr/bin/env node
// Sync one repo into jorah-github's mirror from the command line, for the project runner
// (services/jorah-projects, docs/plan/11-project-mode.md section 4.1 step 3). The same flow as the
// plugin's github_sync tool: a read-only, one-hour installation token for that one repo, every
// GitHub branch into refs/remotes/github/* of the plugin-owned mirror, nothing else. Never pushes.
//
//   node jorah-github-sync.mjs --project <folder under ~/work> --repo <owner/name> --app-id <n> --owner <account>
//                              [--key-file <path>] [--mirror-dir <path>]
//
// Prints one JSON line: {"ok":true,"project","repo","mirror","defaultBranch","branches":<count>} or
// {"ok":false,"error":"..."} with exit code 1. The token is never printed or written to disk.

import { pathToFileURL } from "node:url";
import { settings, syncFlow } from "../github.js";

const FLAGS = new Set(["--project", "--repo", "--app-id", "--owner", "--key-file", "--mirror-dir"]);

export function parseArgs(argv) {
  const out = {};
  for (let i = 0; i < argv.length; i += 2) {
    const flag = argv[i];
    const value = argv[i + 1];
    if (!FLAGS.has(flag) || value === undefined || value.startsWith("--")) throw new Error(`usage: --project P --repo owner/name --app-id N --owner O [--key-file F] [--mirror-dir D] (bad ${flag ?? "end"})`);
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
    });
    const { target, synced } = await syncFlow(config, args.project, { fetchImpl, ...(remoteBase ? { remoteBase } : {}) });
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
