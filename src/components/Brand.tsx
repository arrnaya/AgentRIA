export function Logomark({ className = "h-6 w-6" }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" fill="none" className={className} aria-hidden="true">
      <circle cx="16" cy="16" r="15" stroke="currentColor" strokeOpacity="0.35" strokeWidth="1.5" />
      <circle cx="16" cy="16" r="9.5" stroke="currentColor" strokeOpacity="0.6" strokeWidth="1.5" />
      <circle cx="16" cy="16" r="3.5" fill="currentColor" />
      <path
        d="M16 1.5V6M16 26v4.5M1.5 16H6M26 16h4.5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
      />
    </svg>
  );
}

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <span className={`font-serif-display italic tracking-tight ${className}`}>RIA</span>
  );
}
