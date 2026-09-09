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
| **Current phase** | Architecture finalized (v3) — implementation not yet started |
| **Build checklist** | `░░░░░░░░░░░░░░░░░░░░` 0/15 (0%) |
| **ETHGlobal submission window** | Open since Sep 8, 2026 (day 2) |
| **Latest commit** | [`4d92ac8`](https://github.com/arrnaya/AgentRIA/commit/4d92ac88854d9ee57eea8aeb310ec170e4af55f7) Update repo to Architecture v3: x402-gated MCP server — Arrnaya |
| **Total commits** | 10 |
| **Last updated** | 2026-09-09 10:12 UTC |

_This block is regenerated automatically by [.github/workflows/update-status.yml](.github/workflows/update-status.yml) on every push to `main`._
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
9. [Repository Structure](#repository-structure-target)
10. [Tech Stack](#tech-stack)
11. [Environment Variables](#environment-variables)
12. [Running Locally](#running-locally)
13. [Demo Strategy](#demo-strategy)
14. [Hackathon Qualification Mapping](#hackathon-qualification-mapping)
15. [Build Timeline](#build-timeline)
16. [Build Checklist](#build-checklist)
17. [Why RIA Wins](#why-ria-wins)

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
│                  │                      │  ria-oracle.ria.eth              │
│                  │                      │  ria-exec.ria.eth                │
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
Resolver — one agent can't touch another's records. Metadata follows ENSIP-26 so identities are
discoverable and composable by other protocols.

| ENS name | Agent | Text records (ENSIP-26) | Access control |
|---|---|---|---|
| `ria-recon.ria.eth` | RECON | endpoint, version, capabilities: data-ingestion | RECON only can update |
| `ria-oracle.ria.eth` | ORACLE | endpoint, version, capabilities: enrichment+payment | ORACLE only can update |
| `ria-exec.ria.eth` | EXEC | endpoint, version, capabilities: execution-gating | EXEC only can update |
| `ria-audit.ria.eth` | AUDIT | hcs-topic-id, version, capabilities: audit-logging | AUDIT only can update |

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
| RECON — Subgraph Studio / Substreams client | 🔜 Not started |
| SCOUT / RISK — LangGraph agents | 🔜 Not started |
| `mcp_server/` — x402-gated MCP server + 5 priced tools | 🔜 Not started |
| ORACLE — MCP client + x402 payment flow | 🔜 Not started |
| AUDIT — HCS logging | 🔜 Not started |
| ENSv2 subname registration | 🔜 Not started |
| Live WebSocket feed → dashboard | 🔜 Not started |
| Demo video | 🔜 Before submission |

The dashboard preview ships with static, clearly-labeled illustrative data so the finished
interface can be evaluated ahead of the live pipeline going up. Progress from here is tracked
literally, box by box, in the [Build Checklist](#build-checklist) — the [Live Status](#-live-status)
block above reflects it automatically on every push.

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
├── agents/                    # 🔜 recon.py · scout.py · risk.py · oracle.py · exec.py · audit.py
├── graph/                     # 🔜 subgraph_client.py · substreams_client.py · queries/ (Messari schema)
├── mcp_server/                # 🔜 NEW in v3 — standalone x402-gated MCP server
│   ├── server.py              #     MCP server (HTTP/SSE mode)
│   ├── x402_middleware.py     #     Blocky402 payment verification middleware
│   ├── tools/                 #     gas_price · sentiment · risk_score · price_feed · liquidation_stream
│   └── pricing.py             #     per-tool HBAR price config
├── hedera/                    # 🔜 x402_client.py · hcs_logger.py · wallet.py
├── ens/                       # 🔜 register.py · resolver.py
├── pipeline/                  # 🔜 state.py · graph.py · runner.py · ws_server.py
├── tests/                     # 🔜
├── .github/workflows/         # update-status.yml — keeps the Live Status block current
├── assets/                    # Reference designs & project proposal
├── .env.example                # 🔜
└── SKILL.md                    # 🔜 required for The Graph track
```

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
| `ENS_PRIVATE_KEY` | Sepolia wallet with test ETH | Free from a Sepolia faucet |

## Running Locally

The frontend in this repo runs standalone today:

```bash
git clone https://github.com/arrnaya/AgentRIA.git
cd AgentRIA
npm install
npm run dev
# → http://localhost:3000        (landing)
# → http://localhost:3000/app    (dashboard preview)
```

Once the backend lands, the full stack starts in four terminals:

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
| 2:40–3:00 | Show ENS identity | ENS app on Sepolia resolves `ria-oracle.ria.eth` with live ENSIP-26 metadata |

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
| Built on ENSv2 (Sepolia) | All agent subnames registered on the ENSv2 Sepolia deployment |
| ENSv2 features central to the product | Permissioned Resolver gives each agent isolated record ownership — core to the identity model |
| Functional demo, not hard-coded | Live ENS app resolution of `ria-oracle.ria.eth` with ENSIP-26 text records in the demo video |
| Extra: AI agent namespace | 4 agents × subnames with ENSIP-26 metadata — endpoint, version, capabilities per agent |

</details>

## Build Timeline

| Day | Focus | Deliverable |
|---|---|---|
| Day 1 | Data Layer | Subgraph Studio client + Substreams connected; RECON pulling live normalized data from Uniswap + Aave |
| Day 2 | Intelligence Layer | SCOUT + RISK agents wired; LangGraph StateGraph routing confirmed; WebSocket server emitting `SIGNAL` + `TRACE` events |
| Day 3 | MCP Server + x402 | All 5 MCP tools implemented; Blocky402 middleware wired; ORACLE completing the full x402 payment flow end-to-end |
| Day 4 | Identity + Audit | ENSv2 subnames registered; HCS topic created + logging; ERC-8004 identities registered on Hedera testnet |
| Day 5 | Dashboard | All 4 panels live with real WebSocket data; HashScan links working; HCS mirror node poll confirmed |
| Day 6 | Demo + Submit | SKILL.md + README finalized; 3-minute demo video recorded; ETHGlobal submission completed |

## Build Checklist

The `Build checklist` line in [Live Status](#-live-status) is computed automatically by counting
the boxes below on every push — check one off in a commit and the status block updates itself.

- [ ] Subgraph Studio API key live, querying Uniswap + Aave
- [ ] Messari Standardized Subgraphs queries returning normalized data
- [ ] Substreams pipeline subscribed to ETH mainnet liquidation events
- [ ] x402-gated MCP server running, all 5 tools responding
- [ ] Blocky402 facilitator registered, x402 middleware intercepting
- [ ] ORACLE agent completing the full x402 payment flow end-to-end
- [ ] HCS topic created, AUDIT agent writing entries
- [ ] ERC-8004 agent identities registered
- [ ] ENSv2 subnames registered with Permissioned Resolver
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
