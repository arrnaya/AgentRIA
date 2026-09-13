import { execSync } from "node:child_process";
import { readFileSync, writeFileSync } from "node:fs";

const REPO = "arrnaya/AgentRIA";
// ETHOnline 2026 runs Sep 4-16; submissions close Sun Sep 13 2026, 12:00pm EDT (16:00 UTC).
// Source: https://ethglobal.com/events/ethonline2026/info/details
const SUBMISSION_DEADLINE = new Date("2026-09-13T16:00:00Z");
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
const msRemaining = SUBMISSION_DEADLINE.getTime() - now.getTime();
const hoursRemaining = Math.floor(msRemaining / (60 * 60 * 1000));

const readme = readFileSync(README_PATH, "utf8");

// Each checklist lives in its own "## " section, so a box added under
// "## Future Build Checklist" (scoped-out work, tracked but not promised
// for this submission) never dilutes the main "## Build Checklist" percentage.
function section(heading) {
  const start = readme.indexOf(`## ${heading}`);
  if (start === -1) return "";
  const bodyStart = readme.indexOf("\n", start) + 1;
  const nextHeading = readme.indexOf("\n## ", bodyStart);
  return nextHeading === -1 ? readme.slice(bodyStart) : readme.slice(bodyStart, nextHeading);
}

const barLength = 20;
function tally(text) {
  const matches = [...text.matchAll(/^- \[( |x|X)\]/gm)];
  const total = matches.length;
  const done = matches.filter((m) => m[1].toLowerCase() === "x").length;
  const pct = total ? Math.round((done / total) * 100) : 0;
  const filled = Math.round((pct / 100) * barLength);
  const bar = "█".repeat(filled) + "░".repeat(barLength - filled);
  return { done, total, pct, bar };
}

const { done, total, pct, bar } = tally(section("Build Checklist"));
const future = tally(section("Future Build Checklist"));

// Phase is driven by actual checklist progress, not the calendar — a date
// alone can't tell you whether the pipeline has really been built. Submission
// itself is one of the checklist items, so done === total already implies
// submitted, whether or not the deadline has technically passed yet.
let phase;
if (done === total) {
  phase = msRemaining <= 0 ? "Submitted — build complete before deadline" : "Submitted — build complete";
} else if (msRemaining <= 0) {
  phase = `Deadline passed — ${done}/${total} milestones verified at close`;
} else if (done === 0) {
  phase = "Architecture finalized (v3) — implementation starting";
} else {
  phase = `In progress — ${done}/${total} build milestones verified`;
}

function formatRemaining(hours) {
  if (hours <= 0) return "Deadline passed";
  const days = Math.floor(hours / 24);
  const rem = hours % 24;
  if (days === 0) return `${rem}h remaining — final push`;
  return `${days}d ${rem}h remaining`;
}

const windowLabel = `${formatRemaining(hoursRemaining)} (deadline: Sun Sep 13, 12:00pm EDT)`;

const lastUpdated = now.toISOString().replace("T", " ").slice(0, 16) + " UTC";

const block = `<!-- STATUS:START -->
| | |
|---|---|
| **Current phase** | ${phase} |
| **Build checklist** | \`${bar}\` ${done}/${total} (${pct}%) — verified live where possible, not self-reported |
| **Future build checklist** | \`${future.bar}\` ${future.done}/${future.total} (${future.pct}%) — scoped out of this submission, tracked separately |
| **Time to ETHGlobal deadline** | ${windowLabel} |
| **Latest commit** | [\`${shortSha}\`](https://github.com/${REPO}/commit/${fullSha}) ${message} — ${author} |
| **Total commits** | ${commitCount} |
| **Last updated** | ${lastUpdated} |

_This block is regenerated automatically by [.github/workflows/update-status.yml](.github/workflows/update-status.yml) on every push to \`main\`, after [verify-checklist.mjs](.github/scripts/verify-checklist.mjs) attempts to prove each checklist item live._
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
