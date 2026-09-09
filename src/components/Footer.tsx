import Link from "next/link";
import { Logomark } from "./Brand";

const columns = [
  {
    heading: "Project",
    links: [
      { label: "Executive Summary", href: "/#top" },
      { label: "Architecture", href: "/#architecture" },
      { label: "Build Status", href: "https://github.com/arrnaya/AgentRIA" },
    ],
  },
  {
    heading: "Tracks",
    links: [
      { label: "The Graph — AI Use Case", href: "https://github.com/arrnaya/AgentRIA#hackathon-qualification-mapping" },
      { label: "Hedera — Agentic Payments", href: "https://github.com/arrnaya/AgentRIA#hackathon-qualification-mapping" },
      { label: "ENS — Best Use of ENSv2", href: "https://github.com/arrnaya/AgentRIA#hackathon-qualification-mapping" },
    ],
  },
  {
    heading: "Resources",
    links: [
      { label: "GitHub Repository", href: "https://github.com/arrnaya/AgentRIA" },
      { label: "README", href: "https://github.com/arrnaya/AgentRIA#readme" },
      { label: "Live Dashboard", href: "/app" },
    ],
  },
];

export function Footer() {
  return (
    <footer className="mt-32 rounded-t-[2.5rem] bg-noir text-paper">
      <div className="mx-auto max-w-6xl px-6 pt-16 pb-10 sm:px-10">
        <div className="grid grid-cols-2 gap-10 border-b border-noir-line pb-14 sm:grid-cols-4">
          <div className="col-span-2 sm:col-span-1">
            <div className="flex items-center gap-2">
              <Logomark className="h-6 w-6 text-lavender-deep" />
              <span className="font-serif-display italic text-xl">RIA</span>
            </div>
            <p className="mt-3 max-w-[22ch] text-sm text-paper/55">
              On-chain intelligence that acts. Built for ETHGlobal Online 2026.
            </p>
          </div>
          {columns.map((col) => (
            <div key={col.heading}>
              <h4 className="text-xs font-medium uppercase tracking-wider text-paper/40">
                {col.heading}
              </h4>
              <ul className="mt-4 space-y-2.5">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <Link
                      href={l.href}
                      className="text-sm text-paper/70 transition hover:text-paper"
                    >
                      {l.label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="flex flex-col gap-6 pt-8 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs text-paper/40">Builder</p>
            <p className="mt-1 text-sm text-paper/80">
              Arrnaya (Arun Kumar Yadav) ·{" "}
              <a href="https://github.com/arrnaya" className="underline decoration-paper/30 underline-offset-4 hover:decoration-paper">
                github.com/arrnaya
              </a>
            </p>
          </div>
          <a
            href="https://github.com/arrnaya/AgentRIA"
            className="inline-flex w-fit items-center gap-2 rounded-full border border-paper/20 px-4 py-2 text-sm transition hover:bg-white/10"
          >
            <svg viewBox="0 0 24 24" className="h-4 w-4 fill-current">
              <path d="M12 .5C5.73.5.5 5.74.5 12.02c0 5.02 3.25 9.28 7.77 10.79.57.1.78-.25.78-.55 0-.27-.01-1.16-.02-2.11-3.16.69-3.83-1.34-3.83-1.34-.52-1.32-1.26-1.67-1.26-1.67-1.03-.71.08-.69.08-.69 1.14.08 1.74 1.17 1.74 1.17 1.01 1.74 2.65 1.24 3.3.95.1-.74.4-1.24.72-1.53-2.52-.29-5.17-1.26-5.17-5.62 0-1.24.44-2.26 1.17-3.06-.12-.29-.51-1.46.11-3.04 0 0 .96-.31 3.14 1.17a10.9 10.9 0 0 1 5.72 0c2.18-1.48 3.14-1.17 3.14-1.17.62 1.58.23 2.75.11 3.04.73.8 1.17 1.82 1.17 3.06 0 4.37-2.66 5.33-5.19 5.61.41.36.77 1.07.77 2.15 0 1.55-.01 2.8-.01 3.18 0 .3.2.66.79.55A10.53 10.53 0 0 0 23.5 12.02C23.5 5.74 18.27.5 12 .5Z" />
            </svg>
            View source on GitHub
          </a>
        </div>

        <p className="mt-10 text-[11px] leading-relaxed text-paper/35">
          RIA is an independent hackathon project built for ETHGlobal Online 2026. Not affiliated
          with or endorsed by The Graph, Hedera, ENS, or Anthropic. Trademarks referenced belong to
          their respective owners.
        </p>
      </div>

      <div className="select-none overflow-hidden px-6 pb-4 sm:px-10">
        <span className="block font-serif-display italic text-[22vw] leading-none tracking-tighter text-paper sm:text-[15vw]">
          RIA
        </span>
      </div>
    </footer>
  );
}
