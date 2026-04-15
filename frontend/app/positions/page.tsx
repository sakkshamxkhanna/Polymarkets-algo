"use client";
import { useEffect } from "react";
import { useTradingStore } from "@/lib/store";
import { api } from "@/lib/api";
import { Badge } from "@/components/shared/Badge";
import { StatCard } from "@/components/shared/StatCard";
import { clsx } from "clsx";
import { TrendingUp, Wallet } from "lucide-react";
import type { PositionsData } from "@/lib/types";
import Link from "next/link";

export default function PositionsPage() {
  const { positions, setPositions, setPnl } = useTradingStore();

  useEffect(() => {
    api.getPositions().then((d) => setPositions(d as PositionsData)).catch(() => {});
    api.getPnl().then((d) => setPnl(d as Parameters<typeof setPnl>[0])).catch(() => {});
  }, [setPositions, setPnl]);

  const pos = positions;

  return (
    <div className="flex flex-col h-full overflow-hidden bg-bg-primary">
      {/* Header */}
      <div className="flex-shrink-0 bg-bg-secondary border-b border-border-primary">
        <div className="term-panel-header justify-between">
          <div className="flex items-center gap-2">
            <Wallet className="w-3 h-3 text-accent-cyan" />
            <span className="term-label">Open Positions</span>
            {pos && <Badge variant="cyan">{pos.position_count}</Badge>}
          </div>
          {pos && (
            <div className="flex items-center gap-4 text-3xs font-mono text-text-dim">
              <span>NOTIONAL <span className="text-text-muted">${pos.total_notional.toFixed(0)}</span></span>
              <span className={clsx(
                "font-medium",
                pos.unrealized_pnl >= 0 ? "text-accent-green" : "text-accent-red",
              )}>
                UNREAL {pos.unrealized_pnl >= 0 ? "+" : ""}${pos.unrealized_pnl.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Summary */}
      {pos && (
        <div className="flex-shrink-0 grid grid-cols-4 divide-x divide-border-primary border-b border-border-primary">
          <StatCard label="TOTAL CAPITAL"  value={`$${pos.total_capital.toFixed(0)}`} hint="USDC" highlight="cyan" />
          <StatCard label="NOTIONAL"       value={`$${pos.total_notional.toFixed(0)}`} />
          <StatCard label="UNREALIZED P&L" value={`${pos.unrealized_pnl >= 0 ? "+" : ""}$${Math.abs(pos.unrealized_pnl).toFixed(2)}`} delta={pos.unrealized_pnl} />
          <StatCard label="DAILY P&L"      value={`${pos.daily_pnl >= 0 ? "+" : ""}$${Math.abs(pos.daily_pnl).toFixed(2)}`} delta={pos.daily_pnl} />
        </div>
      )}

      {/* Column headers */}
      <div className="flex-shrink-0 bg-bg-secondary border-b border-border-primary px-3 py-1.5 grid grid-cols-[1fr_54px_120px_80px_90px_64px] gap-2">
        {["MARKET", "SIDE", "ENTRY → MARK", "SIZE", "UNR. P&L", "HELD"].map((h, i) => (
          <span key={h} className={clsx("text-3xs font-mono text-text-dim uppercase tracking-term", i > 0 && "text-right")}>
            {h}
          </span>
        ))}
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto">
        {!pos || pos.positions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 gap-2">
            <TrendingUp className="w-6 h-6 text-text-dim" />
            <span className="text-2xs font-mono text-text-dim uppercase tracking-term">no open positions</span>
            <span className="text-3xs font-mono text-text-faint">capital idle · awaiting signal</span>
          </div>
        ) : (
          <div className="divide-y divide-border-faint">
            {pos.positions.map((position) => {
              const changePct = position.entry_price > 0
                ? ((position.current_price - position.entry_price) / position.entry_price) * 100
                : 0;
              const heldHours = (Date.now() - new Date(position.opened_at).getTime()) / 3_600_000;
              const heldStr = heldHours < 1 ? `${Math.floor(heldHours * 60)}m`
                : heldHours < 24 ? `${heldHours.toFixed(1)}h`
                : `${Math.floor(heldHours / 24)}d`;

              return (
                <div key={position.token_id} className="px-3 py-2 grid grid-cols-[1fr_54px_120px_80px_90px_64px] gap-2 items-center data-row">
                  <div className="min-w-0">
                    <div className="text-xs text-text-primary truncate">{position.question}</div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <Badge variant="muted" size="xs">{position.strategy}</Badge>
                      <Link href={`/markets/${position.token_id}`} className="text-3xs font-mono text-accent-cyan/60 hover:text-accent-cyan">BOOK →</Link>
                    </div>
                  </div>

                  <div>
                    <Badge variant={position.side === "YES" ? "green" : "red"} size="xs">{position.side}</Badge>
                  </div>

                  <div className="text-right font-mono text-xs tabular-nums">
                    <span className="text-text-dim">{position.entry_price.toFixed(3)}</span>
                    <span className="text-text-faint mx-1">→</span>
                    <span className={changePct >= 0 ? "text-accent-green" : "text-accent-red"}>
                      {position.current_price.toFixed(3)}
                    </span>
                    <div className={clsx("text-3xs", changePct >= 0 ? "text-accent-green/60" : "text-accent-red/60")}>
                      {changePct >= 0 ? "+" : ""}{changePct.toFixed(1)}%
                    </div>
                  </div>

                  <span className="text-right font-mono text-xs text-text-muted tabular-nums">${position.size_usdc.toFixed(1)}</span>

                  <div className="text-right">
                    <span className={clsx("font-mono text-xs font-medium tabular-nums", position.unrealized_pnl >= 0 ? "text-accent-green" : "text-accent-red")}>
                      {position.unrealized_pnl >= 0 ? "+" : ""}${position.unrealized_pnl.toFixed(2)}
                    </span>
                  </div>

                  <span className="text-right font-mono text-2xs text-text-dim tabular-nums">{heldStr}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
