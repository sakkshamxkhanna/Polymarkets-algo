"use client";
import { useEffect, useState } from "react";
import { useTradingStore } from "@/lib/store";
import { api } from "@/lib/api";
import { Badge } from "@/components/shared/Badge";
import { clsx } from "clsx";
import { ScrollText, TrendingUp } from "lucide-react";
import type { Order } from "@/lib/types";

interface CalibrationEntry {
  market_id: string;
  predicted_prob: number;
  actual_outcome: number;
  strategy: string;
  brier_score: number;
  timestamp: number;
}

interface CalibrationData {
  entries: CalibrationEntry[];
  brier_score: number | null;
  total_predictions: number;
  correct_predictions: number;
}

type FillFilter = "all" | "profit" | "loss";

export default function JournalPage() {
  const { orders, setOrders } = useTradingStore();
  const [calibration, setCalibration] = useState<CalibrationData | null>(null);
  const [filter, setFilter] = useState<FillFilter>("all");

  useEffect(() => {
    api.getTrades(100)
      .then((d) => {
        const data = d as { trades: Order[] };
        if (data.trades) setOrders(data.trades);
      })
      .catch(() => {});
    api.getCalibration()
      .then((d) => setCalibration(d as CalibrationData))
      .catch(() => {});
  }, [setOrders]);

  const fills = orders.filter((o) => o.state === "FILLED");
  const filtered = fills.filter((o) => {
    if (filter === "all") return true;
    return filter === "profit"
      ? (o.avg_fill_price ?? o.price) >= o.price
      : (o.avg_fill_price ?? o.price) < o.price;
  });

  const totalVolume = fills.reduce((sum, o) => sum + o.filled_size, 0);

  return (
    <div className="flex flex-col h-full overflow-hidden bg-bg-primary">
      {/* Header */}
      <div className="flex-shrink-0 bg-bg-secondary border-b border-border-primary">
        <div className="term-panel-header justify-between">
          <div className="flex items-center gap-2">
            <ScrollText className="w-3 h-3 text-accent-cyan" />
            <span className="term-label">Trade Journal</span>
            <Badge variant="muted">{fills.length} fills</Badge>
          </div>
          <div className="flex items-center gap-3 text-3xs font-mono text-text-dim">
            <span>VOL <span className="text-text-muted tabular-nums">${totalVolume.toFixed(0)}</span></span>
            {calibration?.brier_score != null && (
              <span className={calibration.brier_score < 0.2 ? "text-accent-green" : "text-text-muted"}>
                BS <span className="tabular-nums">{calibration.brier_score.toFixed(3)}</span>
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Summary row */}
      <div className="flex-shrink-0 grid grid-cols-3 divide-x divide-border-primary border-b border-border-primary">
        <div className="px-3 py-2">
          <div className="text-3xs font-mono text-text-dim uppercase tracking-term">FILLS</div>
          <div className="text-lg font-mono font-medium text-text-primary tabular-nums mt-0.5">{fills.length}</div>
        </div>
        <div className="px-3 py-2">
          <div className="text-3xs font-mono text-text-dim uppercase tracking-term">VOLUME</div>
          <div className="text-lg font-mono font-medium text-text-primary tabular-nums mt-0.5">${totalVolume.toFixed(0)}</div>
        </div>
        <div className="px-3 py-2">
          <div className="text-3xs font-mono text-text-dim uppercase tracking-term">BRIER SCORE</div>
          <div className={clsx(
            "text-lg font-mono font-medium tabular-nums mt-0.5",
            calibration?.brier_score != null && calibration.brier_score < 0.2 ? "text-accent-green" : "text-text-primary",
          )}>
            {calibration?.brier_score != null ? calibration.brier_score.toFixed(3) : "—"}
          </div>
          {calibration && (
            <div className="text-3xs font-mono text-text-faint">{calibration.total_predictions} predictions</div>
          )}
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Filter + table */}
        <div className="term-panel mx-3 mt-3">
          <div className="term-panel-header justify-between">
            <span className="term-label">Fill Log</span>
            <div className="flex items-center gap-0.5">
              {(["all", "profit", "loss"] as FillFilter[]).map((f) => (
                <button key={f} onClick={() => setFilter(f)} className={clsx("term-btn", filter === f && "term-btn-active")}>
                  {f.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          {/* Column headers */}
          <div className="px-3 py-1.5 border-b border-border-primary grid grid-cols-[1fr_54px_72px_64px_72px_64px] gap-2">
            {["MARKET", "SIDE", "FILL", "SIZE", "STRAT", "TIME"].map((h, i) => (
              <span key={h} className={clsx("text-3xs font-mono text-text-dim uppercase tracking-term", i > 0 && "text-right")}>
                {h}
              </span>
            ))}
          </div>

          {filtered.length === 0 ? (
            <div className="px-3 py-8 text-center text-2xs font-mono text-text-dim uppercase tracking-term">
              no fills recorded
            </div>
          ) : (
            <div className="divide-y divide-border-faint">
              {filtered.map((trade) => (
                <div key={trade.local_id} className="px-3 py-2 grid grid-cols-[1fr_54px_72px_64px_72px_64px] gap-2 items-center data-row">
                  <div className="min-w-0">
                    <div className="text-xs text-text-muted truncate">{trade.question}</div>
                    {trade.sim_mode && <span className="text-3xs font-mono text-accent-purple">[SIM]</span>}
                  </div>
                  <div className="text-right">
                    <Badge variant={trade.outcome === "YES" ? "green" : "red"} size="xs">{trade.outcome}</Badge>
                  </div>
                  <span className="text-right font-mono text-xs text-text-primary tabular-nums">
                    {(trade.avg_fill_price ?? trade.price).toFixed(3)}
                  </span>
                  <span className="text-right font-mono text-xs text-text-muted tabular-nums">
                    {trade.filled_size.toFixed(1)}
                  </span>
                  <div className="text-right">
                    <Badge variant="muted" size="xs">{trade.strategy}</Badge>
                  </div>
                  <span className="text-right font-mono text-3xs text-text-dim tabular-nums">
                    {new Date(trade.created_at * 1000).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Calibration log */}
        {calibration && (calibration.entries?.length ?? 0) > 0 && (
          <div className="term-panel mx-3 mt-2 mb-3">
            <div className="term-panel-header justify-between">
              <div className="flex items-center gap-2">
                <TrendingUp className="w-3 h-3 text-accent-cyan" />
                <span className="term-label">Calibration Log</span>
              </div>
              <span className="text-3xs font-mono text-text-dim">
                ACC <span className="text-text-muted tabular-nums">
                  {calibration.total_predictions > 0
                    ? ((calibration.correct_predictions / calibration.total_predictions) * 100).toFixed(1)
                    : "—"}%
                </span>
              </span>
            </div>
            <div className="divide-y divide-border-faint">
              {(calibration.entries ?? []).slice(0, 20).map((entry, i) => (
                <div key={i} className="px-3 py-2 flex items-center gap-3 font-mono text-xs">
                  <span className="flex-1 text-text-dim truncate">{entry.market_id.slice(0, 12)}…</span>
                  <span className="text-text-dim tabular-nums">pred <span className="text-text-muted">{(entry.predicted_prob * 100).toFixed(0)}%</span></span>
                  <span className={entry.actual_outcome === 1 ? "text-accent-green" : "text-accent-red"}>
                    {entry.actual_outcome === 1 ? "YES" : "NO"}
                  </span>
                  <span className={clsx(
                    "tabular-nums",
                    entry.brier_score < 0.1 ? "text-accent-green" :
                    entry.brier_score < 0.25 ? "text-text-muted" : "text-accent-red",
                  )}>
                    {entry.brier_score.toFixed(3)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
