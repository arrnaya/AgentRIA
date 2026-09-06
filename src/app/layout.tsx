import type { Metadata } from "next";
import { Inter, Fraunces, JetBrains_Mono } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-sans",
  subsets: ["latin"],
});

const fraunces = Fraunces({
  variable: "--font-serif",
  subsets: ["latin"],
  style: ["normal", "italic"],
  axes: ["opsz", "SOFT", "WONK"],
});

const mono = JetBrains_Mono({
  variable: "--font-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "RIA — Reconnaissance Intelligence Agent",
  description:
    "RIA is an autonomous multi-agent DeFi intelligence system: live on-chain data from The Graph, LangGraph reasoning, self-paying Hedera x402 execution, and ENSv2 agent identity — built for ETHGlobal Online 2026.",
  metadataBase: new URL("https://ria-agent.vercel.app"),
  openGraph: {
    title: "RIA — On-chain intelligence that acts.",
    description:
      "An autonomous multi-agent DeFi intelligence system built on The Graph, Hedera x402, and ENSv2 for ETHGlobal Online 2026.",
    url: "https://ria-agent.vercel.app",
    siteName: "RIA",
    type: "website",
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${fraunces.variable} ${mono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-paper text-ink">{children}</body>
    </html>
  );
}
