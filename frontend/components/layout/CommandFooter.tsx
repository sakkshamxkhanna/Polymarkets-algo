"use client";
import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useTradingStore } from "@/lib/store";
import { clsx } from "clsx";

const COMMANDS = [
  { key: "F1",  label: "DASH",  href: "/" },
  { key: "F2",  label: "MKTS",  href: "/markets" },
  { key: "F3",  label: "POS",   href: "/positions" },
  { key: "F4",  label: "JRNL",  href: "/journal" },
  { key: "F5",  label: "STRAT", href: "/strategy" },
];

/**
 * Bloomberg-style function-key command bar.
 * Always visible at the bottom; F1-F5 navigate, F9 fires kill switch (with confirm),
 * F10 toggles sim mode confirmation.
 */
export function CommandFooter() {
  const router = useRouter();
  const pathname = usePathname();
  const { simMode, killSwitchActive, wsConnected, systemStatus } = useTradingStore();
  const [now, setNow] = useState<Date | null>(null);

  useEffect(() => {
    setNow(new Date());
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const target = COMMANDS.find((c) => c.key === e.key);
      if (target) {
        e.preventDefault();
        router.push(target.href);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [router]);

  const apiP99 = systemStatus?.kill_switch?.api_p99_ms ?? 0;
  const wsGap = systemStatus?.ws_gap_seconds ?? 0;

  return (
    <footer className="flex-shrink-0 h-[26px] flex items-stretch border-t border-border-primary bg-bg-secondary">
      {/* Left: function keys */}
      <div className="flex items-center gap-0.5 px-2 border-r border-border-primary">
        {COMMANDS.map(({ key, label, href }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          return (
            <button
              key={key}
              onClick={() => router.push(href)}
              className={clsx(
                "flex items-center gap-1 h-[18px] px-1.5 border transition-colors text-3xs font-mono uppercase tracking-term",
                active
                  ? "border-accent-cyan/50 bg-accent-cyan/10 text-accent-cyan"
                  : "border-border-strong bg-bg-tertiary text-text-muted hover:text-text-primary hover:border-border-strong",
              )}
              title={`${key} • ${label}`}
            >
              <span className={clsx("font-bold", active ? "text-accent-cyan" : "text-text-dim")}>
                {key}
              </span>
              <span>{label}</span>
            </button>
          );
        })}
      </div>

      {/* Mid: command hint */}
      <div className="flex items-center gap-3 px-3 text-3xs font-mono text-text-dim">
        <span className="uppercase tracking-term">cmd</span>
        <span className="text-text-faint">›</span>
        <span className="text-text-muted">type symbol or command</span>
      </div>

      {/* Right: live system metrics */}
      <div className="ml-auto flex items-center gap-3 px-3 border-l border-border-primary text-3xs font-mono uppercase tracking-term">
        <Metric
          label="API P99"
          value={`${apiP99.toFixed(0)}ms`}
          warn={apiP99 > 500}
        />
        <Metric
          label="WS GAP"
          value={`${wsGap.toFixed(1)}s`}
          warn={wsGap > 10}
        />
        <Metric
          label="MODE"
          value={simMode ? "SIM" : "LIVE"}
          tone={simMode ? "purple" : "red"}
        />
        <Metric
          label="LINK"
          value={wsConnected ? "UP" : "DOWN"}
          tone={wsConnected ? "green" : "red"}
        />
        {killSwitchActive && (
          <span className="flex items-center gap-1 text-accent-red font-bold">
            <span className="w-1 h-1 rounded-full bg-accent-red dot-pulse-red" />
            HALTED
          </span>
        )}
        <span className="text-text-muted tabular-nums">
          {now ? now.toUTCString().slice(17, 25) : "—:—:—"}
        </span>
      </div>
    </footer>
  );
}

function Metric({
  label, value, warn, tone,
}: {
  label: string;
  value: string;
  warn?: boolean;
  tone?: "green" | "red" | "purple" | "amber";
}) {
  const valueColor =
    warn          ? "text-accent-amber" :
    tone === "green"  ? "text-accent-green"  :
    tone === "red"    ? "text-accent-red"    :
    tone === "purple" ? "text-accent-purple" :
    tone === "amber"  ? "text-accent-amber"  :
    "text-text-muted";

  return (
    <span className="flex items-center gap-1">
      <span className="text-text-faint">{label}</span>
      <span className={valueColor}>{value}</span>
    </span>
  );
}
