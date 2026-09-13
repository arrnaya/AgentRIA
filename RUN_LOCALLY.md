# Running RIA Locally — Full Live Stack + Test Playbook

Everything needed to get all three processes running with real data and real payments, plus a
step-by-step test sequence to confirm each panel/agent is genuinely live.

## What you need before starting

| Credential | Where to get it | Used by |
|---|---|---|
| `GRAPH_API_KEY` | [thegraph.com/studio](https://thegraph.com/studio/) — free | Terminal 2 (pipeline) |
| **Two** funded Hedera testnet accounts | [Hedera Testnet Portal](https://portal.hedera.com/) — free faucet | One per terminal, see below — **must be different accounts** |
| `ETHERSCAN_API_KEY` | [etherscan.io/apis](https://etherscan.io/apis) — free | Terminal 1 (MCP server) |
| `ANTHROPIC_API_KEY` | [console.anthropic.com](https://console.anthropic.com/) | Terminal 1 (MCP server — `get_risk_score`/`get_sentiment` call Claude) |
| `COINGECKO_API_KEY` *(optional)* | [coingecko.com/en/api](https://www.coingecko.com/en/api) | Terminal 1 — works without one, a demo key just raises the rate limit |
| `HCS_TOPIC_ID` *(optional but recommended)* | Run `python scripts/hcs_smoke_test.py` once to create one, or reuse an existing one | Terminal 2 — without this, AUDIT silently skips logging and the HCS Audit Trail panel never goes live |

**Why two Hedera accounts, not one:** Terminal 1's `HEDERA_ACCOUNT_ID` is the resource server's
`payTo` address; Terminal 2's is ORACLE's own paying wallet. A native Hedera transfer to yourself
always nets to zero, so if these are the same account every payment silently fails with an
"own account" / amount-mismatch error. This bit this exact build once — see `hedera/x402_client.py`'s
`_build_payment_header` if you want the full story.

Check nothing else is already bound to the ports you're about to use before starting anything:

```bash
lsof -nP -iTCP:8000 -sTCP:LISTEN   # Terminal 1's default port
lsof -nP -iTCP:3002 -sTCP:LISTEN   # the --ws-port used below (3001 is commonly taken by Docker Desktop)
lsof -nP -iTCP:3000 -sTCP:LISTEN   # Terminal 3's default port
```

If any of these print a result, either stop that process or pick a different port everywhere below
(the MCP server via `MCP_PORT`, the pipeline via `--ws-port`, Next.js via `npm run dev -- -p <port>`).

---

## Terminal 1 — the x402-gated MCP server

```bash
cd AgentRIA
source .venv/bin/activate

export HEDERA_ACCOUNT_ID=0.0.AAAAAAA        # account "A" — the payTo / resource-server account
export BLOCKY402_FACILITATOR_URL=https://api.testnet.blocky402.com
export ETHERSCAN_API_KEY=your_etherscan_key
export ANTHROPIC_API_KEY=your_anthropic_key
export COINGECKO_API_KEY=your_coingecko_key   # optional
export MCP_TRANSPORT=streamable-http

python -m mcp_server.server
```

**Expect to see:**
```
INFO     RIA x402-gated MCP server listening on 127.0.0.1:8000
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```
No further output until Terminal 2 starts calling it — that's correct, this terminal only logs on
incoming requests.

`HEDERA_PRIVATE_KEY` is **not** needed here — this server never signs a transaction, it only names
where payments land and verifies/settles through Blocky402.

## Terminal 2 — the agent pipeline + WebSocket server

```bash
cd AgentRIA
source .venv/bin/activate

export GRAPH_API_KEY=your_graph_api_key
export HEDERA_ACCOUNT_ID=0.0.BBBBBBB        # account "B" — ORACLE's own wallet, DIFFERENT from Terminal 1
export HEDERA_PRIVATE_KEY=your_account_B_private_key
export HCS_TOPIC_ID=0.0.10467384             # reuse an existing topic, or your own from hcs_smoke_test.py

python pipeline/runner.py --mode live --risk-threshold 0.65 --budget-hbar 10 --interval 30 --ws-port 3002
```

If Terminal 1 is running on something other than `127.0.0.1:8000`, add
`--mcp-server http://host:port` to this command — it sets `MCP_SERVER_URL` for ORACLE for you.

**Expect to see, every ~30s (one `--interval` cycle), in this order:**
```
ria.recon    INFO  RECON: 10 pools from uniswap-v3-ethereum
ria.recon    INFO  RECON: 10 markets from aave-v3-ethereum
ria.scout    INFO  SCOUT: ranked 20 new signals
ria.risk     INFO  RISK: assessed 20 opportunities (9 above 0.65 threshold)
httpx        INFO  HTTP Request: POST http://127.0.0.1:8000/mcp "HTTP/1.1 402 Payment Required"
httpx        INFO  HTTP Request: POST http://127.0.0.1:8000/mcp "HTTP/1.1 200 OK"
ria.x402_client INFO  x402_client: paid 0.002 HBAR for 'get_risk_score'
ria.exec     INFO  EXEC: dispatched N actions
```
Each `402` → `200` → `paid ...` triple is one real, on-chain HBAR payment. If you see repeated
`402`s with no `200`/`paid` line following, check Terminal 1's own log for the actual rejection
reason — see Troubleshooting below.

## Terminal 3 — the dashboard

```bash
cd AgentRIA
export NEXT_PUBLIC_RIA_WS_URL=ws://localhost:3002   # must match Terminal 2's --ws-port exactly
npm run dev
```

Open the printed URL's `/app` path (e.g. `http://localhost:3000/app`) — **not** the deployed
`ria-agent.vercel.app/app`, which has no way to reach a WebSocket server running on your laptop.

---

## Thorough test sequence

Do this once, off-camera, before recording — it isolates exactly which piece is misbehaving if
something doesn't come up live, instead of debugging blind during a take.

1. **Start Terminal 1 alone.** Confirm the startup log above, no errors. Leave it running.
2. **Start Terminal 3 alone**, open `/app`. All four panels should show `PREVIEW`, header pill
   "Pipeline: Not connected." This confirms the frontend build itself is healthy before any backend
   is involved.
3. **Start Terminal 2.** Watch its log for one full cycle (up to `--interval` seconds, 30s by
   default). Confirm the exact log sequence above appears with no tracebacks.
4. **Switch back to the dashboard.** Within a few seconds of Terminal 2's first cycle completing:
   - Header pill → "Pipeline: Connected"
   - Opportunities Feed → `LIVE` badge, real signals
   - Agent Trace → `LIVE` badge, all 6 agents reporting
   - Payment Monitor → `LIVE` badge, a real tool/amount/tx once ORACLE's first payment settles
   - HCS Audit Trail → `LIVE` badge once EXEC dispatches something AND `HCS_TOPIC_ID` is set in
     Terminal 2 — if this one stays on `PREVIEW` while the others go live, check `HCS_TOPIC_ID`
     first, that's almost always why.
5. **Verify a payment independently**, not just via the log line — pick a tx id Terminal 2 printed
   and check it on the public mirror node (works even before HashScan's UI catches up):
   ```bash
   curl -s "https://testnet.mirrornode.hedera.com/api/v1/transactions/<ACCOUNT>-<SECONDS>-<NANOS>" | python3 -m json.tool
   ```
   (convert the printed `account@seconds.nanos` id by replacing `@`/`.` with `-`). Look for
   `"result": "SUCCESS"`.
6. **Run the external-agent proof**, in a fourth terminal, with a **third** funded account (not
   Terminal 1's or Terminal 2's):
   ```bash
   export HEDERA_ACCOUNT_ID=0.0.CCCCCCC
   export HEDERA_PRIVATE_KEY=your_account_C_private_key
   python scripts/external_agent_demo.py
   ```
   Confirm it reports `4/4 tools called successfully`. This is the "killer moment" segment
   (2:20–2:40) in the [recorded demo](https://www.loom.com/share/685b9f09029745aeb9c96bd9917b40d1).
7. **Only once all of the above passes once, start recording** and repeat the same sequence live —
   you already know it works, so the recording is a rerun, not a first attempt.

## Troubleshooting — every real error this build actually hit

| Symptom | Cause | Fix |
|---|---|---|
| `OSError: address already in use` on startup | Something else already bound that port (Docker Desktop commonly holds 3001) | `lsof -nP -iTCP:<port> -sTCP:LISTEN`, then use a different port |
| ORACLE payment `402` repeats with no `200`/`paid` | Check Terminal 1's log for the specific rejection — was `invalid_exact_hedera_payload_amount_mismatch` (see the two-account note above), `INSUFFICIENT_TX_FEE`/`INSUFFICIENT_GAS` (unlikely now, already fixed), or something new | Read Terminal 1's actual error text, don't just retry |
| `ORACLE: no wallet configured, skipping enrichment` | `HEDERA_ACCOUNT_ID`/`HEDERA_PRIVATE_KEY` not set in **Terminal 2** | Export both in Terminal 2 specifically — this is the pipeline process, not the MCP server |
| `AUDIT: no HCS topic configured, skipping logging` | `HCS_TOPIC_ID` not set in Terminal 2 | Export it, or run `python scripts/hcs_smoke_test.py` once to create one |
| `RiskScoreError`/`SentimentError`: `ANTHROPIC_API_KEY is not set` | Missing in **Terminal 1** (the MCP server calls Claude, not the pipeline) | Export it in Terminal 1 |
| CoinGecko `429 Too Many Requests` | Should be rare now — `get_price_feed` caches for 60s and retries once. If it still happens repeatedly, you're likely running two MCP servers or two pipelines against the same free-tier IP | Check for a duplicate process; wait ~30s and it'll clear on its own |
| `subgraph not found` from the Graph Gateway | A pinned Messari deployment id went stale | See `SKILL.md` for exactly how to re-derive the current id — this happened once already this build |
| Dashboard stuck on `PREVIEW` for every panel | Frontend isn't actually connected | Check you're on `localhost:PORT/app`, not the deployed Vercel URL, and that `NEXT_PUBLIC_RIA_WS_URL`'s port matches Terminal 2's `--ws-port` exactly |
| Dashboard live for 3 panels but HCS Audit Trail stuck on `PREVIEW` | `HCS_TOPIC_ID` missing in Terminal 2, or EXEC hasn't dispatched anything yet this run | Set `HCS_TOPIC_ID`; give it one more `--interval` cycle |