import type { Metadata } from "next";
import { JetBrains_Mono, IBM_Plex_Sans, IBM_Plex_Sans_Condensed } from "next/font/google";
import "./globals.css";
import { ClientLayout } from "@/components/layout/ClientLayout";

// Self-hosted via next/font: zero runtime requests, zero CLS, no compile fetch.
const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

const ibmPlexSans = IBM_Plex_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-ibm-plex",
  display: "swap",
});

const ibmPlexCondensed = IBM_Plex_Sans_Condensed({
  subsets: ["latin"],
  weight: ["500", "600", "700"],
  variable: "--font-ibm-plex-condensed",
  display: "swap",
});

export const metadata: Metadata = {
  title: "PolyTrader — Prediction Market Trading System",
  description: "Institutional-grade Polymarket algorithmic trading interface",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`h-full ${jetbrainsMono.variable} ${ibmPlexSans.variable} ${ibmPlexCondensed.variable}`}
    >
      <body className="h-full overflow-hidden bg-bg-primary text-text-primary">
        <ClientLayout>{children}</ClientLayout>
      </body>
    </html>
  );
}
