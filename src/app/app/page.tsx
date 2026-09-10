import Link from "next/link";
import { Logomark, Wordmark } from "@/components/Brand";
import { Card, Pill } from "@/components/ui";

const tabs = [
  { href: "#overview", label: "Overview" },
  { href: "#opportunities", label: "Opportunities" },
  { href: "#trace", label: "Agent Trace" },
  { href: "#payments", label: "Payments" },
  { href: "#audit", label: "Audit Trail" },
  { href: "#identity", label: "Identity" },
];

const opportunities = [
  { protocol: "Uniswap v3", pair: "ETH / USDC", type: "Yield gap", confidence: 0.82, time: "12s ago", tone: "sky" as const },
  { protocol: "Aave v3", pair: "USDC market", type: "Liquidation proximity", confidence: 0.74, time: "48s ago", tone: "blush" as const },
  { protocol: "Compound v3", pair: "USDC market", type: "Rate divergence", confidence: 0.71, time: "1m ago", tone: "mint" as const },
  { protocol: "Curve", pair: "3pool", type: "Pool imbalance", confidence: 0.63, time: "3m ago", tone: "butter" as const },
  { protocol: "Aave v3", pair: "wstETH", type: "Collateral ratio drift", confidence: 0.58, time: "6m ago", tone: "lavender" as const },
];

const trace = [
  { name: "RECON", status: "Complete", note: "Pulled 4 opportunity signals from Subgraph Studio" },
  { name: "SCOUT", status: "Complete", note: "Ranked signals — top spread 2.3% APY" },
  { name: "RISK", status: "Routed → ORACLE", note: "Confidence 0.71, above 0.65 threshold" },
  { name: "ORACLE", status: "Pending", note: "Will call the x402 MCP server once pipeline connects" },
  { name: "EXEC", status: "Waiting", note: "Gated on ORACLE enrichment" },
  { name: "AUDIT", status: "Waiting", note: "Logs to HCS after EXEC completes" },
];

// Live on Sepolia — registered via scripts/register_agents_live.py,
// isolation verified on-chain (verify_isolation()). Not mock data: these
// resolve for real right now at the ENS app links below.
const identities = [
  { name: "recon.agentria.eth", operator: "0x6968...8280" },
  { name: "oracle.agentria.eth", operator: "0x5f7F...8ff9" },
  { name: "exec.agentria.eth", operator: "0xb016...EE3B8" },
  { name: "audit.agentria.eth", operator: "0xcC25...A388" },
];

export default function Dashboard() {
  return (
    <div className="flex-1 bg-paper">
      {/* HERO HEADER */}
      <header className="relative overflow-hidden bg-noir px-4 pb-10 pt-6 text-paper sm:px-8">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(60%_60%_at_80%_0%,var(--color-lavender)_0%,transparent_60%)] opacity-15" />
        <div className="relative mx-auto flex max-w-6xl items-center justify-between">
          <Link href="/" className="flex items-center gap-2">
            <Logomark className="h-5 w-5 text-lavender-deep" />
            <Wordmark className="text-lg" />
          </Link>
          <div className="flex items-center gap-3">
            <span className="hidden items-center gap-1.5 rounded-full border border-paper/15 px-3 py-1.5 text-xs text-paper/60 sm:inline-flex">
              <span className="h-1.5 w-1.5 rounded-full bg-butter-deep" />
              Pipeline: Pre-launch
            </span>
            <a
              href="https://github.com/arrnaya/AgentRIA"
              className="rounded-full border border-paper/20 p-2 transition hover:bg-white/10"
              aria-label="GitHub repository"
            >
              <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current">
                <path d="M12 .5C5.73.5.5 5.74.5 12.02c0 5.02 3.25 9.28 7.77 10.79.57.1.78-.25.78-.55 0-.27-.01-1.16-.02-2.11-3.16.69-3.83-1.34-3.83-1.34-.52-1.32-1.26-1.67-1.26-1.67-1.03-.71.08-.69.08-.69 1.14.08 1.74 1.17 1.74 1.17 1.01 1.74 2.65 1.24 3.3.95.1-.74.4-1.24.72-1.53-2.52-.29-5.17-1.26-5.17-5.62 0-1.24.44-2.26 1.17-3.06-.12-.29-.51-1.46.11-3.04 0 0 .96-.31 3.14 1.17a10.9 10.9 0 0 1 5.72 0c2.18-1.48 3.14-1.17 3.14-1.17.62 1.58.23 2.75.11 3.04.73.8 1.17 1.82 1.17 3.06 0 4.37-2.66 5.33-5.19 5.61.41.36.77 1.07.77 2.15 0 1.55-.01 2.8-.01 3.18 0 .3.2.66.79.55A10.53 10.53 0 0 0 23.5 12.02C23.5 5.74 18.27.5 12 .5Z" />
              </svg>
            </a>
          </div>
        </div>

        <div className="relative mx-auto mt-14 max-w-6xl">
          <p className="text-sm text-paper/50">Reconnaissance Intelligence Agent</p>
          <h1 className="mt-1 text-3xl font-medium tracking-tight sm:text-4xl">
            Agent <span className="font-serif-display italic text-lavender-deep">Dashboard</span>
          </h1>
        </div>
      </header>

      <div className="relative z-10 mx-auto -mt-6 max-w-6xl px-4 sm:px-8">
        {/* PREVIEW BANNER */}
        <div className="flex flex-col gap-1 rounded-2xl border border-butter-deep/40 bg-butter px-5 py-4 text-sm text-[#6b4f10] shadow-[0_12px_30px_-18px_rgba(23,21,34,0.35)] sm:flex-row sm:items-center sm:justify-between">
          <p>
            <span className="font-medium">Partially live.</span> Agent Identity below is real,
            on-chain, and verified — everything else illustrates the finished dashboard until the
            live pipeline connects.
          </p>
          <a href="https://github.com/arrnaya/AgentRIA" className="shrink-0 font-medium underline underline-offset-2">
            Follow build progress →
          </a>
        </div>

        {/* TABS */}
        <nav className="mt-6 flex gap-1 overflow-x-auto rounded-full border border-line bg-white p-1 text-sm scrollbar-thin">
          {tabs.map((t, i) => (
            <a
              key={t.href}
              href={t.href}
              className={`shrink-0 rounded-full px-4 py-2 transition ${
                i === 0 ? "bg-noir text-paper" : "text-ink-soft hover:bg-lavender/50"
              }`}
            >
              {t.label}
            </a>
          ))}
        </nav>

        {/* OVERVIEW STAT ROW */}
        <section id="overview" className="mt-6 scroll-mt-24 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card>
            <p className="text-xs text-ink-faint">Subgraphs in scope</p>
            <p className="mt-2 text-2xl font-medium text-ink">15,000+</p>
            <div className="mt-4 flex h-10 items-end gap-1">
              {[4, 7, 5, 9, 6, 10, 8, 12, 7, 9, 11, 6].map((h, i) => (
                <span key={i} className="w-full rounded-full bg-butter-deep/70" style={{ height: `${h * 3}px` }} />
              ))}
            </div>
          </Card>
          <Card>
            <p className="text-xs text-ink-faint">Networks monitored</p>
            <p className="mt-2 text-2xl font-medium text-ink">50+</p>
            <svg viewBox="0 0 100 32" className="mt-4 h-10 w-full" preserveAspectRatio="none">
              <polyline
                points="0,24 15,18 30,22 45,10 60,14 75,6 90,12 100,8"
                fill="none"
                stroke="var(--color-sky-deep)"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </Card>
          <Card>
            <p className="text-xs text-ink-faint">Graph products composed</p>
            <p className="mt-2 text-2xl font-medium text-ink">3</p>
            <div className="mt-4 flex h-10 items-end gap-2">
              {[9, 6, 11].map((h, i) => (
                <span key={i} className="w-full rounded-lg bg-mint-deep/70" style={{ height: `${h * 3}px` }} />
              ))}
            </div>
          </Card>
          <Card className="flex flex-col items-center justify-center text-center">
            <div className="relative flex h-20 w-20 items-center justify-center rounded-full bg-[conic-gradient(var(--color-lavender-deep)_100%,var(--color-line)_0)]">
              <div className="flex h-14 w-14 items-center justify-center rounded-full bg-white">
                <span className="text-sm font-medium text-ink">100%</span>
              </div>
            </div>
            <p className="mt-3 text-xs text-ink-faint">Live data coverage</p>
          </Card>
        </section>

        {/* MAIN GRID */}
        <section className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-[1fr_1.3fr_1fr]">
          {/* Opportunities */}
          <Card id="opportunities" className="scroll-mt-24 !p-0">
            <div className="flex items-center justify-between px-6 pt-5">
              <p className="text-sm font-medium text-ink">Opportunities Feed</p>
              <span className="text-xs text-ink-faint">SCOUT</span>
            </div>
            <div className="mt-3 divide-y divide-line">
              {opportunities.map((o) => (
                <div key={o.protocol + o.type} className="px-6 py-4">
                  <div className="flex items-center justify-between">
                    <Pill tone={o.tone}>{o.protocol}</Pill>
                    <span className="text-xs text-ink-faint">{o.time}</span>
                  </div>
                  <p className="mt-2 text-sm font-medium text-ink">{o.type}</p>
                  <div className="mt-1 flex items-center justify-between text-xs text-ink-faint">
                    <span>{o.pair}</span>
                    <span>{Math.round(o.confidence * 100)}% confidence</span>
                  </div>
                </div>
              ))}
            </div>
          </Card>

          {/* Agent Trace */}
          <Card id="trace" className="scroll-mt-24 flex flex-col">
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 items-center justify-center rounded-full bg-lavender text-xs">◎</span>
              <p className="text-sm font-medium text-ink">Proactive Intelligence Engine</p>
            </div>
            <div className="mt-4 space-y-2">
              {trace.map((t) => (
                <div key={t.name} className="rounded-xl bg-paper px-4 py-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-ink">{t.name}</span>
                    <span className="text-xs text-ink-faint">{t.status}</span>
                  </div>
                  <p className="mt-1 text-xs text-ink-soft">{t.note}</p>
                </div>
              ))}
            </div>
            <div className="mt-5 flex flex-col gap-2 sm:flex-row">
              <button className="flex-1 rounded-full border border-line px-4 py-2.5 text-sm font-medium text-ink transition hover:bg-lavender/40">
                View Full Trace
              </button>
              <button
                disabled
                className="flex-1 cursor-not-allowed rounded-full bg-ink/10 px-4 py-2.5 text-sm font-medium text-ink-faint"
                title="Read-only preview — this dashboard never executes"
              >
                Execute (read-only)
              </button>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <div className="rounded-xl bg-paper px-4 py-3">
                <p className="text-xs text-ink-faint">Confidence threshold</p>
                <p className="mt-1 text-lg font-medium text-ink">0.65</p>
              </div>
              <div className="rounded-xl bg-paper px-4 py-3">
                <p className="text-xs text-ink-faint">Signals today</p>
                <p className="mt-1 text-lg font-medium text-ink">5</p>
              </div>
            </div>
          </Card>

          {/* Payments + Audit */}
          <div className="flex flex-col gap-4">
            <Card id="payments" className="scroll-mt-24">
              <p className="text-sm font-medium text-ink">Payment Monitor</p>
              <div className="mt-4 flex h-12 items-end gap-1">
                {[5, 8, 6, 11, 7, 13, 9, 6, 10, 8].map((h, i) => (
                  <span key={i} className="w-full rounded-full bg-blush-deep/70" style={{ height: `${h * 3}px` }} />
                ))}
              </div>
              <dl className="mt-4 space-y-2 text-xs">
                <div className="flex justify-between"><dt className="text-ink-faint">Tool</dt><dd className="font-mono text-ink-soft">get_risk_score()</dd></div>
                <div className="flex justify-between"><dt className="text-ink-faint">Amount</dt><dd className="font-mono text-ink-soft">0.002 HBAR</dd></div>
                <div className="flex justify-between"><dt className="text-ink-faint">Facilitator</dt><dd className="text-ink-soft">Blocky402</dd></div>
                <div className="flex justify-between"><dt className="text-ink-faint">Tx</dt><dd className="font-mono text-ink-faint">awaiting first call</dd></div>
              </dl>
              <span className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-blush px-3 py-1 text-xs text-[#8a3f5f]">
                <span className="h-1.5 w-1.5 rounded-full bg-blush-deep" /> Standing by
              </span>
            </Card>

            <Card id="audit" className="scroll-mt-24 flex-1">
              <p className="text-sm font-medium text-ink">HCS Audit Trail</p>
              <div className="mt-4 space-y-3 text-xs">
                <div className="rounded-xl bg-paper px-4 py-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium text-mint-deep">PREVIEW</span>
                    <span className="text-ink-faint">—</span>
                  </div>
                  <p className="mt-1 text-ink-soft">
                    Awaiting first EXEC cycle. Once live, every action + payment hash logs here
                    with a Hedera mirror node link.
                  </p>
                </div>
              </div>
            </Card>
          </div>
        </section>

        {/* IDENTITY */}
        <section id="identity" className="mt-6 scroll-mt-24">
          <Card>
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-ink">Agent Identity — ENSv2 (Sepolia)</p>
              <span className="inline-flex items-center gap-1.5 text-xs text-mint-deep">
                <span className="h-1.5 w-1.5 rounded-full bg-mint-deep" /> live · agentria.eth
              </span>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-4">
              {identities.map((id) => (
                <a
                  key={id.name}
                  href={`https://sepolia.app.ens.domains/${id.name}`}
                  target="_blank"
                  rel="noreferrer"
                  className="flex flex-col gap-1 rounded-xl bg-paper px-4 py-3 text-sm transition hover:bg-lavender/40"
                >
                  <span className="font-mono text-xs text-ink-soft">{id.name}</span>
                  <span className="font-mono text-[11px] text-ink-faint">{id.operator}</span>
                </a>
              ))}
            </div>
            <p className="mt-3 text-xs text-ink-faint">
              Isolation verified on-chain — no operator key above can write another agent&rsquo;s node. Click a name to resolve it yourself.
            </p>
          </Card>
        </section>

        <p className="mt-8 pb-16 text-center text-xs text-ink-faint">
          RIA Dashboard is a read-only observer — it never executes on your behalf. Built for
          ETHGlobal Online 2026.
        </p>
      </div>
    </div>
  );
}
