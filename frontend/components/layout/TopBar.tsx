"use client";
import { useEffect, useState } from "react";
import { useTradingStore } from "@/lib/store";
import { clsx } from "clsx";

/**
 * Terminal-style status header. Two rows:
 *   Row 1: brand + live ticker (capital, daily PnL, unrealized, sharpe, latency)
 *   Row 2: scrolling sub-status (cycle, scanned, opps, mode, clock)
 */
export function TopBar() {
  const {
    wsConnected, wsLatencyMs, simMode, cycleStats, opportunities, pnl, killSwitchActive,
  } = useTradingStore();

  const dailyPnl = pnl?.daily_pnl ?? 0;
  const unrealized = pnl?.unrealized_pnl ?? 0;
  const totalCapital = pnl?.total_capital ?? 0;
  const sharpe = pnl?.sharpe_ratio;

  return (
    <header className="flex-shrink-0 bg-bg-secondary border-b border-border-primary">
      {/* Row 1 — Brand + macro ticker */}
      <div className="h-[34px] flex items-center px-3 border-b border-border-faint">
        <div className="flex items-baseline gap-2 pr-4 mr-3 border-r border-border-primary h-full pt-2">
          <span className="font-display font-bold text-sm text-text-primary tracking-tight">
            POLYTRADER
          </span>
          <span className="text-3xs font-mono text-text-dim uppercase tracking-term">
            terminal
          </span>
        </div>

        <TickerCell label="CAPITAL" value={`$${formatNumber(totalCapital, 0)}`} />
        <TickerCell
          label="DAILY"
          value={fmtSigned(dailyPnl)}
          tone={tone(dailyPnl)}
        />
        <TickerCell
          label="UNREAL"
          value={fmtSigned(unrealized)}
          tone={tone(unrealized)}
        />
        <TickerCell
          label="SHARPE"
          value={sharpe != null ? sharpe.toFixed(2) : "—"}
          tone={sharpe != null && sharpe > 0 ? "up" : "neutral"}
        />
        <TickerCell
          label="OPEN"
          value={(pnl?.position_count ?? 0).toString()}
        />

        <div className="ml-auto flex items-center gap-3 h-full">
          {killSwitchActive && (
            <div className="flex items-center gap-1.5 px-2 py-0.5 bg-accent-red/15 border border-accent-red/50">
              <span className="w-1.5 h-1.5 rounded-full bg-accent-red dot-pulse-red" />
              <span className="text-2xs font-mono font-bold text-accent-red uppercase tracking-term">
                KILL SWITCH
              </span>
            </div>
          )}

          <ModePill simMode={simMode} />

          <div className="flex items-center gap-1.5">
            <span
              className={clsx(
                "w-1.5 h-1.5 rounded-full",
                wsConnected ? "bg-accent-green dot-pulse-green" : "bg-accent-red dot-pulse-red",
              )}
            />
            <span className="text-2xs font-mono uppercase tracking-term text-text-muted">
              {wsConnected ? "WS LIVE" : "OFFLINE"}
            </span>
            {wsConnected && wsLatencyMs > 0 && (
              <span className="text-2xs font-mono text-text-dim">
                {wsLatencyMs.toFixed(0)}ms
              </span>
            )}
          </div>

          <LiveClock />
        </div>
      </div>

      {/* Row 2 — Sub-status */}
      <div className="h-[22px] flex items-center px-3 gap-4 text-2xs font-mono text-text-dim bg-bg-primary/40">
        {cycleStats ? (
          <>
            <SubItem label="CYCLE" value={cycleStats.cycle_id?.slice(0, 8) ?? "—"} />
            <SubItem label="SCAN" value={cycleStats.markets_scanned?.toString() ?? "0"} />
            <SubItem label="RAW" value={cycleStats.raw_opportunities?.toString() ?? "0"} />
            <SubItem
              label="VERIFIED"
              value={cycleStats.verified_opportunities?.toString() ?? "0"}
              highlight={(cycleStats.verified_opportunities ?? 0) > 0}
            />
            <SubItem label="ORDERS" value={cycleStats.orders_submitted?.toString() ?? "0"} />
          </>
        ) : (
          <span className="text-text-faint">awaiting first cycle…</span>
        )}

        {opportunities.length > 0 && (
          <div className="ml-auto flex items-center gap-1.5">
            <span className="w-1 h-1 rounded-full bg-accent-amber dot-pulse-amber" />
            <span className="text-accent-amber font-medium">
              {opportunities.length} OPPORTUNIT{opportunities.length === 1 ? "Y" : "IES"} DETECTED
            </span>
          </div>
        )}
      </div>
    </header>
  );
}

function TickerCell({
  label, value, tone = "neutral",
}: {
  label: string;
  value: string;
  tone?: "up" | "down" | "neutral";
}) {
  const color =
    tone === "up"   ? "text-accent-green" :
    tone === "down" ? "text-accent-red"   :
    "text-text-primary";
  return (
    <div className="flex flex-col justify-center pr-4 mr-3 border-r border-border-faint h-full">
      <span className="text-3xs font-mono text-text-dim uppercase tracking-term leading-none">
        {label}
      </span>
      <span className={clsx("text-xs font-mono font-medium leading-none mt-0.5", color)}>
        {value}
      </span>
    </div>
  );
}

function ModePill({ simMode }: { simMode: boolean }) {
  return (
    <span
      className={clsx(
        "flex items-center gap-1 px-2 h-[18px] border text-3xs font-mono font-bold uppercase tracking-term",
        simMode
          ? "border-accent-purple/50 bg-accent-purple/10 text-accent-purple"
          : "border-accent-red/60 bg-accent-red/10 text-accent-red",
      )}
    >
      <span className={clsx("w-1 h-1 rounded-full", simMode ? "bg-accent-purple" : "bg-accent-red")} />
      {simMode ? "SIMULATION" : "LIVE"}
    </span>
  );
}

function SubItem({
  label, value, highlight,
}: { label: string; value: string; highlight?: boolean }) {
  return (
    <span className="flex items-center gap-1">
      <span className="text-text-faint">{label}</span>
      <span className={clsx(highlight ? "text-accent-amber font-medium" : "text-text-muted")}>
        {value}
      </span>
    </span>
  );
}

function LiveClock() {
  const [time, setTime] = useState<Date | null>(null);
  useEffect(() => {
    setTime(new Date());
    const t = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return (
    <span className="text-2xs font-mono text-text-muted tracking-tight tabular-nums">
      {time ? `${time.toUTCString().slice(17, 25)} UTC` : "—:—:—"}
    </span>
  );
}

function tone(n: number): "up" | "down" | "neutral" {
  if (n > 0) return "up";
  if (n < 0) return "down";
  return "neutral";
}

function fmtSigned(n: number): string {
  if (n === 0) return "$0.00";
  return `${n >= 0 ? "+" : "-"}$${Math.abs(n).toFixed(2)}`;
}

function formatNumber(n: number, decimals = 0): string {
  return n.toLocaleString("en-US", {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
}
