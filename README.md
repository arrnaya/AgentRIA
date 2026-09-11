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
| **Current phase** | In progress — 4/15 build milestones verified |
| **Build checklist** | `█████░░░░░░░░░░░░░░░` 4/15 (27%) — verified live where possible, not self-reported |
| **Time to ETHGlobal deadline** | 2d 15h remaining (deadline: Sun Sep 13, 12:00pm EDT) |
| **Latest commit** | [`09b0543`](https://github.com/arrnaya/AgentRIA/commit/09b0543ac9289182b96e882907c523babf0db36c) Fix ERC-8004 register() gas budget -- 300k wasn't enough to store the agentURI — Arrnaya |
| **Total commits** | 97 |
| **Last updated** | 2026-09-11 00:43 UTC |

_This block is regenerated automatically by [.github/workflows/update-status.yml](.github/workflows/update-status.yml) on every push to `main`, after [verify-checklist.mjs](.github/scripts/verify-checklist.mjs) attempts to prove each checklist item live._
<!-- STATUS:END -->

This repo is being built in public and the block above tells the truth about progress — it's
computed from the checked boxes in the [Build Checklist](#build-checklist), not from a calendar.
Right now that's the project proposal, this README, and a live preview of the landing page and
dashboard interface. The Python agent pipeline (RECON, the MCP server, ORACLE's x402 flow, ENSv2
registration) lands next, checklist item by checklist item.

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
server sells is the filtered, normalized, agent-ready stream on top of it. That's a defensible
commercial model, not a resale of public data.

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
│  (streaming)     │  ORACLE──────────────┼──► pays x402, calls MCP tools   │
│  Free tier:      │    ↓ (enriched)      │                                  │
│  7M blocks       │  EXEC                │  Hedera Testnet                  │
│  + 5 GiB egress  │    ↓                 │  ─────────────────────────       │
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

Three Graph products are composed:

| Product | How RECON uses it | Query pattern | Free tier used |
|---|---|---|---|
| Subgraph Studio | GraphQL queries for pool TVL, APY, utilization, collateral ratios | 2 queries/min across 3 protocols | ~17k of 100k/month free |
| Messari Standardized Subgraphs | One schema spans Uniswap, Aave, Compound, Curve simultaneously | 1 query → 4 protocols normalized | Included in Studio queries |
| Substreams (Graph Market) | Block-by-block liquidation-proximity event stream | Subscribe, receive pushed events | ~300k of 7M blocks free |

### Confirmed free-tier math for the build window

| Product | Free tier | RIA usage (6-day build) | Cost |
|---|---|---|---|
| Subgraph Studio | 100,000 queries/month | ~17,280 queries (2/min × 60 × 24 × 6) | $0 — ~17% of free tier |
| Substreams (Graph Market) | 7M blocks + 5 GiB egress, no credit card | ~300,000 blocks (50k/day × 6 days) | $0 — ~4% of free tier |
| After the hackathon, at scale | $2 / 100k queries; $25/TB Substreams | Production scale | Very manageable unit economics |

**RIA operates entirely within free tiers for the whole build window — no GRT, no credit card, no
billing setup required.**

## Layer 2 — LangGraph Intelligence Pipeline

Six specialized agents in a LangGraph `StateGraph` with conditional routing edges. Typed state
carries portfolio context, risk thresholds, and HBAR payment budget across every hop.

| Agent | Role | Data source | Output |
|---|---|---|---|
| **RECON** | Ingest + normalize on-chain data | The Graph (Subgraph Studio + Substreams) — free | Normalized opportunity signals |
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
| RECON — Subgraph Studio client + normalization (`graph/`, `agents/recon.py`) | 🟡 Built & unit-tested — needs a live `GRAPH_API_KEY` to run for real |
| Substreams (liquidation event stream) | 🔜 Not started |
| SCOUT / RISK / EXEC — LangGraph agents (`agents/scout.py`, `risk.py`, `exec.py`) | 🟡 Built & unit-tested, no live dependency needed — these run entirely on RECON's output |
| `pipeline/graph.py` — full RECON→SCOUT→RISK→ORACLE→EXEC→AUDIT StateGraph | 🟡 Built & unit-tested — wired end-to-end, not yet run against live credentials |
| `pipeline/ws_server.py` / `runner.py` — WebSocket feed + CLI entrypoint | 🟡 Built & unit-tested — not yet run live against the dashboard |
| `mcp_server/` — x402-gated MCP server + 5 priced tools | ✅ **Live on Hedera testnet** — `get_gas_price` confirmed end-to-end against the real Blocky402 facilitator (see below); the other 4 priced tools run the same code path but aren't individually live-confirmed yet |
| ORACLE — x402 payment client (`hedera/x402_client.py`, `agents/oracle.py`) | ✅ **Live on Hedera testnet** — one real paid `get_gas_price` call, settled, confirmed on the public mirror node (see below) |
| AUDIT — HCS logging (`hedera/hcs_logger.py`, `agents/audit.py`) | ✅ **Live on Hedera testnet** — one real message logged to topic `0.0.10467384`, confirmed on the public mirror node (see below) |
| ENSv2 subname registration (`ens/`) | ✅ **Live on Sepolia** — all 4 subnames registered, isolation verified on-chain, independently re-confirmed with a fresh read-only `text()` call (see below) |
| ERC-8004 agent identity (`hedera/erc8004.py`) | 🟡 Built & unit-tested — Identity Registry contract + registration script ready, needs a live run (`scripts/register_erc8004_live.py`) to deploy and register for real |
| Live WebSocket feed → dashboard | 🟡 Dashboard now wired (`src/hooks/useRiaSocket.ts`) and verified against a real WebSocket connection with synthetic pipeline events — needs `pipeline/runner.py` actually running (with a live `GRAPH_API_KEY`) for the dashboard to show real signals instead of the honest preview fallback |
| Demo video | 🔜 Before submission |

**208+ tests pass with zero live credentials or network access required** — every module above mocks its external dependency (the Graph Gateway, Blocky402, Hedera SDK submission, Sepolia RPC) rather than skipping the test. What's missing everywhere else is the same thing: real funded accounts and a live run to actually flip a [Build Checklist](#build-checklist) box, which only happens when `verify-checklist.mjs` (or a human, for anything that spends HBAR/ETH) proves it — see [Development Workflow](#development-workflow). ENSv2, the x402 payment flow, and HCS audit logging below have cleared that bar for real.

**Live on Hedera testnet right now** — a real, unmocked x402 payment, verifiable by anyone on the public mirror node:

| Step | Value |
|---|---|
| Tool called | `get_gas_price` via the x402-gated MCP server (streamable-http) |
| Buyer (ORACLE's wallet) | `0.0.10262725` |
| Resource server (`payTo`) | `0.0.10451954` |
| Facilitator (fee payer) | `0.0.9185802` (Blocky402, `api.testnet.blocky402.com`) |
| Amount | 0.0005 HBAR (50,000 tinybars) |
| Settlement tx | [`0.0.9185802-1789031699-073655128`](https://hashscan.io/testnet/transaction/0.0.9185802-1789031699-073655128) — `SUCCESS`, confirmed on the [public mirror node](https://testnet.mirrornode.hedera.com/api/v1/transactions/0.0.9185802-1789031699-073655128) |

AUDIT's HCS trail is live too — one real message, independently decoded and confirmed against the mirror node (not just the script's own claim):

| Step | Value |
|---|---|
| Topic | [`0.0.10467384`](https://hashscan.io/testnet/topic/0.0.10467384) |
| Message | `{"type": "PAYMENT", "tool_name": "get_gas_price", "hbar_amount": 0.0005, ...}` — sequence #1, payer `0.0.10452229` |
| Verify yourself | [mirror node topic messages](https://testnet.mirrornode.hedera.com/api/v1/topics/0.0.10467384/messages) — base64-decode `message` to see the JSON payload |

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
│   └── components/            # Shared UI (Nav, Footer, Brand, Card, Pill…)
├── agents/                      # ✅ all six built — recon · scout · risk · oracle · exec · audit
├── graph/
│   ├── subgraph_client.py      # ✅ built — Graph Gateway async client
│   ├── queries/messari.py      # ✅ built — DEX + lending query templates
│   └── substreams_client.py    # 🔜
├── mcp_server/                  # ✅ built — x402-gated MCP server (NEW in v3)
│   ├── server.py                #     FastMCP server (HTTP/SSE mode)
│   ├── x402_middleware.py       #     Blocky402 payment verification middleware
│   ├── tools/                   #     gas_price · sentiment · risk_score · price_feed · liquidation_stream
│   └── pricing.py               #     per-tool HBAR price config
├── hedera/                      # ✅ built — x402_client.py · hcs_logger.py · wallet.py
├── ens/                         # ✅ built — register.py · resolver.py · accounts.py · rpc.py
├── pipeline/                    # ✅ built — state.py · graph.py · runner.py · ws_server.py
├── scripts/                     # ✅ built — one-off live scripts (never wired into CI):
│   ├── live_smoke_test.py       #     one real x402 payment end-to-end
│   └── register_agents_live.py  #     live ENSv2 subname registration
├── tests/                       # ✅ 151 tests, all mocked — no live credentials required to run them
├── .claude/agents/               # the dev-team subagent briefs — see Development Workflow
├── .github/workflows/           # update-status.yml, tests.yml — CI + the Live Status block
├── assets/                      # Reference designs & project proposal
├── requirements.txt              # ✅ built
└── SKILL.md                      # 🔜 required for The Graph track
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
| Data — Streams | The Graph Market (Substreams) | 7M blocks + 5 GiB free; ~300k blocks used — $0 |
| MCP server | Python MCP SDK (HTTP/SSE mode) | Standalone server — any MCP agent can connect |
| x402 payments | Hedera x402 + Blocky402 | Per-tool HBAR micropayments, sub-3s finality on testnet |
| Payment-side enrichment APIs | Etherscan (free) + CoinGecko (free) + Claude API | What the MCP tools call internally once payment is confirmed |
| Audit trail | Hedera Consensus Service (HCS) | Tamper-proof, block-timestamped action log |
| Agent identity (Hedera) | ERC-8004 | On-chain agent identity standard on Hedera testnet |
| Agent identity (ENS) | ENSv2 on Sepolia | Permissioned Resolver + Enhanced Access Control per agent |
| Frontend | Next.js 16 + TypeScript + Tailwind CSS v4 | This repo — landing + dashboard, deployed on Vercel |
| Dashboard feed | Python `websockets` + React hooks | 🔜 Typed events: `SIGNAL`, `TRACE`, `PAYMENT`, `AUDIT` |
| Testing | pytest + Hardhat fork | 🔜 Local fork for execution simulation; MCP tool unit tests |

## Environment Variables

| Variable | Where to get it | Cost |
|---|---|---|
| `GRAPH_API_KEY` | Subgraph Studio → API Keys tab | Free (100k queries/month) |
| `GRAPH_MARKET_TOKEN` | thegraph.market → account → token | Free (7M blocks + 5 GiB) |
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

## Running Locally

This repo ships a project-scoped `.mcp.json` that wires up the
[Hedera Docs MCP server](https://docs.hedera.com/hedera/tutorials/more-tutorials/hedera-mcp-server-setup-guide)
so any AI coding agent working in this repo can query Hedera's docs directly. Optionally add the
[Hedera Skills](https://github.com/hedera-dev/hedera-skills) plugin marketplace too —
`/plugin marketplace add hedera-dev/hedera-skills` in Claude Code — for the Agent Kit and
submission-validator skills.

The frontend in this repo runs standalone today:

```bash
git clone https://github.com/arrnaya/AgentRIA.git
cd AgentRIA
npm install
npm run dev
# → http://localhost:3000        (landing)
# → http://localhost:3000/app    (dashboard preview)
```

The Python backend is landing incrementally (see [What's Live](#whats-live-in-this-repo-right-now)).
What exists today — RECON's Subgraph Studio client — runs and tests like this:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Run the test suite (mocked Graph Gateway responses — no API key needed)
pytest

# Run RECON for real (needs a free key from https://thegraph.com/studio/)
export GRAPH_API_KEY=your_key_here
python -c "
import asyncio
from agents.recon import run_recon
from pipeline.state import RiaState

async def main():
    state = await run_recon(RiaState())
    for s in state.signals:
        print(s['protocol'], s['pair'], s['type'], s['raw_metrics'])

asyncio.run(main())
"
```

Once the rest of the backend lands, the full stack starts in four terminals:

```bash
# Terminal 1 — x402-gated MCP server
cd mcp_server
python server.py --host 0.0.0.0 --port 8080 --facilitator blocky402 --network testnet

# Terminal 2 — RIA agent pipeline + WebSocket server
python pipeline/runner.py \
  --mode live --networks ethereum,arbitrum,polygon \
  --risk-threshold 0.65 --budget-hbar 10 --interval 30 --ws-port 3001 \
  --mcp-server http://localhost:8080

# Terminal 3 — Next.js dashboard
npm run dev
# → http://localhost:3000

# Terminal 4 — watch the HCS audit trail live (optional)
python hedera/hcs_logger.py --follow --topic <TOPIC_ID>
```

## Demo Strategy

The demo has one job: show that every claim is verifiable on-chain, live. No pre-recorded output,
no mocked data — every panel updates during the recording.

| Time | Action | What a judge sees |
|---|---|---|
| 0:00–0:20 | Open the dashboard and the MCP server logs side by side | Four panels empty — pipeline not started, MCP server idle |
| 0:20–0:50 | Start the pipeline | Opportunities Feed populates: Uniswap yield gap + Aave liquidation proximity from live Graph data |
| 0:50–1:20 | Walk the Agent Trace panel | RECON → SCOUT → RISK progression, confidence scores, routing decision |
| 1:20–2:00 | ORACLE fires an x402 MCP call | MCP server log shows the call → 402 → payment → execution; Payment Monitor shows the HBAR amount + a live HashScan link |
| 2:00–2:20 | EXEC dispatches, AUDIT logs | Agent Trace shows the final routing; an HCS Audit Trail entry appears — click the mirror node link live |
| **2:20–2:40** | **The killer moment — a second agent connects** | A `curl` or Claude Desktop session connects to the MCP server cold, gets a 402, pays HBAR, and receives data back — proof this is a generalized commercial primitive, not a RIA-only trick |
| 2:40–3:00 | Show ENS identity | ENS app on Sepolia resolves `oracle.agentria.eth` with live ENSIP-26 metadata |

The 2:20–2:40 moment is the single most memorable thing to show a judge: it proves the MCP server
works for *any* AI agent, not just RIA, in about 20 seconds and no judge forgets it.

## Hackathon Qualification Mapping

<details>
<summary><strong>The Graph — AI Use Case Track</strong></summary>

| Requirement | How RIA satisfies it |
|---|---|
| The Graph is load-bearing | RECON cannot function without Subgraph Studio — it's the sole on-chain data source. Zero mocked data. |
| Live data | Subgraph Studio API key + Graph Market Substreams — all hitting live mainnet, $0 within free tiers |
| Meaningful work with the data | 6-agent reasoning pipeline: detection → scoring → paid enrichment → execution → on-chain audit |
| AI use case | LangGraph multi-agent pipeline using Graph data for autonomous DeFi intelligence |
| Composable Graph products | Composes 3 products — Subgraph Studio + Messari Standardized Subgraphs + Substreams — the highest tier |
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

- [ ] Subgraph Studio API key live, querying Uniswap + Aave
- [ ] Messari Standardized Subgraphs queries returning normalized data
- [ ] Substreams pipeline subscribed to ETH mainnet liquidation events
- [ ] x402-gated MCP server running, all 5 tools responding
- [x] Blocky402 facilitator registered, x402 middleware intercepting
- [x] ORACLE agent completing the full x402 payment flow end-to-end
- [x] HCS topic created, AUDIT agent writing entries
- [ ] ERC-8004 agent identities registered
- [x] ENSv2 subnames registered with Permissioned Resolver
- [ ] Dashboard — all 4 panels updating with live data
- [ ] External agent (Claude Desktop or `curl`) connecting to the MCP server and paying x402
- [ ] SKILL.md written describing The Graph integration
- [ ] README complete with architecture, setup, and payment flow
- [ ] 3-minute demo video following the demo script
- [ ] ETHGlobal submission with a public repo link

## Why RIA Wins

| Judging criterion | RIA v3's edge |
|---|---|
| Technical depth | 6-agent LangGraph pipeline + MCP server + x402 middleware + Substreams + HCS + ENSv2 — not a chatbot wrapper |
| Graph product composition | 3 Graph products composed (Studio + Standardized Subgraphs + Substreams) — the highest qualification tier |
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
