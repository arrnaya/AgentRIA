# RIA — Reconnaissance Intelligence Agent

**On-chain intelligence that acts.**

RIA is an autonomous, multi-agent DeFi intelligence system that combines live on-chain data from
[The Graph](https://thegraph.com)'s 15,000+ Subgraphs with autonomous payment execution on
[Hedera](https://hedera.com)'s x402 protocol and per-agent identity on [ENSv2](https://ens.domains)
— presented through a real-time dashboard that makes every agent decision and payment visible.

> RIA is not a dashboard. It is an agent that acts — and a dashboard that proves it.

Built solo by **Arrnaya (Arun Kumar Yadav)** for **ETHGlobal Online 2026**.

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
| **Current phase** | Pre-launch — repo, README & landing/dashboard preview live |
| **Build checklist** | `░░░░░░░░░░░░░░░░░░░░` 0/14 (0%) |
| **Days to ETHGlobal submission open** | 2 days |
| **Latest commit** | [`0bf3fbe`](https://github.com/arrnaya/AgentRIA/commit/0bf3fbeba2378073a0a3f89de424cc199c172c33) Switch live domain to ria-agent.vercel.app — Arrnaya |
| **Total commits** | 3 |
| **Last updated** | 2026-09-06 13:38 UTC |

_This block is regenerated automatically by [.github/workflows/update-status.yml](.github/workflows/update-status.yml) on every push to `main`._
<!-- STATUS:END -->

Full build updates (agents, live data, on-chain payments) begin **September 8, 2026**, when the
ETHGlobal Online submission window opens, and push to this repo daily. Until then this repo holds
the project proposal, the public-facing landing page, and a preview of the agent dashboard.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Problem Statement](#problem-statement)
3. [Solution Overview](#solution-overview)
4. [Technical Architecture](#technical-architecture)
5. [What's Live in This Repo Right Now](#whats-live-in-this-repo-right-now)
6. [Repository Structure](#repository-structure-target)
7. [Tech Stack](#tech-stack)
8. [Running Locally](#running-locally)
9. [Hackathon Qualification Mapping](#hackathon-qualification-mapping)
10. [Build Timeline](#build-timeline)
11. [Build Checklist](#build-checklist)
12. [Why RIA Wins](#why-ria-wins)

---

## Executive Summary

RIA (Reconnaissance Intelligence Agent) is an autonomous, multi-agent DeFi intelligence system
that combines live on-chain data from The Graph's 15,000+ Subgraphs with autonomous payment
execution on Hedera's x402 protocol — presented through a real-time web dashboard that makes
every agent decision and payment visible to judges and users alike.

| Dimension | Detail |
|---|---|
| Project name | RIA — Reconnaissance Intelligence Agent |
| Tagline | On-chain intelligence that acts. |
| Track 1 | The Graph — Best AI Use Case (From Scratch) · $5,000 |
| Track 2 | Hedera — AI & Agentic Payments · $6,000 (up to 3 winners) |
| Track 3 | ENS — Best Use of ENSv2 · bonus $500+ |
| **Total prize target** | **$12,500+** |
| Core stack | The Graph · Hedera (x402/HBAR) · ENSv2 · LangGraph · Python · Next.js |
| Networks | Ethereum Mainnet (data) · Hedera Testnet (payments) · Sepolia (ENS) |

## Problem Statement

DeFi operates at machine speed. Price discrepancies across protocols close in seconds.
Liquidation thresholds are breached in a single block. Risk parameters shift with oracle updates.
Yet the dominant tooling for DeFi intelligence still requires:

- Human operators to monitor dashboards and decide when to act
- Manual API key management and subscription billing for data providers
- Separate pipelines for data ingestion, analysis, and execution
- No native mechanism for AI agents to pay for the services they consume
- Backend-only systems with no visible proof of agent reasoning for judges or users

The result: opportunities are missed, risks go unhedged, AI agents remain dependent on humans for
routine payments, and autonomous systems have no window for observers to verify their work.

RIA solves all of these gaps simultaneously: live data from The Graph, autonomous reasoning via
LangGraph, autonomous payment via Hedera x402, and a real-time dashboard that makes every decision
transparent and verifiable.

## Solution Overview

RIA is a modular, multi-agent system built on four pillars: **data, intelligence, payments, and
visibility.**

### 1 · The Graph — Live DeFi Intelligence

RIA queries The Graph's Subgraph MCP and Substreams in real time to ingest structured,
standardized DeFi data across 50+ networks. Messari Standardized Subgraphs mean a single query
pattern spans Uniswap, Aave, Compound, Curve, and any ERC-4626 vault simultaneously.

- Liquidity pool TVL, APY, fee tiers, and volume across protocols
- Lending market utilization, borrow rates, and collateral ratios
- Wallet-level position tracking and liquidation proximity alerts
- Cross-protocol arbitrage signals from standardized schemas
- Block-by-block Substreams pipeline for real-time event processing

### 2 · LangGraph Multi-Agent Reasoning

RIA's intelligence layer is a LangGraph `StateGraph` of six specialized agents with conditional
routing edges. Each agent has a defined role; outputs route to the next agent based on confidence
scores and action thresholds.

| Agent | Role | Input | Output |
|---|---|---|---|
| **RECON** | Data ingestion & normalization | Subgraph MCP / Substreams | Normalized opportunity signals |
| **SCOUT** | Opportunity detection & ranking | Normalized signals | Ranked opportunity list |
| **RISK** | Risk scoring & position sizing | Opportunities + portfolio state | Risk-adjusted recommendations |
| **ORACLE** | External signal enrichment | Recommendations | Enriched signals (paid via x402) |
| **EXEC** | Execution gating & action dispatch | Enriched signals | Executed actions or human alerts |
| **AUDIT** | Post-execution logging | Executed actions | On-chain audit trail via HCS |

- Persistent typed state object carries portfolio context, risk thresholds, and payment budget across every agent hop
- Conditional edges: RISK routes high-confidence signals to EXEC, low-confidence to a human alert queue in the dashboard
- ORACLE is the only agent with payment authority — it holds the HBAR wallet and is the sole x402 caller
- AUDIT writes a structured JSON payload to HCS after every EXEC action — tamper-proof, block-timestamped
- A WebSocket server runs alongside the pipeline, streaming state updates to the dashboard in real time

### 3 · Hedera — Autonomous Agentic Payments

The ORACLE agent pays for external inference and data signals autonomously via **Hedera x402**
through the **Blocky402** facilitator — no API key stored anywhere in the codebase. Sub-3 second
finality on Hedera means payments add negligible latency. Every payment is logged to the Hedera
Consensus Service (HCS) for a tamper-proof audit trail.

| Step | Actor | Action |
|---|---|---|
| 1 | RIA | x402-gated inference endpoint deployed on Hedera testnet via Blocky402 |
| 2 | ORACLE Agent | Sends HTTP request to the gated endpoint — no pre-loaded API key |
| 3 | Blocky402 | Returns HTTP 402 with HBAR payment instructions and amount |
| 4 | ORACLE Agent | Reads instructions, signs and submits HBAR transfer on Hedera |
| 5 | Blocky402 | Confirms payment on-chain (sub-3s finality), issues access token |
| 6 | ORACLE Agent | Retries request with token, receives inference response |
| 7 | AUDIT Agent | Logs payment tx ID + response hash to an HCS topic |
| 8 | Dashboard | Payment Monitor panel updates with tx ID and HashScan link in real time |

- x402-gated inference endpoint hosted on Hedera testnet via Blocky402
- ORACLE agent discovers the endpoint and pays per call in HBAR autonomously
- No API key, no subscription, no human approval for routine requests
- Payment and action hashes logged to HCS after every EXEC cycle
- Agent identity registered via the ERC-8004 on-chain agent standard

### 4 · ENSv2 — Agent Identity

Each RIA agent carries an ENSv2 subname (e.g. `ria-oracle.ria.eth`) on Sepolia with isolated
permissions via the Permissioned Resolver and Enhanced Access Control. Agent metadata follows
ENSIP-26 so identities are discoverable and composable by other protocols.

- Parent name: `ria.eth` registered on ENSv2 Sepolia
- Subnames: `ria-recon.ria.eth`, `ria-scout.ria.eth`, `ria-risk.ria.eth`, `ria-oracle.ria.eth`, `ria-exec.ria.eth`, `ria-audit.ria.eth`
- Permissioned Resolver: each subname owns its own text records in isolation
- Enhanced Access Control: the EXEC agent cannot touch ORACLE's records; permissions are enforced at the resolver level
- Agent text records follow ENSIP-26 for AI agent metadata — endpoint, version, capabilities

### 5 · Real-Time Dashboard — Making the Agent Visible

RIA's backend pipeline is powerful — but invisible to judges watching a terminal. The dashboard is
the window that proves the agent is working. It's built in Next.js with a WebSocket connection to
the Python pipeline and surfaces four live panels:

| Panel | What it shows | Data source |
|---|---|---|
| Opportunities Feed | Live DeFi signals detected by SCOUT — protocol, type, confidence score, timestamp | The Graph Subgraphs / Substreams |
| Agent Trace | Active agent, current reasoning step, confidence threshold, routing decision | LangGraph state stream via WebSocket |
| Payment Monitor | ORACLE's last x402 call — endpoint, HBAR amount paid, Hedera tx ID, HashScan link | Hedera testnet + Blocky402 |
| HCS Audit Trail | Last 10 AUDIT entries — action type, timestamp, HCS topic link | Hedera Consensus Service |

**The dashboard does not execute actions itself — it is a read-only observer of the agent
pipeline.** This separation keeps the agent's autonomy intact while giving judges interactive
proof of every decision.

## Technical Architecture

```
┌──────────────────────────────────────────────────────────────────────────┐
│                          RIA SYSTEM OVERVIEW                             │
├─────────────────┬─────────────────┬──────────────────┬───────────────────┤
│  DATA LAYER     │  INTELLIGENCE   │  PAYMENT &       │  VISIBILITY       │
│                 │  LAYER          │  IDENTITY        │  LAYER            │
│  The Graph      │                 │                  │                   │
│  ────────────   │  LangGraph      │  Hedera x402     │  Next.js Dashboard│
│  Subgraph MCP   │  ────────────   │  ────────────    │  ─────────────    │
│  Substreams     │  RECON Agent    │  x402-gated API  │  Opportunity Feed │
│  Standardized   │  SCOUT Agent    │  Blocky402       │  Agent Trace      │
│  Subgraphs      │  RISK Agent     │  HBAR Payments   │  Payment Monitor  │
│  (50+ networks) │  ORACLE Agent ──┼──► Pay per call  │  HCS Audit Trail  │
│                 │  EXEC Agent     │  HCS Audit Log   │                   │
│  15,000+        │  AUDIT Agent    │                  │  WebSocket feed   │
│  Subgraphs      │                 │  ENSv2 Sepolia   │  from pipeline    │
│  available      │  StateGraph     │  Agent subnames  │  HashScan links   │
│                 │  (conditional   │  Permissioned    │  for on-chain     │
│                 │   routing)      │  Resolver        │  verification     │
└─────────────────┴─────────────────┴──────────────────┴───────────────────┘
```

**Data layer** — RIA composes three Graph products, satisfying the composable and standardized
qualification requirement: Subgraph MCP for natural-language subgraph queries, Substreams for
block-by-block event pipelines, and Messari Standardized Subgraphs for one schema across
protocols.

**Payment layer (x402 flow)** — see the step table above. ORACLE is the sole caller with wallet
access; every call is metered, logged, and verifiable.

**Visibility layer** — a Next.js app with four panels, each fed by a dedicated WebSocket channel
from the Python pipeline. It is read-only: it observes the agent, it does not control it.

## What's Live in This Repo Right Now

This repository is being built in public. Here's an honest snapshot of what exists **today** vs.
what's on the roadmap starting September 8:

| Component | Status |
|---|---|
| Project proposal & architecture docs | ✅ Complete |
| Public landing page (`/`) — [ria-agent.vercel.app](https://ria-agent.vercel.app) | ✅ Live |
| Dashboard interface preview (`/app`) — [ria-agent.vercel.app/app](https://ria-agent.vercel.app/app) | ✅ Live (static preview, illustrative data) |
| README with self-updating status | ✅ Live (this file) |
| RECON — Subgraph MCP / Substreams client | 🔜 From Sep 8 |
| SCOUT / RISK — LangGraph agents | 🔜 From Sep 8 |
| ORACLE — Hedera x402 payment flow | 🔜 From Sep 8 |
| AUDIT — HCS logging | 🔜 From Sep 8 |
| ENSv2 subname registration | 🔜 From Sep 8 |
| Live WebSocket feed → dashboard | 🔜 From Sep 8 |
| Demo video | 🔜 Before submission close |

The dashboard preview currently ships with static, clearly-labeled illustrative data so the
finished interface can be evaluated ahead of the live pipeline going up.

## Repository Structure (target)

The frontend below is live today at the repo root. `agents/`, `graph/`, `hedera/`, `ens/`,
`pipeline/`, and `server/` are the planned Python backend, landing from September 8 per the
[Build Timeline](#build-timeline):

```
AgentRIA/
├── src/
│   ├── app/
│   │   ├── page.tsx          # Landing page  →  ria-agent.vercel.app
│   │   ├── app/page.tsx      # Dashboard      →  ria-agent.vercel.app/app
│   │   ├── layout.tsx
│   │   └── globals.css
│   └── components/           # Shared UI (Nav, Footer, Brand, Card, Pill…)
├── agents/                   # 🔜 recon.py · scout.py · risk.py · oracle.py · exec.py · audit.py
├── graph/                    # 🔜 subgraph_client.py · substreams_client.py · queries/
├── hedera/                   # 🔜 x402_client.py · hcs_logger.py · wallet.py
├── ens/                      # 🔜 register.py · resolver.py
├── pipeline/                 # 🔜 state.py · graph.py · runner.py · ws_server.py
├── server/                   # 🔜 inference_api.py (x402-gated FastAPI endpoint)
├── tests/                    # 🔜
├── .github/workflows/        # update-status.yml — keeps the Live Status block current
├── assets/                   # Reference designs & project proposal
├── .env.example              # 🔜
└── SKILL.md                  # 🔜 required for The Graph track
```

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Agent framework | LangGraph (Python) | StateGraph with conditional edges and typed state |
| LLM | Claude Sonnet via Anthropic API | Tool-calling for agent actions across all 6 agents |
| Data — Subgraph | The Graph Subgraph MCP | Natural-language queries across 15,000+ subgraphs |
| Data — Streams | The Graph Substreams | Block-by-block EVM event pipeline |
| Schema | Messari Standardized Subgraphs | Single schema spanning Uniswap, Aave, Compound, Curve |
| Payments | Hedera x402 + Blocky402 | HBAR micropayments, sub-3s finality on testnet |
| Audit trail | Hedera Consensus Service (HCS) | Tamper-proof, block-timestamped action log |
| Agent identity | Hedera ERC-8004 | On-chain agent identity standard |
| ENS identity | ENSv2 on Sepolia | Permissioned Resolver + Enhanced Access Control |
| Inference server | FastAPI (Python) | x402-gated endpoint registered in Blocky402 |
| Frontend | Next.js 16 + TypeScript + Tailwind CSS v4 | This repo — landing + dashboard, deployed on Vercel |
| Dashboard feed | Python `websockets` + React hooks | 🔜 Typed event stream: SIGNAL, TRACE, PAYMENT, AUDIT |
| Testing | pytest + Hardhat fork | 🔜 Local fork for execution simulation |

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

From September 8, the full stack adds the Python agent pipeline:

```bash
# Terminal 1 — x402-gated inference endpoint
cd server && python inference_api.py \
  --network testnet --price 0.001 --facilitator blocky402 --port 8080

# Terminal 2 — RIA agent pipeline + WebSocket server
python pipeline/runner.py \
  --mode live --networks ethereum,arbitrum,polygon \
  --risk-threshold 0.65 --budget-hbar 10 --interval 30 --ws-port 3001

# Terminal 3 — Next.js dashboard
npm run dev

# Terminal 4 — Watch HCS audit trail (optional)
python hedera/hcs_logger.py --follow --topic <TOPIC_ID>
```

## Hackathon Qualification Mapping

<details>
<summary><strong>The Graph — AI Use Case Track</strong></summary>

| Requirement | How RIA satisfies it |
|---|---|
| Use The Graph as a load-bearing part | RECON cannot function without Subgraph MCP — it is the sole data ingestion layer |
| Consume live data (no mocked datasets) | Subgraph Studio API key for Subgraphs; The Graph Market for Substreams — all live |
| Do meaningful work with the data | 6-agent reasoning pipeline: detection → scoring → enrichment → execution → audit |
| AI tooling or AI use case | LangGraph pipeline using Graph data for autonomous DeFi intelligence |
| Open-source with README + SKILL.md | SKILL.md at repo root describing the Graph integration; full README with setup steps |
| Public repo + 2–4 min demo video | GitHub repo + demo showing live query → agent trace → action → on-chain proof |
| From Scratch pool | Net-new build; no prior project-specific code reused during the event |

</details>

<details>
<summary><strong>Hedera — AI & Agentic Payments Track</strong></summary>

| Requirement | How RIA satisfies it |
|---|---|
| Host a live x402-gated service on Hedera testnet | Inference endpoint registered via Blocky402 on Hedera testnet |
| Build an agent that consumes the service | ORACLE agent completes paid requests autonomously — no human approval |
| At least one real paid request end-to-end | Demonstrated live: ORACLE → 402 → HBAR payment → access → response |
| Public GitHub repo with README | Full README covering setup, architecture, and the complete x402 payment flow |
| Demo video ≤ 5 min | Payment Monitor showing HBAR tx and live HashScan verification |
| Extra: on-chain agent identity (ERC-8004) | Agent registered via ERC-8004 on Hedera testnet |
| Extra: verifiable payment audit trail on HCS | AUDIT agent writes every payment + action hash to HCS; dashboard shows it live |

</details>

<details>
<summary><strong>ENS — Best Use of ENSv2</strong></summary>

| Requirement | How RIA satisfies it |
|---|---|
| Built on ENSv2 (Sepolia) | All subnames registered on the ENSv2 Sepolia deployment |
| ENSv2 features central to the product | Permissioned Resolver gives each agent isolated record ownership — core to the identity model |
| Functional demo, not hard-coded | Live subname registration and record resolution shown in the demo |
| Open source + video | Shared repo + demo video covering ENS agent identity setup and resolution |
| Extra: AI agent namespace | Each agent has a subname with ENSIP-26 text records — endpoint, version, capabilities |

</details>

## Build Timeline

| Day | Focus | Deliverable |
|---|---|---|
| Day 1 | Data Layer | Subgraph MCP + Substreams client; RECON agent pulling live data |
| Day 2 | Intelligence Layer | SCOUT + RISK agents wired; LangGraph StateGraph routing confirmed; WebSocket server emitting events |
| Day 3 | Payment Layer | x402 inference server live on Hedera testnet; ORACLE paying autonomously end-to-end |
| Day 4 | Identity + Audit | ENSv2 subnames registered; HCS logging; ERC-8004 registered |
| Day 5 | Dashboard | All 4 dashboard panels live with real data from the WebSocket feed; HashScan links working |
| Day 6 | Polish + Submit | README + SKILL.md finalized; 3-minute demo video recorded; submitted |

## Build Checklist

The `Build checklist` line in [Live Status](#-live-status) is computed automatically by counting
the boxes below on every push — check one off in a commit and the status block updates itself.

- [ ] Subgraph MCP connection with a live API key (Subgraph Studio)
- [ ] Substreams pipeline for ETH mainnet liquidations (The Graph Market)
- [ ] Messari Standardized Subgraph queries across ≥ 2 protocols (Uniswap + Aave)
- [ ] x402-gated inference endpoint live (Hedera Testnet)
- [ ] ORACLE agent x402 payment flow end-to-end (Blocky402 facilitator)
- [ ] HCS audit trail topic created and logging (Hedera Testnet)
- [ ] ERC-8004 agent identity registration (Hedera Testnet)
- [ ] ENSv2 subnames with Permissioned Resolver (Sepolia)
- [ ] Dashboard — all 4 panels live with real data (ria-agent.vercel.app/app)
- [ ] WebSocket server emitting all 4 event types (pipeline runner)
- [ ] SKILL.md written for The Graph track (repo root)
- [ ] README finalized with setup, architecture, payment flow
- [ ] Demo video (3 min) following the demo script (YouTube / Loom)
- [ ] ETHGlobal submission with public repo link (ethglobal.com)

## Why RIA Wins

| Judging criterion | RIA's edge |
|---|---|
| Technical depth | Multi-agent LangGraph graph, not a chatbot; a Substreams pipeline, not just Subgraph queries |
| Graph product composition | Composes 3 Graph products (MCP + Substreams + Standardized Subgraphs) — the highest tier |
| Live data | Zero mocked data; every query hits a live Graph provider with a real API key |
| Hedera x402 completeness | Hosts the gated service **and** consumes it — a full loop, not a PoC stub |
| Demo quality | The dashboard makes every agent decision and on-chain payment visible and clickable in real time |
| Differentiation | RIA acts; the dashboard proves it — not a read-only analytics tool |
| Bonus criteria | ERC-8004 identity, HCS audit trail, ENSv2 subnames — all bonus boxes checked |
| Reusability | SKILL.md makes the Graph integration reusable — required for the AI tooling sub-pool |

---

## License

MIT — see [LICENSE](LICENSE).

## Builder

**Arrnaya (Arun Kumar Yadav)** · [github.com/arrnaya](https://github.com/arrnaya)

*RIA — Reconnaissance Intelligence Agent · On-chain intelligence that acts. · ETHGlobal Online 2026*
