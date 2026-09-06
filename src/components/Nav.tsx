import Link from "next/link";
import { Logomark } from "./Brand";

const links = [
  { href: "#agents", label: "Agents" },
  { href: "#tracks", label: "Tracks" },
  { href: "#verify", label: "Verify" },
  { href: "#faq", label: "FAQ" },
];

export function Nav() {
  return (
    <div className="sticky top-4 z-50 mx-auto flex w-full max-w-3xl items-center justify-between rounded-full border border-white/10 bg-noir/95 px-3 py-2 text-paper shadow-[0_10px_40px_-15px_rgba(23,21,34,0.6)] backdrop-blur">
      <Link href="/" className="flex items-center gap-2 rounded-full px-2 py-1">
        <Logomark className="h-5 w-5 text-lavender-deep" />
        <span className="font-serif-display italic text-lg">RIA</span>
      </Link>
      <nav className="hidden items-center gap-1 md:flex">
        {links.map((l) => (
          <a
            key={l.href}
            href={l.href}
            className="rounded-full px-3 py-1.5 text-sm text-paper/70 transition hover:bg-white/10 hover:text-paper"
          >
            {l.label}
          </a>
        ))}
      </nav>
      <Link
        href="/app"
        className="rounded-full bg-paper px-4 py-2 text-sm font-medium text-noir transition hover:bg-lavender"
      >
        Launch Dashboard
      </Link>
    </div>
  );
}
