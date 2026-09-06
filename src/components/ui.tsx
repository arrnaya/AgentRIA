import type { ReactNode } from "react";

export function Eyebrow({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-line bg-white/60 px-3 py-1 text-xs font-medium uppercase tracking-wider text-ink-soft">
      {children}
    </span>
  );
}

export function Pill({
  tone = "lavender",
  children,
}: {
  tone?: "lavender" | "mint" | "butter" | "blush" | "sky";
  children: ReactNode;
}) {
  const tones: Record<string, string> = {
    lavender: "bg-lavender text-[#4b3d8f]",
    mint: "bg-mint text-[#256b4a]",
    butter: "bg-butter text-[#7a5c14]",
    blush: "bg-blush text-[#8a3f5f]",
    sky: "bg-sky text-[#2c5a80]",
  };
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${tones[tone]}`}>
      {children}
    </span>
  );
}

export function Card({
  className = "",
  id,
  children,
}: {
  className?: string;
  id?: string;
  children: ReactNode;
}) {
  return (
    <div
      id={id}
      className={`rounded-3xl border border-line bg-white/80 p-6 shadow-[0_1px_0_rgba(28,26,36,0.02)] backdrop-blur-sm ${className}`}
    >
      {children}
    </div>
  );
}

export function SectionHeading({
  eyebrow,
  title,
  italic,
  description,
}: {
  eyebrow?: string;
  title: string;
  italic?: string;
  description?: string;
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      {eyebrow ? <Eyebrow>{eyebrow}</Eyebrow> : null}
      <h2 className="mt-4 text-3xl font-medium tracking-tight text-ink sm:text-4xl">
        {title} {italic ? <span className="font-serif-display italic text-lavender-deep">{italic}</span> : null}
      </h2>
      {description ? (
        <p className="mt-4 text-balance text-[15px] leading-relaxed text-ink-soft">{description}</p>
      ) : null}
    </div>
  );
}
