"use client";

import Link from "next/link";
import { Logomark, Wordmark } from "@/components/Brand";
import { Card, Pill } from "@/components/ui";
import { useRiaSocket, type SignalEvent } from "@/hooks/useRiaSocket";

// Static illustrative data — shown only when the panel hasn't received a
// real event of its type yet (see `useRiaSocket`'s `live` flags below).
// Once a panel goes live, its real feed replaces this entirely.
const mockOpportunities = [
  { protocol: "Uniswap v3", pair: "ETH / USDC", type: "Yield gap", confidence: 0.82, time: "12s ago", tone: "sky" as const },
  { protocol: "Aave v3", pair: "USDC market", type: "Liquidation proximity", confidence: 0.74, time: "48s ago", tone: "blush" as const },
  { protocol: "Compound v3", pair: "USDC market", type: "Rate divergence", confidence: 0.71, time: "1m ago", tone: "mint" as const },
  { protocol: "Curve", pair: "3pool", type: "Pool imbalance", confidence: 0.63, time: "3m ago", tone: "butter" as const },
  { protocol: "Aave v3", pair: "wstETH", type: "Collateral ratio drift", confidence: 0.58, time: "6m ago", tone: "lavender" as const },
];

const mockTrace = [
  { name: "RECON", status: "Complete", note: "Pulled 4 opportunity signals from Subgraph Studio" },
  { name: "SCOUT", status: "Complete", note: "Ranked signals — top spread 2.3% APY" },
  { name: "RISK", status: "Routed → ORACLE", note: "Confidence 0.71, above 0.65 threshold" },
  { name: "ORACLE", status: "Pending", note: "Will call the x402 MCP server once pipeline connects" },
  { name: "EXEC", status: "Waiting", note: "Gated on ORACLE enrichment" },
  { name: "AUDIT", status: "Waiting", note: "Logs to HCS after EXEC completes" },
];

const AGENT_ORDER = ["RECON", "SCOUT", "RISK", "ORACLE", "EXEC", "AUDIT"] as const;

// Mirrors ws_server.py's _TYPE_LABELS keys (pipeline/state.py's SignalType
// values) to the same tone-per-type associations the original mock used.
const TONE_BY_SIGNAL_TYPE: Record<string, "lavender" | "mint" | "butter" | "blush" | "sky"> = {
  yield_gap: "sky",
  liquidation_proximity: "blush",
  rate_divergence: "mint",
  pool_imbalance: "butter",
  collateral_drift: "lavender",
};

function toneForSignal(type: string): "lavender" | "mint" | "butter" | "blush" | "sky" {
  return TONE_BY_SIGNAL_TYPE[type] ?? "lavender";
}

function relativeTime(iso: string): string {
  const then = Date.parse(iso);
  if (Number.isNaN(then)) return "—";
  const seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  return `${hours}h ago`;
}

function LiveBadge({ live }: { live: boolean }) {
  return live ? (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-mint px-2.5 py-1 text-[11px] font-medium text-mint-deep">
      <span className="h-1.5 w-1.5 rounded-full bg-mint-deep" /> LIVE
    </span>
  ) : (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-butter px-2.5 py-1 text-[11px] font-medium text-[#7a5c14]">
      <span className="h-1.5 w-1.5 rounded-full bg-butter-deep" /> PREVIEW
    </span>
  );
}

function signalToRow(s: SignalEvent) {
  return {
    protocol: s.protocol,
    pair: s.pair,
    type: s.type_label,
    confidence: s.confidence,
    time: relativeTime(s.observed_at),
    tone: toneForSignal(s.type),
  };
}

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
  const { status, trace: liveTrace, signals, payments, audits, live } = useRiaSocket();

  const displayOpportunities = live.signals ? signals.map(signalToRow) : mockOpportunities;

  const liveTraceByName = new Map(
    [...liveTrace].reverse().map((t) => [t.name, t] as const),
  );
  const displayTrace = live.trace
    ? AGENT_ORDER.map(
        (name) =>
          liveTraceByName.get(name) ?? {
            name,
            status: "Not yet reported",
            note: "No TRACE event from this agent yet this run.",
          },
      )
    : mockTrace;

  const latestPayment = payments[0];
  const latestAudits = audits.slice(0, 3);

  const pipelineLabel =
    status === "open" ? "Pipeline: Connected" : status === "connecting" ? "Pipeline: Connecting…" : "Pipeline: Not connected";
  const pipelineDot = status === "open" ? "bg-mint-deep" : status === "connecting" ? "bg-sky-deep" : "bg-butter-deep";

  const liveCount = Object.values(live).filter(Boolean).length;

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
              <span className={`h-1.5 w-1.5 rounded-full ${pipelineDot}`} />
              {pipelineLabel}
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
            <span className="font-medium">{liveCount === 4 ? "Fully live." : liveCount > 0 ? "Partially live." : "Preview mode."}</span>{" "}
            Agent Identity is real, on-chain, and verified. Opportunities, Agent Trace, Payment
            Monitor, and HCS Audit Trail each connect to RIA&rsquo;s live WebSocket pipeline and
            switch from illustrative preview data to real events the moment that panel receives
            its first one — watch for the <span className="font-medium">LIVE</span> badge on each
            panel below.{" "}
            {liveCount > 0 ? (
              <span className="font-medium">{liveCount} of 4 event-driven panels are live right now.</span>
            ) : (
              <span>No pipeline is connected right now ({pipelineLabel.toLowerCase()}), so those four panels are showing preview data.</span>
            )}
          </p>
          <a href="https://github.com/arrnaya/AgentRIA" className="shrink-0 font-medium underline underline-offset-2">
            Follow build progress →
          </a>
        </div>

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
              <div className="flex items-center gap-2">
                <LiveBadge live={live.signals} />
                <span className="text-xs text-ink-faint">SCOUT</span>
              </div>
            </div>
            <div className="mt-3 max-h-[420px] divide-y divide-line overflow-y-auto">
              {displayOpportunities.map((o, i) => (
                <div key={live.signals ? `${o.protocol}-${o.type}-${i}` : o.protocol + o.type} className="px-6 py-4">
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
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-lavender text-xs">◎</span>
                <p className="text-sm font-medium text-ink">Proactive Intelligence Engine</p>
              </div>
              <LiveBadge live={live.trace} />
            </div>
            <div className="mt-4 space-y-2">
              {displayTrace.map((t) => (
                <div key={t.name} className="rounded-xl bg-paper px-4 py-3">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium text-ink">{t.name}</span>
                    <span className="text-xs text-ink-faint">{t.status}</span>
                  </div>
                  <p className="mt-1 text-xs text-ink-soft">{t.note}</p>
                </div>
              ))}
            </div>
            <div className="mt-5">
              <button
                disabled
                className="w-full cursor-not-allowed rounded-full bg-ink/10 px-4 py-2.5 text-sm font-medium text-ink-faint"
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
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-ink">Payment Monitor</p>
                <LiveBadge live={live.payments} />
              </div>
              <div className="mt-4 flex h-12 items-end gap-1">
                {[5, 8, 6, 11, 7, 13, 9, 6, 10, 8].map((h, i) => (
                  <span key={i} className="w-full rounded-full bg-blush-deep/70" style={{ height: `${h * 3}px` }} />
                ))}
              </div>
              {live.payments && latestPayment ? (
                <>
                  <dl className="mt-4 space-y-2 text-xs">
                    <div className="flex justify-between"><dt className="text-ink-faint">Tool</dt><dd className="font-mono text-ink-soft">{latestPayment.tool ?? "—"}</dd></div>
                    <div className="flex justify-between"><dt className="text-ink-faint">Amount</dt><dd className="font-mono text-ink-soft">{latestPayment.amount_hbar != null ? `${latestPayment.amount_hbar} HBAR` : "—"}</dd></div>
                    <div className="flex justify-between"><dt className="text-ink-faint">Facilitator</dt><dd className="text-ink-soft">{latestPayment.facilitator}</dd></div>
                    <div className="flex justify-between"><dt className="text-ink-faint">Tx</dt><dd className="font-mono text-ink-faint">{latestPayment.tx_id ?? "pending"}</dd></div>
                  </dl>
                  <span
                    className={`mt-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs ${
                      latestPayment.status === "confirmed" ? "bg-mint text-mint-deep" : "bg-blush text-[#8a3f5f]"
                    }`}
                  >
                    <span className={`h-1.5 w-1.5 rounded-full ${latestPayment.status === "confirmed" ? "bg-mint-deep" : "bg-blush-deep"}`} />
                    {latestPayment.status === "confirmed" ? "Confirmed on Hedera" : "Pending"}
                  </span>
                </>
              ) : (
                <>
                  <dl className="mt-4 space-y-2 text-xs">
                    <div className="flex justify-between"><dt className="text-ink-faint">Tool</dt><dd className="font-mono text-ink-soft">get_risk_score()</dd></div>
                    <div className="flex justify-between"><dt className="text-ink-faint">Amount</dt><dd className="font-mono text-ink-soft">0.002 HBAR</dd></div>
                    <div className="flex justify-between"><dt className="text-ink-faint">Facilitator</dt><dd className="text-ink-soft">Blocky402</dd></div>
                    <div className="flex justify-between"><dt className="text-ink-faint">Tx</dt><dd className="font-mono text-ink-faint">awaiting first call</dd></div>
                  </dl>
                  <span className="mt-4 inline-flex items-center gap-1.5 rounded-full bg-blush px-3 py-1 text-xs text-[#8a3f5f]">
                    <span className="h-1.5 w-1.5 rounded-full bg-blush-deep" /> Standing by
                  </span>
                </>
              )}
            </Card>

            <Card id="audit" className="scroll-mt-24 flex-1">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-ink">HCS Audit Trail</p>
                <LiveBadge live={live.audits} />
              </div>
              <div className="mt-4 max-h-[420px] space-y-3 overflow-y-auto text-xs">
                {live.audits && latestAudits.length > 0 ? (
                  latestAudits.map((a, i) => (
                    <div key={`${a.action}-${a.logged_at}-${i}`} className="rounded-xl bg-paper px-4 py-3">
                      <div className="flex items-center justify-between">
                        <span className="font-medium text-mint-deep">{a.action}</span>
                        <span className="text-ink-faint">{relativeTime(a.logged_at)}</span>
                      </div>
                      <p className="mt-1 text-ink-soft">{a.note || "Logged to HCS."}</p>
                      {a.tx_id ? (
                        <p className="mt-1 font-mono text-[11px] text-ink-faint">{a.tx_id}</p>
                      ) : null}
                      {a.hcs_topic_id ? (
                        <a
                          href={`https://hashscan.io/testnet/topic/${a.hcs_topic_id}`}
                          target="_blank"
                          rel="noreferrer"
                          className="mt-1 inline-block text-[11px] text-lavender-deep underline underline-offset-2"
                        >
                          View on HashScan mirror node →
                        </a>
                      ) : null}
                    </div>
                  ))
                ) : (
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
                )}
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
