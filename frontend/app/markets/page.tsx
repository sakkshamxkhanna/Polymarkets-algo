"use client";
import { useEffect, useState } from "react";
import { useTradingStore } from "@/lib/store";
import { api } from "@/lib/api";
import { Badge } from "@/components/shared/Badge";
import { ResolutionCountdown } from "@/components/shared/ResolutionCountdown";
import { clsx } from "clsx";
import { Search, TrendingUp } from "lucide-react";
import type { Market, Opportunity } from "@/lib/types";
import Link from "next/link";

type SortKey = "volume" | "resolution" | "spread" | "edge";
type Category = "All" | "Sports" | "Politics" | "Economics" | "Crypto";

export default function MarketsPage() {
  const { markets, opportunities, setMarkets } = useTradingStore();
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState<Category>("All");
  const [sortKey, setSortKey] = useState<SortKey>("resolution");

  useEffect(() => {
    api.getMarkets(100)
      .then((d) => {
        const data = d as { markets: Market[] };
        if (data.markets) setMarkets(data.markets);
      })
      .catch(() => {});
  }, [setMarkets]);

  const oppByMarket = new Map(opportunities.map((o) => [o.market_id, o]));

  let filtered = markets.filter((m) => {
    if (search && !m.question.toLowerCase().includes(search.toLowerCase())) return false;
    if (category !== "All" && m.category?.toLowerCase() !== category.toLowerCase()) return false;
    return true;
  });

  filtered = [...filtered].sort((a, b) => {
    if (sortKey === "volume")     return (b.volume_usd ?? 0) - (a.volume_usd ?? 0);
    if (sortKey === "resolution") return (a.hours_to_resolution ?? 9999) - (b.hours_to_resolution ?? 9999);
    if (sortKey === "spread")     return (a.spread_cents ?? 0) - (b.spread_cents ?? 0);
    if (sortKey === "edge") {
      const aEdge = oppByMarket.get(a.condition_id)?.net_edge_cents ?? -1;
      const bEdge = oppByMarket.get(b.condition_id)?.net_edge_cents ?? -1;
      return bEdge - aEdge;
    }
    return 0;
  });

  const categories: Category[] = ["All", "Sports", "Politics", "Economics", "Crypto"];
  const sortOptions: { key: SortKey; label: string }[] = [
    { key: "resolution", label: "T−0" },
    { key: "volume",     label: "VOL" },
    { key: "spread",     label: "SPRD" },
    { key: "edge",       label: "EDGE" },
  ];

  return (
    <div className="flex flex-col h-full overflow-hidden bg-bg-primary">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-border-primary bg-bg-secondary">
        <div className="term-panel-header justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-3 h-3 text-accent-cyan" />
            <span className="term-label">Market Scanner</span>
            <Badge variant="muted">{filtered.length}</Badge>
            {opportunities.length > 0 && <Badge variant="amber" dot>{opportunities.length} opp</Badge>}
          </div>
        </div>

        {/* Toolbar */}
        <div className="flex items-center gap-2 px-3 pb-2">
          <div className="relative flex-1 min-w-[180px]">
            <Search className="absolute left-2 top-1/2 -translate-y-1/2 w-3 h-3 text-text-dim" />
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="search markets…"
              className="term-input w-full pl-7 py-1 text-2xs"
            />
          </div>

          <div className="flex items-center gap-0.5">
            {categories.map((cat) => (
              <button
                key={cat}
                onClick={() => setCategory(cat)}
                className={clsx("term-btn", category === cat && "term-btn-active")}
              >
                {cat}
              </button>
            ))}
          </div>

          <div className="w-px h-4 bg-border-primary" />

          <div className="flex items-center gap-0.5">
            {sortOptions.map((s) => (
              <button
                key={s.key}
                onClick={() => setSortKey(s.key)}
                className={clsx("term-btn", sortKey === s.key && "term-btn-active")}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Column headers */}
      <div className="flex-shrink-0 sticky top-0 z-10 bg-bg-secondary border-b border-border-primary px-3 py-1.5 grid grid-cols-[1fr_70px_60px_80px_90px_72px] gap-2">
        {["MARKET", "MID", "SPRD", "VOL 24H", "T−0", "EDGE"].map((h, i) => (
          <span key={h} className={clsx("text-3xs font-mono text-text-dim uppercase tracking-term", i > 0 && "text-right")}>
            {h}
          </span>
        ))}
      </div>

      {/* Rows */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="flex items-center justify-center py-20 text-2xs font-mono text-text-dim uppercase tracking-term">
            no markets match filter
          </div>
        ) : (
          <div className="divide-y divide-border-faint">
            {filtered.map((market) => (
              <MarketRow key={market.condition_id} market={market} opportunity={oppByMarket.get(market.condition_id)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function MarketRow({ market, opportunity }: { market: Market; opportunity: Opportunity | undefined }) {
  const hasOpp = Boolean(opportunity);
  const midPct = (market.mid_price * 100).toFixed(1);

  return (
    <div className={clsx(
      "px-3 py-2 grid grid-cols-[1fr_70px_60px_80px_90px_72px] gap-2 items-center data-row",
      hasOpp && "border-l-2 border-accent-amber/50",
    )}>
      <div className="min-w-0">
        <div className="text-xs text-text-primary truncate">{market.question}</div>
        <div className="flex items-center gap-1.5 mt-0.5">
          {market.category && <Badge variant="muted" size="xs">{market.category}</Badge>}
          {hasOpp && <Badge variant="amber" size="xs">OPP</Badge>}
          <Link href={`/markets/${market.yes_token_id}`} className="text-3xs font-mono text-accent-cyan/60 hover:text-accent-cyan">
            BOOK →
          </Link>
        </div>
      </div>

      <span className="text-right text-xs font-mono text-text-primary tabular-nums">{midPct}%</span>

      <span className={clsx(
        "text-right text-xs font-mono tabular-nums",
        (market.spread_cents ?? 0) < 3 ? "text-accent-green" :
        (market.spread_cents ?? 0) < 8 ? "text-text-muted" : "text-accent-red",
      )}>
        {market.spread_cents?.toFixed(1) ?? "—"}¢
      </span>

      <span className="text-right text-xs font-mono text-text-muted tabular-nums">
        {market.volume_usd != null ? fmtVol(market.volume_usd) : "—"}
      </span>

      <div className="text-right">
        <ResolutionCountdown hoursToResolution={market.hours_to_resolution ?? 9999} />
      </div>

      <span className={clsx("text-right text-xs font-mono font-medium tabular-nums", opportunity ? "text-accent-green" : "text-text-dim")}>
        {opportunity ? `+${opportunity.net_edge_cents.toFixed(1)}¢` : "—"}
      </span>
    </div>
  );
}

function fmtVol(v: number): string {
  if (v >= 1_000_000) return `$${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000)     return `$${(v / 1_000).toFixed(0)}K`;
  return `$${v.toFixed(0)}`;
}
