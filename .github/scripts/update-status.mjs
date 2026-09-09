import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const REPO = "arrnaya/AgentRIA";
const SUBMISSION_OPEN = new Date("2026-09-08T00:00:00Z");
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
const daysSinceOpen = Math.floor((now.getTime() - SUBMISSION_OPEN.getTime()) / msPerDay);

const readme = readFileSync(README_PATH, "utf8");

const checklistMatches = [...readme.matchAll(/^- \[( |x|X)\]/gm)];
const total = checklistMatches.length;
const done = checklistMatches.filter((m) => m[1].toLowerCase() === "x").length;
const pct = total ? Math.round((done / total) * 100) : 0;
const barLength = 20;
const filled = Math.round((pct / 100) * barLength);
const bar = "█".repeat(filled) + "░".repeat(barLength - filled);

// Phase is driven by actual checklist progress, not the calendar — a date
// alone can't tell you whether the pipeline has really been built.
let phase;
if (done === 0) {
  phase =
    now.getTime() >= SUBMISSION_OPEN.getTime()
      ? "Architecture finalized (v3) — implementation not yet started"
      : "Pre-launch — repo, README & landing/dashboard preview live";
} else if (done === total) {
  phase = "Build complete — submitted to ETHGlobal Online 2026";
} else {
  phase = `In progress — ${done}/${total} build milestones complete`;
}

const windowLabel =
  daysSinceOpen >= 0
    ? `Open since Sep 8, 2026 (day ${daysSinceOpen + 1})`
    : `Opens in ${Math.abs(daysSinceOpen)} day${Math.abs(daysSinceOpen) === 1 ? "" : "s"}`;

const lastUpdated = now.toISOString().replace("T", " ").slice(0, 16) + " UTC";

const block = `<!-- STATUS:START -->
| | |
|---|---|
| **Current phase** | ${phase} |
| **Build checklist** | \`${bar}\` ${done}/${total} (${pct}%) |
| **ETHGlobal submission window** | ${windowLabel} |
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
