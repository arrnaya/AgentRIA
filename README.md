# RIA — Reconnaissance Intelligence Agent

**On-chain intelligence that acts.**

RIA is an autonomous, multi-agent DeFi intelligence system built on three distinct layers: a
free, open data foundation from [The Graph](https://thegraph.com); a commercial,
[x402](https://x402.org)-gated [MCP](https://modelcontextprotocol.io) server on
[Hedera](https://hedera.com) that **any** AI agent can pay to use; and a real-time
[ENSv2](https://ens.domains)-identified dashboard that makes every decision and payment visible.

> RIA is not a dashboard. It is an agent that acts — and a commercial primitive that proves how
> the AI agent economy should handle payments.

Built solo by **Arrnaya (Arun Kumar Yadav)** for **ETHGlobal Online 2026**. Architecture v3.

[![Landing](https://img.shields.io/badge/landing-ria--agent.vercel.app-b7a2ec?style=flat-square)](https://ria-agent.vercel.app)
[![Dashboard](https://img.shields.io/badge/dashboard-ria--agent.vercel.app%2Fapp-a4cdec?style=flat-square)](https://ria-agent.vercel.app/app)
[![Deploy](https://img.shields.io/github/actions/workflow/status/arrnaya/AgentRIA/update-status.yml?label=status%20bot&style=flat-square)](https://github.com/arrnaya/AgentRIA/actions/workflows/update-status.yml)
[![Last commit](https://img.shields.io/github/last-commit/arrnaya/AgentRIA?style=flat-square&color=93d9b8)](https://github.com/arrnaya/AgentRIA/commits/main)
[![License](https://img.shields.io/badge/license-MIT-eeb2cd?style=flat-square)](#license)

---

## 🔴 Live Status

<!-- STATUS:START -->
| | |
|---|---|
| **Current phase** | In progress — 8/15 build milestones verified |
| **Build checklist** | `███████████░░░░░░░░░` 8/15 (53%) — verified live where possible, not self-reported |
| **Time to ETHGlobal deadline** | 11h remaining — final push (deadline: Sun Sep 13, 12:00pm EDT) |
| **Latest commit** | [`2ad19cb`](https://github.com/arrnaya/AgentRIA/commit/2ad19cb2ca760126777cd19cdc86a685b54f6289) Fix confidence_delta always 0.0 and response_hash always null — Arrnaya |
| **Total commits** | 126 |
| **Last updated** | 2026-09-13 04:30 UTC |

_This block is regenerated automatically by [.github/workflows/update-status.yml](.github/workflows/update-status.yml) on every push to `main`, after [verify-checklist.mjs](.github/scripts/verify-checklist.mjs) attempts to prove each checklist item live._
<!-- STATUS:END -->

This repo is being built in public and the block above tells the truth about progress — it's
computed from the checked boxes in the [Build Checklist](#build-checklist), not from a calendar.
The full Python backend is live: RECON pulling real Graph data, ORACLE paying real HBAR via x402
(repeatedly, autonomously), HCS audit logging, ERC-8004 identity, and ENSv2 identity are all
confirmed on-chain — see [What's Live](#whats-live-in-this-repo-right-now) for the receipts. What's
left is Substreams (explicitly scoped out, see [Build Timeline](#build-timeline)), a fully-connected
dashboard demo, and the submission itself.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [The Core Innovation — x402-Gated MCP Server](#the-core-innovation--x402-gated-mcp-server)
3. [System Architecture](#system-architecture)
4. [Layer 1 — The Graph, Free & Load-Bearing](#layer-1--the-graph-free--load-bearing)
5. [Layer 2 — LangGraph Intelligence Pipeline](#layer-2--langgraph-intelligence-pipeline)
6. [x402 Payment Flow — Step by Step](#x402-payment-flow--step-by-step)
7. [Layer 3 — Identity & Visibility](#layer-3--identity--visibility)
8. [What's Live in This Repo Right Now](#whats-live-in-this-repo-right-now)
9. [Development Workflow](#development-workflow)
10. [Repository Structure](#repository-structure-target)
11. [Tech Stack](#tech-stack)
12. [Environment Variables](#environment-variables)
13. [Running Locally](#running-locally)
14. [Demo Strategy](#demo-strategy)
15. [Hackathon Qualification Mapping](#hackathon-qualification-mapping)
16. [Build Timeline](#build-timeline)
17. [Build Checklist](#build-checklist)
18. [Why RIA Wins](#why-ria-wins)

---

## Executive Summary

RIA (Reconnaissance Intelligence Agent) is an autonomous, multi-agent DeFi intelligence system
with three distinct layers: a free, open data foundation from The Graph; a commercial x402-gated
MCP server that any AI agent can pay to use; and a real-time dashboard that makes every agent
decision and on-chain payment visible to judges and users.

| Dimension | Detail |
|---|---|
| Project name | RIA — Reconnaissance Intelligence Agent |
| Tagline | On-chain intelligence that acts. |
| **Core innovation** | x402-gated MCP server: any AI agent pays per tool call in HBAR — no API key, no subscription |
| Track 1 | The Graph — Best AI Use Case (From Scratch) |
| Track 2 | Hedera — AI & Agentic Payments |
| Track 3 | ENS — Best Use of ENSv2 (bonus) |
| Core stack | The Graph · Hedera (x402/HBAR) · MCP · ENSv2 · LangGraph · Python · Next.js |
| Networks | Ethereum Mainnet (data) · Hedera Testnet (payments) · Sepolia (ENS) |
| **The Graph cost** | **$0** — entirely within free tier for the whole build window |

## The Core Innovation — x402-Gated MCP Server

The central architectural idea in RIA v3 isn't the DeFi agent — it's the commercial primitive
underneath it.

### The problem with current AI agent economics

Every AI agent that needs external data or compute today has a human somewhere managing API keys,
topping up credits, and handling billing. The agent fails silently when the key expires. Nobody
has built a generalized mechanism for agents to pay for services autonomously — until x402.

### What the MCP server is

RIA hosts a [Model Context Protocol](https://modelcontextprotocol.io) server over HTTP/SSE. Every
tool call on this server is gated behind an x402 payment check via **Blocky402** on Hedera
testnet. Before any tool executes, the calling agent must pay in HBAR. No payment → `402`
response. Payment confirmed → the tool executes and returns data.

```
Any AI Agent (MCP client)
        │
        │ tool call: get_risk_score(opportunity)
        ▼
x402-Gated MCP Server
        │
        │ HTTP 402 → "pay 0.002 HBAR to Blocky402"
        ▼
Agent pays HBAR on Hedera (sub-3s finality)
        │
        │ payment confirmed → tool executes
        ▼
MCP Server calls: CoinGecko + Etherscan + Claude LLM
        │
        │ synthesized risk score returned
        ▼
Agent receives enrichment, continues reasoning
```

This is not RIA-specific infrastructure. **Any** MCP-compatible AI agent — Claude, GPT, Gemini, a
LangGraph agent, a CrewAI agent — can connect to this server and pay per call. RIA's ORACLE agent
is the first consumer and the proof of concept; the MCP server is the product.

### Priced tools

| MCP tool | What it does | Data sources behind it | Price per call |
|---|---|---|---|
| `get_gas_price(network)` | Current gas price + EIP-1559 base fee | Etherscan Gas Tracker (free tier) | 0.0005 HBAR |
| `get_sentiment(protocol)` | Sentiment score for a protocol (0–1) | LLM synthesis over recent on-chain signals | 0.001 HBAR |
| `get_risk_score(opportunity)` | Risk-adjusted confidence delta for a signal — the main SKU | LLM inference: gas + price + position data | 0.002 HBAR |
| `get_price_feed(token)` | Spot price + 24h change | CoinGecko (free tier) | 0.0005 HBAR |
| `stream_liquidation_alerts(protocol, threshold)` | Pre-filtered liquidation-proximity alerts | Substreams, processed and normalized | 0.001 HBAR / alert |

The raw Substreams data behind `stream_liquidation_alerts` is free from The Graph — what the MCP
server sells would be the filtered, normalized, agent-ready stream on top of it. That's a defensible
commercial model, not a resale of public data — but Substreams itself was scoped out for time (see
[Build Timeline](#build-timeline)), so this specific tool correctly fails loud rather than faking
alert data; the other four tools are unaffected.

### Why MCP over a plain gated endpoint

| Dimension | Plain FastAPI x402 endpoint | x402-gated MCP server |
|---|---|---|
| Consumer | RIA only — custom integration required | Any MCP-compatible AI agent — zero integration work |
| Discovery | Not discoverable — hardcoded URL | Discoverable via MCP marketplace / tool registry |
| Tool schema | Custom JSON — every consumer parses differently | Standardized MCP tool schema — universal |
| Commercial model | Implicit — a private endpoint that happens to charge | Explicit — a metered, per-tool, autonomous payment primitive |
| Differentiation | Low — any team can build a FastAPI + x402 endpoint | High — MCP + x402 is a first-mover combination at this hackathon |

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        RIA — FULL SYSTEM (v3)                               │
├──────────────────┬──────────────────────┬──────────────────────────────────┤
│  LAYER 1         │  LAYER 2             │  LAYER 3                         │
│  FREE DATA       │  INTELLIGENCE        │  COMMERCIAL ENRICHMENT           │
│  FOUNDATION      │  PIPELINE            │  + IDENTITY + VISIBILITY         │
│                  │                      │                                  │
│  The Graph       │  LangGraph           │  x402-Gated MCP Server           │
│  ─────────────   │  StateGraph          │  ─────────────────────────       │
│                  │  ─────────────       │  get_gas_price()    0.0005 HBAR  │
│  Subgraph Studio │  RECON               │  get_sentiment()    0.001  HBAR  │
│  (GraphQL)       │    ↓ (Graph data)    │  get_risk_score()   0.002  HBAR  │
│  Free tier:      │  SCOUT               │  get_price_feed()   0.0005 HBAR  │
│  100k q/month    │    ↓                 │  stream_alerts()    0.001  HBAR  │
│                  │  RISK                │  (per alert)                     │
│  Substreams      │    ↓                 │                                  │
│  scoped out for  │  ORACLE──────────────┼──► pays x402, calls MCP tools   │
│  time -- not     │    ↓ (enriched)      │                                  │
│  attempted, not  │  EXEC                │  Hedera Testnet                  │
│  mocked          │    ↓                 │  ─────────────────────────       │
│                  │  AUDIT               │  x402 payments (Blocky402)       │
│  Direct queries  │    ↓                 │  HCS audit trail                 │
│  by RECON agent  │  WebSocket ──────────┼──► Dashboard feed                │
│                  │  stream              │                                  │
│                  │                      │  ENSv2 (Sepolia)                 │
│                  │                      │  oracle.agentria.eth              │
│                  │                      │  exec.agentria.eth                │
│                  │                      │                                  │
│                  │                      │  Next.js Dashboard               │
│                  │                      │  4 panels, read-only observer    │
└──────────────────┴──────────────────────┴──────────────────────────────────┘

  Any external AI agent (Claude, GPT, CrewAI) can also connect to the
  x402-Gated MCP Server directly — RIA is the first consumer, not the only one.
```

## Layer 1 — The Graph, Free & Load-Bearing

RECON queries The Graph directly — no payment gate, no intermediary. This is the open data
foundation RIA is built on. **The Graph data never routes through the x402 MCP server**: it's
free, public, and open, and gating it behind payments would be architecturally wrong and
philosophically backwards.

Two Graph products are composed live today; a third was scoped out for time (not attempted, not
mocked — see [Build Timeline](#build-timeline)):

| Product | How RECON uses it | Query pattern | Status |
|---|---|---|---|
| Subgraph Studio | GraphQL queries for pool TVL, volume, rates against real mainnet Uniswap v3 + Aave v3 | 2 queries/cycle, both protocols | ✅ Live — real queries every pipeline cycle |
| Messari Standardized Subgraphs | One schema spans Uniswap, Aave, Compound, Curve simultaneously | 1 query shape → N protocols (see `SKILL.md`) | ✅ Live — same query shape against both live deployments |
| Substreams (Graph Market) | Block-by-block liquidation-proximity event stream | Subscribe, receive pushed events | 🔜 Scoped out — `stream_liquidation_alerts` fails loud rather than faking data |

### Confirmed free-tier usage

| Product | Free tier | Cost |
|---|---|---|
| Subgraph Studio | 100,000 queries/month | $0 — real usage this build is a small fraction of that |
| After the hackathon, at scale | $2 / 100k queries | Very manageable unit economics |

**RIA operates entirely within free tiers — no GRT, no credit card, no billing setup required.**

## Layer 2 — LangGraph Intelligence Pipeline

Six specialized agents in a LangGraph `StateGraph` with conditional routing edges. Typed state
carries portfolio context, risk thresholds, and HBAR payment budget across every hop.

| Agent | Role | Data source | Output |
|---|---|---|---|
| **RECON** | Ingest + normalize on-chain data | The Graph Subgraph Studio — free | Normalized opportunity signals |
| **SCOUT** | Rank opportunities by raw potential | RECON output | Ranked opportunity list with scores |
| **RISK** | Score and size positions | SCOUT output + portfolio state | Risk-adjusted recommendations |
| **ORACLE** | Enrich signals — pays the x402 MCP server | x402 MCP server tools (paid in HBAR) | Enriched signals with confidence delta |
| **EXEC** | Gate and dispatch actions | ORACLE output + risk threshold config | Executed actions or human alert queue |
| **AUDIT** | Log every action on-chain | EXEC output | Tamper-proof HCS entries |

**Containment rule:** ORACLE is the *only* agent with HBAR payment authority. RECON, SCOUT, RISK,
EXEC, and AUDIT cannot trigger x402 payments — a reasoning error in any other agent can't drain
the wallet. RISK routes high-confidence signals to EXEC and low-confidence signals to a human
alert queue in the dashboard. A WebSocket server runs alongside the pipeline, streaming typed
state updates (`SIGNAL`, `TRACE`, `PAYMENT`, `AUDIT`) to the dashboard in real time.

## x402 Payment Flow — Step by Step

| Step | Actor | Action | On-chain? |
|---|---|---|---|
| 1 | ORACLE agent | Sends MCP tool call: `get_risk_score(opportunity)` | No |
| 2 | x402 middleware | Intercepts the request, returns HTTP 402 with payment instructions — "pay 0.002 HBAR to Blocky402" | No |
| 3 | ORACLE agent | Reads the 402 header, constructs a Hedera `CryptoTransfer` transaction, signs with its agent wallet key | No |
| 4 | Hedera testnet | Transaction confirmed in < 3 seconds, sub-cent fee | **Yes — Hedera** |
| 5 | Blocky402 | Confirms payment on-chain, issues a short-lived access token | **Yes — Hedera** |
| 6 | ORACLE agent | Retries the MCP tool call with the access token in the header | No |
| 7 | MCP server | Token valid — the tool executes: calls Etherscan + CoinGecko + Claude, returns the enriched signal | No |
| 8 | AUDIT agent | Logs tool name, HBAR amount, Hedera tx ID, response hash → HCS topic | **Yes — Hedera HCS** |
| 9 | Dashboard | Payment Monitor panel updates with the tx ID and a live HashScan link | No (reads HCS) |

## Layer 3 — Identity & Visibility

### Hedera infrastructure

| Component | Purpose | Implementation |
|---|---|---|
| Blocky402 facilitator | Verifies HBAR payments before tool execution | x402 middleware registered with Blocky402 on Hedera testnet |
| HBAR agent wallet | ORACLE holds its own wallet, pays per call from a session budget | Hedera SDK — funded from the testnet faucet at startup |
| HCS audit trail | Tamper-proof, block-timestamped action log | AUDIT writes a JSON payload to an HCS topic after every EXEC cycle |
| ERC-8004 identity | On-chain agent identity standard | Each RIA agent registered as an ERC-8004 identity on Hedera testnet |

### ENSv2 agent identity (Sepolia)

Each core agent carries its own ENSv2 subname with isolated permissions via the Permissioned
Resolver — one agent can't touch another's records. Isolation is enforced by ENSv2's Enhanced
Access Control: each subname's node is its own on-chain permission scope, and only that agent's
own derived signing key is ever granted the role to write it — a write from any other key reverts
on-chain (`EACUnauthorizedAccountRoles`), not just a convention this codebase happens to follow.
Metadata follows ENSIP-26 so identities are discoverable and composable by other protocols.

| ENS name | Agent | Text records (ENSIP-26) | Access control |
|---|---|---|---|
| `recon.agentria.eth` | RECON | endpoint, version, capabilities: data-ingestion | RECON only can update |
| `oracle.agentria.eth` | ORACLE | endpoint, version, capabilities: enrichment+payment | ORACLE only can update |
| `exec.agentria.eth` | EXEC | endpoint, version, capabilities: execution-gating | EXEC only can update |
| `audit.agentria.eth` | AUDIT | hcs-topic-id, version, capabilities: audit-logging | AUDIT only can update |

### Real-time dashboard

RIA's backend pipeline is powerful — but invisible to judges watching a terminal. The dashboard is
the window that proves the agent is working: a Next.js app with a WebSocket connection to the
Python pipeline, four live panels, and zero write access to the pipeline itself.

| Panel | WebSocket event | What a judge sees |
|---|---|---|
| Opportunities Feed | `SIGNAL` from SCOUT | Live DeFi signals: protocol, type, raw confidence, timestamp |
| Agent Trace | `TRACE` from every StateGraph node | Active agent, reasoning step, routing decision, threshold |
| Payment Monitor | `PAYMENT` from ORACLE after each x402 call | Tool called, HBAR amount, Hedera tx ID, live HashScan link |
| HCS Audit Trail | `AUDIT` event + HCS mirror node poll | Last 10 AUDIT entries with an HCS topic link for verification |

**The dashboard does not execute actions — it only observes.** This keeps the agent's autonomy
intact while giving judges interactive, live proof of every decision and payment.

## What's Live in This Repo Right Now

| Component | Status |
|---|---|
| Project proposal & architecture (v3) | ✅ Complete |
| Public landing page (`/`) — [ria-agent.vercel.app](https://ria-agent.vercel.app) | ✅ Live |
| Dashboard interface preview (`/app`) — [ria-agent.vercel.app/app](https://ria-agent.vercel.app/app) | ✅ Live (static preview, illustrative data) |
| README with self-updating status | ✅ Live (this file) |
| RECON — Subgraph Studio client + normalization (`graph/`, `agents/recon.py`) | ✅ **Live** — real `GRAPH_API_KEY` queries against both corrected subgraph ids, real pool/market counts back each cycle |
| Substreams (liquidation event stream) | 🔜 Not started |
| SCOUT / RISK / EXEC — LangGraph agents (`agents/scout.py`, `risk.py`, `exec.py`) | ✅ **Live** — ran against real RECON output: SCOUT ranked real signals, RISK correctly gated them against threshold, EXEC correctly held dispatch pending ORACLE enrichment (its actual dispatch path still needs a run with ORACLE's wallet configured too) |
| `pipeline/graph.py` — full RECON→SCOUT→RISK→ORACLE→EXEC→AUDIT StateGraph | ✅ **Live** — ran end-to-end against real `GRAPH_API_KEY` credentials, multiple real cycles; ORACLE/AUDIT ran but had nothing to do without Hedera credentials in the same process (see ORACLE row below for that half, live separately) |
| `pipeline/ws_server.py` / `runner.py` — WebSocket feed + CLI entrypoint | ✅ **Live** — ran real multi-cycle loops, WebSocket server bound and serving; a browser client actually consuming that feed is tracked separately below |
| `mcp_server/` — x402-gated MCP server + 5 priced tools | ✅ **Live on Hedera testnet** — `get_gas_price` and `get_risk_score` both confirmed end-to-end, repeatedly, against the real Blocky402 facilitator (see below); `get_sentiment`/`get_price_feed` run the same code path but aren't individually live-confirmed yet; `stream_liquidation_alerts` correctly fails loud (no mocked fallback) since it depends on the Substreams client, which was scoped out — see the Build Timeline |
| ORACLE — x402 payment client (`hedera/x402_client.py`, `agents/oracle.py`) | ✅ **Live on Hedera testnet** — one real paid `get_gas_price` call, settled, confirmed on the public mirror node (see below) |
| AUDIT — HCS logging (`hedera/hcs_logger.py`, `agents/audit.py`) | ✅ **Live on Hedera testnet** — one real message logged to topic `0.0.10467384`, confirmed on the public mirror node (see below) |
| ENSv2 subname registration (`ens/`) | ✅ **Live on Sepolia** — all 4 subnames registered, isolation verified on-chain, independently re-confirmed with a fresh read-only `text()` call (see below) |
| ERC-8004 agent identity (`hedera/erc8004.py`) | ✅ **Live on Hedera testnet** — Identity Registry deployed, all 4 agents registered, independently confirmed on the mirror node (see below) |
| Live WebSocket feed → dashboard | 🟡 Dashboard now wired (`src/hooks/useRiaSocket.ts`) and verified against a real WebSocket connection with synthetic pipeline events — needs `pipeline/runner.py` actually running (with a live `GRAPH_API_KEY`) for the dashboard to show real signals instead of the honest preview fallback |
| Demo video | 🔜 Before submission |

**211+ tests pass with zero live credentials or network access required** — every module above mocks its external dependency (the Graph Gateway, Blocky402, Hedera SDK submission, Sepolia RPC) rather than skipping the test. What's missing everywhere else is the same thing: real funded accounts and a live run to actually flip a [Build Checklist](#build-checklist) box, which only happens when `verify-checklist.mjs` (or a human, for anything that spends HBAR/ETH) proves it — see [Development Workflow](#development-workflow). ENSv2, the x402 payment flow, HCS audit logging, and ERC-8004 identity below have cleared that bar for real.

**Live on Hedera testnet right now** — a real, unmocked x402 payment, verifiable by anyone on the public mirror node:

| Step | Value |
|---|---|
| Tool called | `get_gas_price` via the x402-gated MCP server (streamable-http) |
| Buyer (ORACLE's wallet) | `0.0.10262725` |
| Resource server (`payTo`) | `0.0.10451954` |
| Facilitator (fee payer) | `0.0.9185802` (Blocky402, `api.testnet.blocky402.com`) |
| Amount | 0.0005 HBAR (50,000 tinybars) |
| Settlement tx | [`0.0.9185802-1789031699-073655128`](https://hashscan.io/testnet/transaction/0.0.9185802-1789031699-073655128) — `SUCCESS`, confirmed on the [public mirror node](https://testnet.mirrornode.hedera.com/api/v1/transactions/0.0.9185802-1789031699-073655128) |

That was a one-off manual smoke test. Since then, ORACLE has paid **autonomously and repeatedly** through the real `pipeline/runner.py` loop — no script, no human triggering each call. A representative example, independently pulled from the mirror node's own transaction history for the account (not the pipeline's log output): [`0.0.7162784-1789120758-359904050`](https://hashscan.io/testnet/transaction/0.0.7162784-1789120758-359904050), `get_risk_score` (0.002 HBAR), buyer `0.0.10452229` → resource server `0.0.10451954`, facilitator `0.0.7162784` — one of over a dozen consecutive `SUCCESS` transfers of the same shape in that run.

AUDIT's HCS trail is live too — one real message, independently decoded and confirmed against the mirror node (not just the script's own claim):

| Step | Value |
|---|---|
| Topic | [`0.0.10467384`](https://hashscan.io/testnet/topic/0.0.10467384) |
| Message | `{"type": "PAYMENT", "tool_name": "get_gas_price", "hbar_amount": 0.0005, ...}` — sequence #1, payer `0.0.10452229` |
| Verify yourself | [mirror node topic messages](https://testnet.mirrornode.hedera.com/api/v1/topics/0.0.10467384/messages) — base64-decode `message` to see the JSON payload |

ERC-8004 agent identity is live too — a real Identity Registry deployment, all 4 agents registered:

| Agent | Agent id | Register tx |
|---|---|---|
| RECON | 1 | [`0.0.10452229@1789087900`](https://hashscan.io/testnet/transaction/0.0.10452229-1789087900-248740196) |
| ORACLE | 2 | [`0.0.10452229@1789087902`](https://hashscan.io/testnet/transaction/0.0.10452229-1789087902-449367046) |
| EXEC | 3 | [`0.0.10452229@1789087909`](https://hashscan.io/testnet/transaction/0.0.10452229-1789087909-98556995) |
| AUDIT | 4 | [`0.0.10452229@1789087915`](https://hashscan.io/testnet/transaction/0.0.10452229-1789087915-806875944) |

Registry: [`0.0.10468445`](https://hashscan.io/testnet/contract/0.0.10468445), EVM address `0x00000000000000000000000000000000009fbc5d` — global agent id format is `eip155:296:<registry evm address>:<agentId>`. Independently verified with a raw, unauthenticated mirror-node `/contracts/call` query against `ownerOf(1)`/`tokenURI(1)` — `ownerOf` matched the registering account's real EVM address, and `tokenURI` decoded to RECON's exact registration document, not just the script's own claim.

**Live on Sepolia right now** — resolve any of these yourself, no trust required:

| Agent | ENS name | Operator (only key that can write it) |
|---|---|---|
| RECON | [`recon.agentria.eth`](https://sepolia.app.ens.domains/recon.agentria.eth) | `0x6968cc4b2674b5ca9559e9FD9EA7580c90EB8280` |
| ORACLE | [`oracle.agentria.eth`](https://sepolia.app.ens.domains/oracle.agentria.eth) | `0x5f7F17577B858afDDff1685B8D7717724c878ff9` |
| EXEC | [`exec.agentria.eth`](https://sepolia.app.ens.domains/exec.agentria.eth) | `0xb01689952da0624390ce5227B5CcA8cbBebEE3B8` |
| AUDIT | [`audit.agentria.eth`](https://sepolia.app.ens.domains/audit.agentria.eth) | `0xcC257BDe07909f076eE19cFEA139F50b0134A388` |

Shared Permissioned Resolver: [`0x5b5aF2C6EC2B9941ef073B0681984dB739fAca4B`](https://sepolia.etherscan.io/address/0x5b5aF2C6EC2B9941ef073B0681984dB739fAca4B) · Subregistry: `0xf1d8Bc687E5f160344Ee3015c0292eea5E5f564C` — `verify_isolation()` ran against the real chain after registration and confirmed none of the four operator keys can write another agent's node.

The dashboard preview ships with static, clearly-labeled illustrative data so the finished
interface can be evaluated ahead of the live pipeline going up. Progress from here is tracked
literally, box by box, in the [Build Checklist](#build-checklist) — the [Live Status](#-live-status)
block above reflects it automatically on every push.

## Development Workflow

RIA is built solo, but developed like a small, disciplined team — fittingly, since the product
itself is a multi-agent system. Work is split across specialized
[Claude Code subagents](.claude/agents/) with fixed ownership boundaries, so each change stays
scoped and reviewable instead of one sprawling context doing everything at once:

| Agent | Owns | Definition |
|---|---|---|
| `hedera-payments-engineer` | `mcp_server/`, `hedera/`, the x402 payment flow, ORACLE's wallet, HCS logging, ERC-8004 | [`.claude/agents/hedera-payments-engineer.md`](.claude/agents/hedera-payments-engineer.md) |
| `langgraph-pipeline-engineer` | `pipeline/`, SCOUT, RISK, EXEC, the StateGraph wiring, the WebSocket feed | [`.claude/agents/langgraph-pipeline-engineer.md`](.claude/agents/langgraph-pipeline-engineer.md) |
| `ens-identity-engineer` | `ens/`, ENSv2 subname registration, the Permissioned Resolver | [`.claude/agents/ens-identity-engineer.md`](.claude/agents/ens-identity-engineer.md) |
| `frontend-integrator` | `src/` — landing page, dashboard, wiring the UI to live data as it lands | [`.claude/agents/frontend-integrator.md`](.claude/agents/frontend-integrator.md) |
| `submission-lead` | ETHGlobal rule compliance, checklist honesty, README status, deadline tracking | [`.claude/agents/submission-lead.md`](.claude/agents/submission-lead.md) |

Two things keep the public status trustworthy rather than self-reported:

- **Live verification, not checkbox honor system.** [`verify-checklist.mjs`](.github/scripts/verify-checklist.mjs)
  runs on every push and actually queries the live Graph Gateway (using a `GRAPH_API_KEY` GitHub
  Actions secret — never a local `.env` file) before it will check a box. It only ever moves a box
  from unchecked to checked; nothing flips back on a transient failure.
- **Commit hygiene matches ETHGlobal's own rules.** Submissions with large single commits or
  missing history [can be disqualified](https://ethglobal.com/events/ethonline2026/info/details) —
  work lands in small, real, incremental commits for exactly that reason, not just as a nicety.

## Repository Structure (target)

The frontend below is live today at the repo root. Everything else is the planned Python backend,
per [Build Timeline](#build-timeline):

```
AgentRIA/
├── src/
│   ├── app/
│   │   ├── page.tsx           # Landing page  →  ria-agent.vercel.app
│   │   ├── app/page.tsx       # Dashboard      →  ria-agent.vercel.app/app
│   │   ├── layout.tsx
│   │   └── globals.css
│   ├── components/             # Shared UI (Nav, Footer, Brand, Card, Pill…)
│   └── hooks/useRiaSocket.ts   # ✅ built — typed WebSocket client for the live pipeline feed
├── agents/                      # ✅ all six built — recon · scout · risk · oracle · exec · audit
├── graph/
│   ├── subgraph_client.py      # ✅ built — Graph Gateway async client
│   ├── queries/messari.py      # ✅ built — DEX + lending query templates
│   └── substreams_client.py    # 🔜 scoped out for time, not attempted
├── mcp_server/                  # ✅ built — x402-gated MCP server (NEW in v3)
│   ├── server.py                #     FastMCP server (streamable-http mode)
│   ├── x402_middleware.py       #     Blocky402 payment verification middleware
│   ├── tools/                   #     gas_price · sentiment · risk_score · price_feed · liquidation_stream
│   └── pricing.py               #     per-tool HBAR price config
├── hedera/                      # ✅ built — wallet.py · x402_client.py · hcs_logger.py · key_loader.py · erc8004.py
│   └── contracts/               #     RIAIdentityRegistry.sol + compiled artifact (ERC-8004)
├── ens/                         # ✅ built — register.py · resolver.py · accounts.py · rpc.py
├── pipeline/                    # ✅ built — state.py · graph.py · runner.py · ws_server.py
├── scripts/                     # ✅ built — one-off live scripts (never wired into CI):
│   ├── live_smoke_test.py       #     one real x402 payment end-to-end
│   ├── hcs_smoke_test.py        #     one real HCS topic message end-to-end
│   ├── register_agents_live.py  #     live ENSv2 subname registration
│   ├── register_erc8004_live.py #     live ERC-8004 registry deploy + agent registration
│   └── external_agent_demo.py   #     independent 3rd-party agent paying x402 (the demo's killer moment)
├── tests/                       # ✅ 217 tests, all mocked — no live credentials required to run them
├── .claude/agents/               # the dev-team subagent briefs — see Development Workflow
├── .github/workflows/           # update-status.yml, tests.yml — CI + the Live Status block
├── assets/                      # Reference designs & project proposal
├── requirements.txt              # ✅ built
└── SKILL.md                      # ✅ written — Messari Standardized Subgraphs skill, for The Graph track
```

Environment variables (`GRAPH_API_KEY`, `HEDERA_ACCOUNT_ID`, …) are documented in
[Environment Variables](#environment-variables) below rather than a committed `.env.example` —
`.env*` paths are intentionally kept out of version control.

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Agent framework | LangGraph (Python) | StateGraph with conditional edges and a typed state object |
| LLM | Claude Sonnet via Anthropic API | Tool-calling across all 6 agents + LLM inference inside MCP tools |
| Data — Subgraph | The Graph Subgraph Studio | 100k free queries/month; ~17k used across the build window — $0 |
| Data — Schema | Messari Standardized Subgraphs | Single GraphQL schema spanning Uniswap, Aave, Compound, Curve |
| Data — Streams | The Graph Market (Substreams) | 🔜 Scoped out for time — not attempted, not mocked |
| MCP server | Python MCP SDK (streamable-http mode) | Standalone server — any MCP agent can connect |
| x402 payments | Hedera x402 + Blocky402 | Per-tool HBAR micropayments, sub-3s finality on testnet |
| Payment-side enrichment APIs | Etherscan (free) + CoinGecko (free, TTL-cached) + Claude API | What the MCP tools call internally once payment is confirmed |
| Audit trail | Hedera Consensus Service (HCS) | Tamper-proof, block-timestamped action log |
| Agent identity (Hedera) | ERC-8004 | On-chain agent identity standard on Hedera testnet |
| Agent identity (ENS) | ENSv2 on Sepolia | Permissioned Resolver + Enhanced Access Control per agent |
| Frontend | Next.js 16 + TypeScript + Tailwind CSS v4 | This repo — landing + dashboard, deployed on Vercel |
| Dashboard feed | Python `websockets` + React hooks | ✅ Live — `useRiaSocket.ts`, typed `SIGNAL`/`TRACE`/`PAYMENT`/`AUDIT` events |
| Testing | pytest | ✅ 217 tests, fully mocked — no live credentials needed to run them |

## Environment Variables

| Variable | Where to get it | Cost |
|---|---|---|
| `GRAPH_API_KEY` | Subgraph Studio → API Keys tab | Free (100k queries/month) |
| `GRAPH_MARKET_TOKEN` | thegraph.market → account → token — not currently used; Substreams was scoped out (see [Build Timeline](#build-timeline)) | Free (7M blocks + 5 GiB) |
| `HEDERA_ACCOUNT_ID` | Hedera Testnet Portal | Free testnet |
| `HEDERA_PRIVATE_KEY` | Hedera Testnet Portal | Free testnet |
| `ANTHROPIC_API_KEY` | console.anthropic.com | Pay per token — minimal for a hackathon build |
| `ETHERSCAN_API_KEY` | etherscan.io/apis | Free tier (5 calls/sec) |
| `COINGECKO_API_KEY` | coingecko.com/en/api | Free tier (30 calls/min) |
| `BLOCKY402_FACILITATOR_URL` | `https://api.testnet.blocky402.com` — confirmed live, no signup/API key | Free — Blocky402 is open access on Hedera testnet |
| `HCS_TOPIC_ID` | One-time `HcsLogger.create_topic()` call (`hedera/hcs_logger.py`) | Small fixed Hedera network fee to create |
| `MCP_SERVER_URL` | Wherever `mcp_server/server.py` is running (default `http://127.0.0.1:8000/mcp`) | n/a — your own server |
| `ENS_PRIVATE_KEY` | Sepolia wallet with test ETH, owning `agentria.eth` | Free from a Sepolia faucet |
| `SEPOLIA_RPC_URL` | Infura / Alchemy / a public Sepolia gateway | Free tier |
| `RIA_SUBREGISTRY_ADDRESS` *(optional)* | agentria.eth's own ENSv2 subregistry (holds recon/oracle/exec/audit as child labels) — printed by `scripts/register_agents_live.py` after its first run | Deploys a fresh one via ENSv2's VerifiableFactory if unset |
| `RIA_RESOLVER_ADDRESS` *(optional)* | The shared ENSv2 Permissioned Resolver proxy RIA's four subnames resolve through — printed by `scripts/register_agents_live.py` after its first run | Deploys a fresh one via ENSv2's VerifiableFactory if unset |
| `ERC8004_REGISTRY_CONTRACT_ID` *(optional)* | RIA's ERC-8004 Identity Registry contract id — printed by `scripts/register_erc8004_live.py` after its first run | Deploys a fresh registry via the Hedera File + Smart Contract Service if unset |

## Running Locally

This repo ships a project-scoped `.mcp.json` that wires up the
[Hedera Docs MCP server](https://docs.hedera.com/hedera/tutorials/more-tutorials/hedera-mcp-server-setup-guide)
so any AI coding agent working in this repo can query Hedera's docs directly. Optionally add the
[Hedera Skills](https://github.com/hedera-dev/hedera-skills) plugin marketplace too —
`/plugin marketplace add hedera-dev/hedera-skills` in Claude Code — for the Agent Kit and
submission-validator skills.

Both halves of RIA are built and run live today — this is the actual, current command set (not
aspirational), matching what this build has been run with:

```bash
git clone https://github.com/arrnaya/AgentRIA.git
cd AgentRIA

# Frontend
npm install

# Backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pytest   # 217 tests, fully mocked — no credentials needed
```

Three terminals for the full live stack (a fourth if you also want the frontend dev server open
locally instead of just visiting the deployed site):

```bash
# Terminal 1 — x402-gated MCP server (streamable-http mode; ORACLE's client needs the
# session-handshake support that mode provides, not the sse default)
export HEDERA_ACCOUNT_ID=0.0.xxxxx        # this server's payTo account — must differ from
                                            # Terminal 2's ORACLE wallet, or every payment
                                            # nets to zero (a native transfer to yourself)
export BLOCKY402_FACILITATOR_URL=https://api.testnet.blocky402.com
export ETHERSCAN_API_KEY=...
export ANTHROPIC_API_KEY=...
export MCP_TRANSPORT=streamable-http
python -m mcp_server.server
# → binds 127.0.0.1:8000 by default (MCP_HOST/MCP_PORT to change)

# Terminal 2 — RIA agent pipeline + WebSocket server
export GRAPH_API_KEY=...
export HEDERA_ACCOUNT_ID=0.0.yyyyy         # ORACLE's own wallet — different account than Terminal 1
export HEDERA_PRIVATE_KEY=...
python pipeline/runner.py --mode live --risk-threshold 0.65 --budget-hbar 10 --interval 30 --ws-port 3002
# --mcp-server <url> overrides Terminal 1's address if it isn't the 127.0.0.1:8000 default

# Terminal 3 — Next.js dashboard, pointed at Terminal 2's WebSocket port
export NEXT_PUBLIC_RIA_WS_URL=ws://localhost:3002
npm run dev
# → http://localhost:3000/app — watch for "Pipeline: Connected" and each panel's LIVE badge
```

Optional one-time live setup scripts (each spends real, free testnet HBAR/ETH and is deliberately
not wired into CI — see each script's own docstring before running):

```bash
python scripts/live_smoke_test.py           # one real x402 payment, end-to-end
python scripts/external_agent_demo.py       # an independent agent (own wallet) paying 4 of the 5 tools
python scripts/hcs_smoke_test.py            # one real HCS topic message
python scripts/register_agents_live.py      # ENSv2 subname registration (Sepolia)
python -m scripts.register_erc8004_live     # ERC-8004 identity registration (Hedera testnet)
```

## Demo Strategy

The demo has one job: show that every claim is verifiable on-chain, live. No pre-recorded output,
no mocked data — every panel updates during the recording. [`DEMO_SCRIPT.md`](DEMO_SCRIPT.md) is the
full word-for-word version of the table below — exact commands, exact narration, a pre-flight
checklist, and what to do if a segment doesn't cooperate live.

| Time | Action | What a judge sees |
|---|---|---|
| 0:00–0:20 | Open the dashboard and the MCP server logs side by side | Four panels empty — pipeline not started, MCP server idle |
| 0:20–0:50 | Start the pipeline | Opportunities Feed populates: Uniswap yield gap + Aave liquidation proximity from live Graph data |
| 0:50–1:20 | Walk the Agent Trace panel | RECON → SCOUT → RISK progression, confidence scores, routing decision |
| 1:20–2:00 | ORACLE fires an x402 MCP call | MCP server log shows the call → 402 → payment → execution; Payment Monitor shows the HBAR amount + a live HashScan link |
| 2:00–2:20 | EXEC dispatches, AUDIT logs | Agent Trace shows the final routing; an HCS Audit Trail entry appears — click the mirror node link live |
| **2:20–2:40** | **The killer moment — a second agent connects** | `scripts/external_agent_demo.py` — a standalone script with its own wallet, never touching RIA's pipeline — connects to the MCP server cold, gets a 402, pays HBAR, and receives data back for 4 of the 5 tools — proof this is a generalized commercial primitive, not a RIA-only trick |
| 2:40–3:00 | Show ENS identity | ENS app on Sepolia resolves `oracle.agentria.eth` with live ENSIP-26 metadata |

The 2:20–2:40 moment is the single most memorable thing to show a judge: it proves the MCP server
works for *any* AI agent, not just RIA, in about 20 seconds and no judge forgets it.

## Hackathon Qualification Mapping

<details>
<summary><strong>The Graph — AI Use Case Track</strong></summary>

| Requirement | How RIA satisfies it |
|---|---|
| The Graph is load-bearing | RECON cannot function without Subgraph Studio — it's the sole on-chain data source. Zero mocked data. |
| Live data | Subgraph Studio API key, live against real mainnet Uniswap v3 + Aave v3 deployments, $0 within free tier — confirmed via a real multi-cycle pipeline run, not just a one-off test |
| Meaningful work with the data | 6-agent reasoning pipeline: detection → scoring → paid enrichment → execution → on-chain audit |
| AI use case | LangGraph multi-agent pipeline using Graph data for autonomous DeFi intelligence |
| Composable Graph products | Composes 2 products live — Subgraph Studio + Messari Standardized Subgraphs (one query shape, N protocols — see `SKILL.md`). Substreams was scoped out for time, not attempted and left unmocked. |
| Open source + SKILL.md + README | SKILL.md at repo root, full README, public GitHub repo |
| From Scratch pool | Net-new build — no prior project-specific code reused |

</details>

<details>
<summary><strong>Hedera — AI & Agentic Payments Track</strong></summary>

| Requirement | How RIA satisfies it |
|---|---|
| Live x402-gated service on Hedera testnet | The x402-gated MCP server, registered via Blocky402 on Hedera testnet — live, not mocked |
| A platform/agent that consumes it | ORACLE pays per MCP tool call autonomously — **and** a second, external agent shown live in the demo |
| One real paid request end-to-end | Live demo: MCP call → 402 → HBAR payment → Hedera tx confirmed → tool executes → data returned |
| Public repo + README | Full README covering the x402 architecture, MCP server setup, and the complete payment flow |
| Demo video ≤ 5 min | 3-minute demo with live HashScan tx verification |
| Extra: ERC-8004 agent identity | All RIA agents registered via ERC-8004 on Hedera testnet |
| Extra: HCS audit trail | AUDIT writes every payment + action hash to HCS, shown live in the dashboard |
| Extra: a generalized commercial model | The MCP server is usable by any AI agent, not RIA-specific — the strongest possible demo of the track's intent |

</details>

<details>
<summary><strong>ENS — Best Use of ENSv2</strong></summary>

| Requirement | How RIA satisfies it |
|---|---|
| Built on ENSv2 (Sepolia) | ✅ Live — all 4 agent subnames registered on the standard ENSv2 Beta Sepolia deployment, see [What's Live](#whats-live-in-this-repo-right-now) |
| ENSv2 features central to the product | ✅ Permissioned Resolver's Enhanced Access Control gives each agent an isolated per-node grant — `verify_isolation()` confirmed on the real chain that no agent's key can write another's node |
| Functional demo, not hard-coded | ✅ Live ENS app resolution of [`oracle.agentria.eth`](https://sepolia.app.ens.domains/oracle.agentria.eth) with real ENSIP-26 text records — resolvable by anyone right now, not staged for the demo video |
| Extra: AI agent namespace | ✅ 4 agents × subnames with ENSIP-26 metadata (endpoint, version, capabilities) live on-chain |

</details>

## Build Timeline

**Revised for the real deadline.** ETHOnline 2026's submission close is **Sunday, September 13,
2026, 12:00pm EDT** — confirmed from the [official rules](https://ethglobal.com/events/ethonline2026/info/details),
not the earlier "opens Sep 8" assumption this proposal started from. The original 6-day plan below
has been compressed into what's actually achievable in the time left, prioritized by prize weight
and by what makes the strongest live demo: the Hedera x402/MCP flow (highest prize, most
differentiated) and a working LangGraph pipeline come before ENS polish.

| Day | Focus | Deliverable |
|---|---|---|
| Sep 10 (today) | Data + Intelligence Layer | ✅ RECON done and tested. SCOUT + RISK + EXEC wired; LangGraph StateGraph routing confirmed; WebSocket server emitting `SIGNAL` + `TRACE` |
| Sep 11 | MCP Server + x402 | All 5 MCP tools implemented; Blocky402 middleware wired; ORACLE completing the full x402 payment flow end-to-end; HCS audit logging live |
| Sep 12 | Identity + Dashboard | ENSv2 subnames registered; dashboard panels wired to real WebSocket data; HashScan + HCS mirror node links confirmed live |
| Sep 13 (morning, before 12pm EDT) | Demo + Submit | SKILL.md + README finalized; demo video recorded; ETHGlobal submission completed with margin before the deadline, not at it |

If time runs short, cut scope in this order: ENS polish first (bonus track, smallest prize),
then the number of MCP tools demoed live (one real end-to-end payment beats five half-wired
ones), never the demo video or the submission itself.

## Build Checklist

The `Build checklist` line in [Live Status](#-live-status) is computed automatically by counting
the boxes below on every push — check one off in a commit and the status block updates itself.

- [x] Subgraph Studio API key live, querying Uniswap + Aave
- [x] Messari Standardized Subgraphs queries returning normalized data
- [ ] Substreams pipeline subscribed to ETH mainnet liquidation events
- [ ] x402-gated MCP server running, all 5 tools responding
- [x] Blocky402 facilitator registered, x402 middleware intercepting
- [x] ORACLE agent completing the full x402 payment flow end-to-end
- [x] HCS topic created, AUDIT agent writing entries
- [x] ERC-8004 agent identities registered
- [x] ENSv2 subnames registered with Permissioned Resolver
- [ ] Dashboard — all 4 panels updating with live data
- [ ] External agent (Claude Desktop or `curl`) connecting to the MCP server and paying x402
- [x] SKILL.md written describing The Graph integration
- [ ] README complete with architecture, setup, and payment flow
- [ ] 3-minute demo video following the demo script
- [ ] ETHGlobal submission with a public repo link

## Why RIA Wins

| Judging criterion | RIA v3's edge |
|---|---|
| Technical depth | 6-agent LangGraph pipeline + MCP server + x402 middleware + HCS + ERC-8004 + ENSv2 — not a chatbot wrapper |
| Graph product composition | 2 Graph products composed live (Studio + Standardized Subgraphs, one query shape spanning N protocols — see `SKILL.md`); Substreams scoped out for time, not claimed |
| Live data integrity | Zero mocked data; every Graph query hits live mainnet within free tier, verifiable in the demo |
| Hedera x402 completeness | Hosts the gated MCP server **and** consumes it — a full loop. A second external agent connecting proves generalization. |
| Commercial model clarity | The x402-gated MCP server is a first-mover demonstration of how AI agents should pay for services |
| Demo quality | Dashboard + live HashScan + live HCS + a second agent connecting — four independent on-chain verification points |
| Differentiation | MCP + x402 combined isn't common at this hackathon; a clean separation of the free Graph layer from the paid enrichment layer |
| Bonus criteria coverage | ERC-8004 identity + HCS audit trail + ENSv2 subnames — every Hedera bonus box checked |
| Builder credibility | MaalChain (EVM L1) · ORACLE (12-agent LangGraph bot) · ARIA (embodied AI) · ICUSD (stablecoin) — judges can verify each one |
| Reusability | The MCP server is standalone — other teams can build on it. SKILL.md makes the Graph integration reusable. |

---

## License

MIT — see [LICENSE](LICENSE).

## Builder

**Arrnaya (Arun Kumar Yadav)** · [github.com/arrnaya](https://github.com/arrnaya)

*RIA — Reconnaissance Intelligence Agent · On-chain intelligence that acts. · ETHGlobal Online 2026*
