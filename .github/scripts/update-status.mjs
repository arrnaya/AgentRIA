import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const REPO = "arrnaya/AgentRIA";
const LAUNCH = new Date("2026-09-08T00:00:00Z");
const README_PATH = "README.md";

function git(cmd) {
  return execSync(`git ${cmd}`, { encoding: "utf8" }).trim();
}

const shortSha = git("rev-parse --short HEAD");
const fullSha = git("rev-parse HEAD");
const message = git("log -1 --pretty=%s");
const author = git("log -1 --pretty=%an");
const commitCount = git("rev-list --count HEAD");

const now = new Date();
const msPerDay = 24 * 60 * 60 * 1000;
const daysToLaunch = Math.ceil((LAUNCH.getTime() - now.getTime()) / msPerDay);

const PHASES = {
  1: "Day 1 — Data Layer (Subgraph MCP + Substreams + RECON)",
  2: "Day 2 — Intelligence Layer (SCOUT + RISK + LangGraph routing)",
  3: "Day 3 — Payment Layer (x402 inference server + ORACLE)",
  4: "Day 4 — Identity + Audit (ENSv2 subnames + HCS logging)",
  5: "Day 5 — Dashboard (live WebSocket panels)",
  6: "Day 6 — Polish + Submit (README, SKILL.md, demo video)",
};

let phase = "Pre-launch — repo, README & landing/dashboard preview live";
if (now.getTime() >= LAUNCH.getTime()) {
  const dayNum = Math.min(
    6,
    Math.max(1, Math.floor((now.getTime() - LAUNCH.getTime()) / msPerDay) + 1)
  );
  phase = PHASES[dayNum] ?? "Post-submission — live at ETHGlobal Online 2026";
}

const readme = readFileSync(README_PATH, "utf8");

const checklistMatches = [...readme.matchAll(/^- \[( |x|X)\]/gm)];
const total = checklistMatches.length;
const done = checklistMatches.filter((m) => m[1].toLowerCase() === "x").length;
const pct = total ? Math.round((done / total) * 100) : 0;
const barLength = 20;
const filled = Math.round((pct / 100) * barLength);
const bar = "█".repeat(filled) + "░".repeat(barLength - filled);

const daysLabel =
  daysToLaunch > 0
    ? `${daysToLaunch} day${daysToLaunch === 1 ? "" : "s"}`
    : "Submission window open";

const lastUpdated = now.toISOString().replace("T", " ").slice(0, 16) + " UTC";

const block = `<!-- STATUS:START -->
| | |
|---|---|
| **Current phase** | ${phase} |
| **Build checklist** | \`${bar}\` ${done}/${total} (${pct}%) |
| **Days to ETHGlobal submission open** | ${daysLabel} |
| **Latest commit** | [\`${shortSha}\`](https://github.com/${REPO}/commit/${fullSha}) ${message} — ${author} |
| **Total commits** | ${commitCount} |
| **Last updated** | ${lastUpdated} |

_This block is regenerated automatically by [.github/workflows/update-status.yml](.github/workflows/update-status.yml) on every push to \`main\`._
<!-- STATUS:END -->`;

const updated = readme.replace(
  /<!-- STATUS:START -->[\s\S]*?<!-- STATUS:END -->/,
  block
);

if (updated !== readme) {
  writeFileSync(README_PATH, updated);
  console.log("README status block updated.");
} else {
  console.log("README status block unchanged.");
}
