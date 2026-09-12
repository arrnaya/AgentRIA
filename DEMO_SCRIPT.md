# RIA Demo Video Script (3 minutes)

Companion to README.md's [Demo Strategy](README.md#demo-strategy) table — this is the word-for-word
version: exact commands, exact narration, exact things to click. Read through once before recording;
the pre-flight checklist below takes the real risk out of a live demo.

## Pre-flight checklist (do this before hitting record)

- [ ] Two **different** funded Hedera testnet accounts ready (buyer ≠ payTo — reusing one account
      makes every payment net to zero, a real bug this build hit and fixed).
- [ ] `.env.local` (or exported vars) has: `GRAPH_API_KEY`, `HEDERA_ACCOUNT_ID`/`HEDERA_PRIVATE_KEY`
      ×2 (one per account above), `BLOCKY402_FACILITATOR_URL=https://api.testnet.blocky402.com`,
      `ETHERSCAN_API_KEY`, `ANTHROPIC_API_KEY`.
- [ ] Port 3002 (or whichever `--ws-port` you use) is free — check with `lsof -nP -iTCP:3002`.
- [ ] Do a **dry run** of the whole sequence once, off-camera, immediately before recording — this
      catches a stale terminal, an expired key, or a port conflict before it costs you a take.
- [ ] Have these tabs pre-opened, ready to switch to: the dashboard (`localhost:3000/app`), a
      HashScan tab, the Sepolia ENS app for `oracle.agentria.eth`, and a terminal showing the MCP
      server's logs.
- [ ] Know your MCP server's bound port (default `8000`) — you'll paste a `curl` command against it
      live in segment 5, so have the exact command ready in a scratch file, not retyped on camera.

## Terminal setup (start these in order, before recording, so cycle timing is predictable)

```bash
# Terminal 1 — MCP server
export HEDERA_ACCOUNT_ID=0.0.<payTo-account>
export BLOCKY402_FACILITATOR_URL=https://api.testnet.blocky402.com
export ETHERSCAN_API_KEY=...
export ANTHROPIC_API_KEY=...
export MCP_TRANSPORT=streamable-http
python -m mcp_server.server

# Terminal 2 — pipeline (start this ONLY when the recording begins segment 2)
export GRAPH_API_KEY=...
export HEDERA_ACCOUNT_ID=0.0.<oracle-wallet>   # different account than Terminal 1
export HEDERA_PRIVATE_KEY=...
python pipeline/runner.py --mode live --risk-threshold 0.65 --budget-hbar 10 --interval 30 --ws-port 3002

# Terminal 3 — frontend
export NEXT_PUBLIC_RIA_WS_URL=ws://localhost:3002
npm run dev
```

Start Terminals 1 and 3 before recording (an idle MCP server and an idle dashboard are exactly what
segment 1 shows). Start Terminal 2 live, on camera, at the top of segment 2.

---

## Segment-by-segment

### 0:00–0:20 — Cold open

**Show:** Dashboard (`localhost:3000/app`) full-screen, all four panels showing the honest
`PREVIEW` badge, header pill reading "Pipeline: Not connected."

**Say:** "This is RIA — an autonomous multi-agent DeFi intelligence system. Every panel you're
about to see is live, not staged. Right now nothing's running, so it's honestly showing preview
data — watch it go live in real time."

### 0:20–0:50 — Start the pipeline

**Do:** Switch to Terminal 2, run the pipeline command above.

**Show:** Terminal scrolling real `RECON: N pools from uniswap-v3-ethereum` / `RECON: N markets
from aave-v3-ethereum` log lines, then cut to the dashboard — Opportunities Feed panel flips to its
`LIVE` badge and starts populating with real signals.

**Say:** "That's a real query against The Graph's decentralized network — Messari Standardized
Subgraphs, live Uniswap v3 and Aave v3 data on Ethereum mainnet. Watch the Opportunities Feed."

### 0:50–1:20 — Agent Trace

**Show:** Agent Trace panel — RECON → SCOUT → RISK progression as each node reports in, with real
confidence scores and the 0.65 routing threshold.

**Say:** "Six agents in a LangGraph StateGraph. SCOUT ranks what RECON found; RISK decides what
clears the confidence bar to get paid enrichment. Everything below the threshold waits, everything
above routes to ORACLE — the only agent in this system allowed to spend money."

### 1:20–2:00 — The x402 payment

**Show:** Split screen or quick cut: Terminal 1 (MCP server log) showing
`402 Payment Required` → `POST .../verify 200 OK` → `POST .../settle 200 OK` → `x402 middleware:
settled payment for 'get_risk_score' — tx <real tx id>`; then the dashboard's Payment Monitor panel
flipping to `LIVE` with the HBAR amount and a "Confirmed on Hedera" badge.

**Say:** "ORACLE just called a priced tool with no payment — got a 402, built a Hedera transfer,
signed it, retried. Blocky402 verified and settled it in about three seconds. That's real HBAR,
right now, on Hedera testnet." Click the tx into HashScan live if time allows.

### 2:00–2:20 — EXEC and AUDIT

**Show:** Agent Trace's final routing entry; HCS Audit Trail panel flips to `LIVE` with a new entry
carrying an HCS topic link.

**Say:** "EXEC gates on that enrichment and dispatches. AUDIT writes the action, the payment amount,
and a hash of the response to Hedera Consensus Service — tamper-proof, timestamped." Click the
mirror-node link live.

### 2:20–2:40 — The killer moment: a second, independent agent

**Do:** Switch to a clean terminal (not Terminal 1 or 2) and run the external-agent script:

```bash
export HEDERA_ACCOUNT_ID=0.0.<a-third-account>   # not ORACLE's, not the MCP server's payTo
export HEDERA_PRIVATE_KEY=...
python scripts/external_agent_demo.py
```

**Show:** The script's own output: cold connect → `402` → build + sign a payment → `200` with real
data back, for each of the four working tools.

**Say:** "This script has never talked to RIA's pipeline before — it's a completely independent
client with its own wallet. It connects cold, gets challenged for payment, pays, and gets data
back. This is the proof: the MCP server isn't a RIA-only trick, it's a generalized commercial
primitive any AI agent can use."

This is the single most memorable 20 seconds for a judge — don't rush it.

### 2:40–3:00 — Identity, close

**Show:** The Sepolia ENS app resolving `oracle.agentria.eth` live, then back to the dashboard's
Identity panel.

**Say:** "Every agent carries its own ENSv2 identity with on-chain-enforced write isolation — one
agent's key can never touch another's records. That's RIA: free Graph data, autonomous agent
reasoning, real x402 payments, and verifiable identity, all live, all on-chain, right now."

---

## If something breaks mid-recording

- **A panel doesn't go live in time:** don't stall on camera — narrate what should happen ("this
  will populate within the next cycle") and cut to it in editing, or just let a slightly-late signal
  land; a live demo running a few seconds behind schedule is normal and forgivable.
- **A 402 retry fails:** check Terminal 1's log for the actual error before re-recording that
  segment — don't guess. The buyer/payTo distinct-account rule (see pre-flight checklist) is the
  most common cause.
- **CoinGecko rate-limits:** `get_price_feed`/`get_risk_score` now cache for 60s (see
  `mcp_server/tools/price_feed.py`), so this should be rare — if it happens anyway, wait ~30s and
  retry rather than restarting everything.

## After recording

Upload, get the shareable link, and drop it into the ETHGlobal submission form alongside the repo
link — see the [Build Checklist](README.md#build-checklist)'s last three items.
