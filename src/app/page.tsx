import Link from "next/link";
import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import { Card, Eyebrow, Pill, SectionHeading } from "@/components/ui";

const agents = [
  {
    name: "RECON",
    role: "Data ingestion & normalization",
    input: "Subgraph Studio / Substreams",
    output: "Normalized opportunity signals",
    tone: "sky" as const,
  },
  {
    name: "SCOUT",
    role: "Opportunity detection & ranking",
    input: "Normalized signals",
    output: "Ranked opportunity list",
    tone: "mint" as const,
  },
  {
    name: "RISK",
    role: "Risk scoring & position sizing",
    input: "Opportunities + portfolio state",
    output: "Risk-adjusted recommendations",
    tone: "butter" as const,
  },
  {
    name: "ORACLE",
    role: "External signal enrichment",
    input: "Recommendations",
    output: "Enriched signals — pays the x402 MCP server",
    tone: "blush" as const,
  },
  {
    name: "EXEC",
    role: "Execution gating & action dispatch",
    input: "Enriched signals",
    output: "Executed actions or human alerts",
    tone: "lavender" as const,
  },
  {
    name: "AUDIT",
    role: "Post-execution logging",
    input: "Executed actions",
    output: "On-chain audit trail via HCS",
    tone: "sky" as const,
  },
];

const mcpTools = [
  {
    name: "get_gas_price()",
    desc: "Live gas + EIP-1559 base fee via Etherscan",
    price: "0.0005 HBAR",
  },
  {
    name: "get_sentiment()",
    desc: "Protocol sentiment score via LLM synthesis",
    price: "0.001 HBAR",
  },
  {
    name: "get_risk_score()",
    desc: "Risk-adjusted confidence delta — the main SKU",
    price: "0.002 HBAR",
  },
  {
    name: "get_price_feed()",
    desc: "Spot price + 24h change via CoinGecko",
    price: "0.0005 HBAR",
  },
  {
    name: "stream_alerts()",
    desc: "Filtered liquidation-proximity alerts",
    price: "0.001 HBAR / alert",
  },
];

const verifications = [
  {
    label: "The Graph data",
    detail: "Live Subgraph Studio API key — every query hits real mainnet subgraphs, nothing mocked.",
  },
  {
    label: "MCP payment",
    detail: "Every x402 tool call resolves to a real HBAR transfer, visible on HashScan the moment it confirms.",
  },
  {
    label: "External agent proof",
    detail: "A second AI agent — not RIA — pays the same MCP server live during the demo.",
  },
  {
    label: "HCS audit trail",
    detail: "Hedera mirror node link shows timestamped, immutable action-log entries.",
  },
  {
    label: "ENS identity",
    detail: "ENS app on Sepolia resolves ria-oracle.ria.eth with live ENSIP-26 text records.",
  },
];

const faqs = [
  {
    q: "Is RIA just a dashboard?",
    a: "No — RIA is an agent that acts, and a commercial primitive that proves how the AI agent economy should handle payments. The pipeline runs independently in Python; the Next.js dashboard is a read-only observer that streams every reasoning step and payment over WebSocket so nothing happens off-screen.",
  },
  {
    q: "Where does RIA's data actually come from?",
    a: "The Graph. RECON queries Subgraph Studio and Substreams directly in real time, composing Messari Standardized Subgraphs so one schema spans Uniswap, Aave, Compound, Curve, and any ERC-4626 vault across 50+ networks. This layer is free and never routed through a payment gate.",
  },
  {
    q: "How does an AI agent pay for enrichment data?",
    a: "ORACLE calls a tool on RIA's x402-gated MCP server — say get_risk_score(). It gets an HTTP 402 with payment instructions, signs and submits an HBAR transfer, Blocky402 confirms it in under 3 seconds, and ORACLE retries with its access token to receive the enriched data. Fully autonomous, no stored key.",
  },
  {
    q: "Can other AI agents use RIA's payment server too?",
    a: "Yes — that's the point. The MCP server isn't RIA-specific infrastructure. Any MCP-compatible agent (Claude, GPT, Gemini, a LangGraph or CrewAI agent) can connect, pay per tool call in HBAR, and get data back. RIA's ORACLE is simply the first consumer.",
  },
  {
    q: "Can anyone verify what RIA actually did?",
    a: "Yes. Every claim resolves on-chain: HashScan for the HBAR payment, the HCS mirror node for the audit log entry, and the ENS app on Sepolia for live agent identity — judges don't have to take anything on faith.",
  },
];

const techBadges = [
  "The Graph",
  "MCP",
  "Hedera x402",
  "ENSv2",
  "LangGraph",
  "Claude Sonnet",
  "Next.js",
];

export default function Home() {
  return (
    <div id="top" className="flex-1">
      <div className="mx-auto max-w-6xl px-4 pt-4 sm:px-6">
        <Nav />
      </div>

      {/* HERO */}
      <section className="relative mx-auto mt-6 max-w-6xl px-4 sm:px-6">
        <div className="pointer-events-none absolute -inset-x-10 -top-10 -z-10 h-[560px] rounded-[3rem] bg-[radial-gradient(60%_60%_at_15%_20%,var(--color-lavender)_0%,transparent_70%),radial-gradient(50%_50%_at_85%_15%,var(--color-butter)_0%,transparent_70%),radial-gradient(60%_60%_at_50%_100%,var(--color-mint)_0%,transparent_70%)] opacity-80 blur-2xl" />

        <div className="relative overflow-hidden rounded-[2.5rem] bg-noir px-6 pb-16 pt-14 text-center text-paper sm:px-12 sm:pt-20">
          <div className="pointer-events-none absolute inset-0 bg-noise opacity-[0.04]" />
          <Eyebrow>
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-mint-deep" />
            <span className="text-paper/70">ETHGlobal Online 2026 · Live Build</span>
          </Eyebrow>

          <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-medium tracking-tight sm:text-6xl">
            On-chain intelligence{" "}
            <span className="font-serif-display italic text-lavender-deep">that acts</span>
          </h1>

          <p className="mx-auto mt-5 max-w-xl text-balance text-[15px] leading-relaxed text-paper/65 sm:text-base">
            RIA is an autonomous multi-agent DeFi intelligence system — free live data from The
            Graph, LangGraph reasoning, and a commercial x402-gated MCP server on Hedera that any
            AI agent can pay to use — all made visible in real time.
          </p>

          <div className="mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="#agents"
              className="w-full rounded-full border border-paper/25 px-6 py-3 text-sm font-medium transition hover:bg-white/10 sm:w-auto"
            >
              See the Agents
            </a>
            <Link
              href="/app"
              className="w-full rounded-full bg-paper px-6 py-3 text-sm font-medium text-noir transition hover:bg-lavender sm:w-auto"
            >
              Launch Dashboard →
            </Link>
          </div>
        </div>

        {/* floating stat chips */}
        <div className="relative z-10 -mt-8 grid grid-cols-1 gap-3 px-2 sm:grid-cols-3 sm:px-8">
          {[
            { label: "Subgraphs in scope", value: "15,000+" },
            { label: "Autonomous agents", value: "6" },
            { label: "x402 MCP server on Hedera", value: "5 priced tools" },
          ].map((s) => (
            <div
              key={s.label}
              className="rounded-2xl border border-line bg-white px-5 py-4 text-center shadow-[0_12px_30px_-18px_rgba(23,21,34,0.35)] sm:text-left"
            >
              <p className="font-serif-display text-2xl italic text-ink">{s.value}</p>
              <p className="mt-0.5 text-xs text-ink-faint">{s.label}</p>
            </div>
          ))}
        </div>
      </section>

      {/* TECH ROW */}
      <section className="mx-auto mt-14 max-w-4xl px-4 sm:px-6">
        <p className="text-center text-xs uppercase tracking-wider text-ink-faint">
          Composed on
        </p>
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2.5">
          {techBadges.map((t) => (
            <span
              key={t}
              className="rounded-full border border-line bg-white px-4 py-1.5 text-sm text-ink-soft"
            >
              {t}
            </span>
          ))}
        </div>
      </section>

      {/* PROBLEM -> SOLUTION */}
      <section className="mx-auto mt-24 max-w-3xl px-4 sm:px-6">
        <p className="text-center font-serif-display text-xl italic leading-snug text-ink sm:text-2xl">
          &ldquo;RIA is not a dashboard. It is an agent that acts — and a commercial primitive that
          proves how the AI agent economy should handle payments.&rdquo;
        </p>
      </section>

      {/* AGENTS / ARCHITECTURE */}
      <section id="agents" className="mx-auto mt-28 max-w-6xl scroll-mt-24 px-4 sm:px-6">
        <SectionHeading
          eyebrow="Intelligence Layer"
          title="Six agents,"
          italic="one reasoning graph"
          description="RIA's intelligence layer is a LangGraph StateGraph of six specialized agents with conditional routing edges. Each agent has a defined role; outputs route to the next agent based on confidence scores and action thresholds."
        />

        <div id="architecture" className="mt-12 scroll-mt-24 overflow-hidden rounded-[2rem] bg-noir p-6 text-paper sm:p-10">
          <p className="text-xs uppercase tracking-wider text-paper/40">Pipeline flow</p>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-sm sm:text-base">
            {agents.map((a, i) => (
              <span key={a.name} className="flex items-center gap-2">
                <span className="rounded-full border border-paper/20 bg-white/5 px-3.5 py-1.5 font-medium">
                  {a.name}
                </span>
                {i < agents.length - 1 && <span className="text-paper/30">→</span>}
              </span>
            ))}
          </div>
          <p className="mt-6 max-w-2xl text-sm leading-relaxed text-paper/60">
            RISK routes high-confidence signals to EXEC and low-confidence signals to a human
            alert queue in the dashboard. ORACLE is the only agent with payment authority — it
            holds the HBAR wallet and is the sole caller of the x402-gated MCP server. AUDIT
            writes a structured, block-timestamped payload to HCS after every EXEC cycle.
          </p>
        </div>

        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((a) => (
            <Card key={a.name}>
              <Pill tone={a.tone}>{a.name}</Pill>
              <p className="mt-3 text-sm font-medium text-ink">{a.role}</p>
              <dl className="mt-4 space-y-2 text-xs text-ink-faint">
                <div className="flex justify-between gap-3">
                  <dt className="shrink-0">Input</dt>
                  <dd className="text-right text-ink-soft">{a.input}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="shrink-0">Output</dt>
                  <dd className="text-right text-ink-soft">{a.output}</dd>
                </div>
              </dl>
            </Card>
          ))}
        </div>
      </section>

      {/* CORE INNOVATION — MCP SERVER */}
      <section id="mcp" className="mx-auto mt-28 max-w-6xl scroll-mt-24 px-4 sm:px-6">
        <SectionHeading
          eyebrow="Core Innovation"
          title="A payment server"
          italic="any agent can use"
          description="RIA hosts an x402-gated MCP server on Hedera. Every tool call is metered and paid in HBAR — no API key, no subscription, no human in the loop. ORACLE is the first consumer; the server itself is the product."
        />

        <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
          {mcpTools.map((t) => (
            <Card key={t.name} className="flex flex-col justify-between">
              <div>
                <p className="font-mono text-xs text-ink-faint">{t.name}</p>
                <p className="mt-2 text-sm text-ink-soft">{t.desc}</p>
              </div>
              <p className="mt-4 font-serif-display text-lg italic text-lavender-deep">{t.price}</p>
            </Card>
          ))}
        </div>

        <div className="mt-6 overflow-hidden rounded-[2rem] bg-noir p-6 text-paper sm:p-10">
          <p className="text-xs uppercase tracking-wider text-paper/40">The killer moment</p>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-paper/70">
            During the demo, a second AI agent — not RIA — connects to the MCP server cold: a
            plain <code className="rounded bg-white/10 px-1.5 py-0.5 font-mono text-paper/90">curl</code> call
            gets a 402, pays HBAR, and gets data back in about 20 seconds. It proves the server is
            a generalized commercial primitive any MCP-compatible agent can use, not a RIA-only
            trick.
          </p>
        </div>
      </section>

      {/* AGENT TRACE + PAYMENT MOCKUP */}
      <section className="mx-auto mt-28 max-w-6xl px-4 sm:px-6">
        <div className="grid grid-cols-1 gap-4 overflow-hidden rounded-[2rem] bg-noir p-4 text-paper sm:grid-cols-[1.3fr_1fr] sm:p-6">
          <div className="rounded-2xl bg-white/5 p-5">
            <p className="flex items-center gap-2 text-sm text-paper/60">
              <span className="h-2 w-2 rounded-full bg-mint-deep" /> Agent Trace — live preview
            </p>
            <div className="mt-4 space-y-2.5">
              {[
                { name: "RECON", status: "Complete", tone: "text-mint-deep" },
                { name: "SCOUT", status: "Complete", tone: "text-mint-deep" },
                { name: "RISK", status: "Routed → ORACLE", tone: "text-sky-deep" },
                { name: "ORACLE", status: "Calling MCP tool…", tone: "text-butter-deep" },
              ].map((row) => (
                <div
                  key={row.name}
                  className="flex items-center justify-between rounded-xl bg-noir-soft px-4 py-3 text-sm"
                >
                  <span className="font-medium">{row.name}</span>
                  <span className={row.tone}>{row.status}</span>
                </div>
              ))}
            </div>
            <p className="mt-4 text-xs leading-relaxed text-paper/45">
              SCOUT flagged a yield spread between Aave v3 and Compound v3 USDC markets. RISK
              scored it 0.71 — above the 0.65 execution threshold. Routing to ORACLE for
              enrichment.
            </p>
          </div>

          <div className="rounded-2xl bg-white/5 p-5">
            <p className="text-sm text-paper/60">Payment Monitor</p>
            <div className="mt-4 flex h-16 items-end gap-1">
              {[6, 10, 14, 9, 18, 12, 20, 8, 15, 11, 19, 7, 13, 16, 10].map((h, i) => (
                <span
                  key={i}
                  className="w-full rounded-full bg-lavender-deep/70"
                  style={{ height: `${h * 4}px` }}
                />
              ))}
            </div>
            <div className="mt-5 space-y-1.5 text-xs text-paper/50">
              <p className="flex justify-between"><span>Tool</span><span className="font-mono text-paper/70">get_risk_score()</span></p>
              <p className="flex justify-between"><span>Amount</span><span className="font-mono text-paper/70">0.002 HBAR</span></p>
              <p className="flex justify-between"><span>Facilitator</span><span className="text-paper/70">Blocky402</span></p>
            </div>
          </div>
        </div>
      </section>

      {/* VERIFY */}
      <section id="verify" className="mx-auto mt-28 max-w-4xl scroll-mt-24 px-4 sm:px-6">
        <SectionHeading
          eyebrow="Trust"
          title="Verifiable,"
          italic="not just promised"
          description="Every claim RIA makes during the demo resolves to a public, on-chain record — judges don't have to take anything on faith."
        />
        <Card className="mt-10 divide-y divide-line !p-0">
          {verifications.map((v) => (
            <div key={v.label} className="flex flex-col gap-1 px-6 py-5 sm:flex-row sm:items-center sm:gap-6">
              <p className="w-48 shrink-0 text-sm font-medium text-ink">{v.label}</p>
              <p className="text-sm text-ink-soft">{v.detail}</p>
            </div>
          ))}
        </Card>
        <p className="mx-auto mt-8 max-w-xl text-center text-sm leading-relaxed text-ink-soft">
          RIA is engineered so security and provenance aren&rsquo;t optional features — they are the
          core every other capability relies on, from the first Subgraph query to the last HCS
          log entry.
        </p>
      </section>

      {/* FAQ */}
      <section id="faq" className="mx-auto mt-28 max-w-3xl scroll-mt-24 px-4 sm:px-6">
        <SectionHeading eyebrow="FAQ" title="Questions from" italic="Users" />
        <div className="mt-10 divide-y divide-line rounded-[2rem] border border-line bg-white/70">
          {faqs.map((f) => (
            <details key={f.q} className="group px-6 py-5">
              <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-sm font-medium text-ink marker:content-none">
                {f.q}
                <span className="shrink-0 text-lg text-ink-faint transition group-open:rotate-45">+</span>
              </summary>
              <p className="mt-3 text-sm leading-relaxed text-ink-soft">{f.a}</p>
            </details>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="mx-auto mt-28 max-w-6xl px-4 sm:px-6">
        <div className="relative overflow-hidden rounded-[2.5rem] bg-noir px-6 py-16 text-center text-paper sm:px-12">
          <div className="pointer-events-none absolute -inset-x-10 -top-24 -z-0 h-[400px] rounded-[3rem] bg-[radial-gradient(50%_50%_at_20%_20%,var(--color-blush)_0%,transparent_70%),radial-gradient(50%_50%_at_80%_30%,var(--color-sky)_0%,transparent_70%)] opacity-30 blur-2xl" />
          <h2 className="relative text-3xl font-medium tracking-tight sm:text-4xl">
            Ready to watch{" "}
            <span className="font-serif-display italic text-lavender-deep">intelligence act?</span>
          </h2>
          <p className="relative mx-auto mt-4 max-w-md text-sm text-paper/60">
            Build updates land on GitHub as each checklist milestone ships — follow along or open
            the live dashboard.
          </p>
          <div className="relative mt-8 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="https://github.com/arrnaya/AgentRIA"
              className="w-full rounded-full border border-paper/25 px-6 py-3 text-sm font-medium transition hover:bg-white/10 sm:w-auto"
            >
              View the Repo
            </a>
            <Link
              href="/app"
              className="w-full rounded-full bg-paper px-6 py-3 text-sm font-medium text-noir transition hover:bg-lavender sm:w-auto"
            >
              Launch Dashboard →
            </Link>
          </div>
        </div>
      </section>

      <Footer />
    </div>
  );
}
