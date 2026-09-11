/**
 * Live verification for checklist items that can be proven automatically.
 *
 * This deliberately does NOT read local .env files — it only ever runs
 * against `GRAPH_API_KEY` supplied as a GitHub Actions repository secret,
 * so the checklist can only move from unchecked -> checked based on a real,
 * reproducible check anyone with repo admin access can audit in the
 * workflow run logs. It never unchecks a box: a transient network blip
 * should not make the README lie about work that was already verified.
 */

import { readFileSync, writeFileSync } from "node:fs";

const README_PATH = "README.md";
const GATEWAY = "https://gateway.thegraph.com/api";
// Kept in sync with graph/subgraph_client.py's SUBGRAPH_IDS -- see that
// module's comment for how these were re-derived from Messari's own
// registry after a live pipeline run found the previous ids had gone
// stale ("subgraph not found" from the Gateway).
const SUBGRAPHS = {
  uniswap: "4cKy6QQMc5tpfdx8yxfYeb9TLZmgLQe44ddW1G7NwkA6",
  aave: "JCNWRypm7FYwV8fx5HhzZPSFaMxgkPuw4TnR3Gpi81zk",
};

async function queryPoolCount(apiKey, subgraphId, field) {
  const url = `${GATEWAY}/${apiKey}/subgraphs/id/${subgraphId}`;
  const query =
    field === "liquidityPools"
      ? `query { liquidityPools(first: 1) { id totalValueLockedUSD } }`
      : `query { markets(first: 1) { id totalValueLockedUSD } }`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ query }),
  });

  if (!res.ok) {
    throw new Error(`${subgraphId} gateway returned HTTP ${res.status}`);
  }
  const body = await res.json();
  if (body.errors) {
    throw new Error(`${subgraphId} GraphQL errors: ${JSON.stringify(body.errors)}`);
  }
  const rows = body.data?.[field] ?? [];
  return rows.length;
}

function setChecked(readme, itemText) {
  const pattern = new RegExp(`^- \\[ \\] ${itemText.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`, "m");
  if (!pattern.test(readme)) return readme; // already checked, or text drifted — leave untouched
  return readme.replace(pattern, `- [x] ${itemText}`);
}

async function main() {
  const apiKey = process.env.GRAPH_API_KEY;
  if (!apiKey) {
    console.log("GRAPH_API_KEY not set (no repo secret configured yet) — skipping live verification.");
    return;
  }

  let readme = readFileSync(README_PATH, "utf8");
  const results = [];

  try {
    const uniswapCount = await queryPoolCount(apiKey, SUBGRAPHS.uniswap, "liquidityPools");
    const aaveCount = await queryPoolCount(apiKey, SUBGRAPHS.aave, "markets");
    results.push({ check: "uniswap", ok: uniswapCount > 0, count: uniswapCount });
    results.push({ check: "aave", ok: aaveCount > 0, count: aaveCount });

    if (uniswapCount > 0 && aaveCount > 0) {
      readme = setChecked(readme, "Subgraph Studio API key live, querying Uniswap + Aave");
      readme = setChecked(
        readme,
        "Messari Standardized Subgraphs queries returning normalized data"
      );
    }
  } catch (err) {
    results.push({ check: "graph-gateway", ok: false, error: String(err) });
  }

  console.log("Verification results:", JSON.stringify(results, null, 2));

  writeFileSync(README_PATH, readme);
}

main();
