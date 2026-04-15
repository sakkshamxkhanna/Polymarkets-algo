"use client";
import { useEffect, useState, use } from "react";
import { useTradingStore } from "@/lib/store";
import { api } from "@/lib/api";
import { Badge } from "@/components/shared/Badge";
import { ResolutionCountdown } from "@/components/shared/ResolutionCountdown";
import { ArrowLeft } from "lucide-react";
import Link from "next/link";
import type { Orderbook } from "@/lib/types";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip,
  ResponsiveContainer, ReferenceLine,
} from "recharts";

type HistoryPoint = { t: number; p: number };
type Interval = "1h" | "1d" | "1w" | "max";

export default function MarketDetailPage({
  params,
}: {
  params: Promise<{ token_id: string }>;
}) {
  const { token_id } = use(params);
  const { orderbooks, markets, opportunities, updateOrderbook, setMarkets } = useTradingStore();
  const ob: Orderbook | undefined = orderbooks[token_id];
  const market = markets.find(
    (m) => m.yes_token_id === token_id || m.no_token_id === token_id,
  );
  const opp = opportunities.find((o) => o.token_id === token_id);

  // Hydrate markets if navigated directly to this URL
  useEffect(() => {
    if (markets.length === 0) {
      api.getMarkets(100).then((d) => {
        const data = d as { markets: import("@/lib/types").Market[] };
        if (data.markets) setMarkets(data.markets);
      }).catch(() => {});
    }
  }, [markets.length, setMarkets]);

  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [interval, setInterval] = useState<Interval>("1d");
  const [histLoading, setHistLoading] = useState(false);

  // Trade form state
  const [outcome, setOutcome] = useState<"YES" | "NO">("YES");
  const [sizeUsdc, setSizeUsdc] = useState("10");
  const [submitting, setSubmitting] = useState(false);
  const [tradeResult, setTradeResult] = useState<string | null>(null);

  useEffect(() => {
    // Subscribe token to WS feed and fetch current snapshot
    api.subscribeTokens([token_id]).catch(() => {});
    api.getOrderbook(token_id)
      .then((d) => updateOrderbook(d as Orderbook))
      .catch(() => {});
  }, [token_id, updateOrderbook]);

  useEffect(() => {
    setHistLoading(true);
    api.getPriceHistory(token_id, interval)
      .then((d) => setHistory(d.history ?? []))
      .catch(() => setHistory([]))
      .finally(() => setHistLoading(false));
  }, [token_id, interval]);

  const entryPrice = outcome === "YES"
    ? (ob?.best_ask ?? market?.mid_price ?? 0.5)
    : (1 - (ob?.best_bid ?? (1 - (market?.mid_price ?? 0.5))));

  async function handleTrade() {
    if (!market) return;
    setSubmitting(true);
    setTradeResult(null);
    try {
      const res = await api.submitManualOrder({
        token_id,
        market_id: market.condition_id,
        question: market.question,
        outcome,
        price: entryPrice,
        size_usdc: parseFloat(sizeUsdc) || 0,
      });
      setTradeResult(`✓ Order submitted — ID: ${res.local_id.slice(0, 8)}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      setTradeResult(`✗ ${msg}`);
    } finally {
      setSubmitting(false);
    }
  }

  // Format chart x-axis
  const chartData = history.map((pt) => ({
    time: new Date(pt.t * 1000).toLocaleTimeString("en-US", {
      hour: "2-digit", minute: "2-digit",
    }),
    price: parseFloat((pt.p * 100).toFixed(2)),
  }));

  const INTERVALS: Interval[] = ["1h", "1d", "1w", "max"];

  return (
    <div className="flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="flex-shrink-0 px-4 py-3 border-b border-border-primary bg-bg-secondary">
        <div className="flex items-center gap-3">
          <Link
            href="/markets"
            className="flex items-center gap-1 text-xs font-mono text-text-dim hover:text-accent-cyan transition-colors"
          >
            <ArrowLeft className="w-3.5 h-3.5" /> Markets
          </Link>
          <div className="w-px h-4 bg-border-primary" />
          {market ? (
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-text-primary truncate">
                {market.question}
              </div>
              <div className="flex items-center gap-2 mt-0.5">
                {market.category && <Badge variant="muted" size="sm">{market.category.toUpperCase()}</Badge>}
                {opp && <Badge variant="yellow" size="sm">EDGE +{opp.net_edge_cents.toFixed(1)}¢</Badge>}
                <ResolutionCountdown hoursToResolution={market.hours_to_resolution ?? 9999} />
              </div>
            </div>
          ) : (
            <span className="text-sm font-mono text-text-dim">{token_id.slice(0, 16)}…</span>
          )}
        </div>
      </div>

      {/* Body */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">

        {/* Price Chart */}
        <div className="bg-bg-secondary border border-border-primary rounded-lg overflow-hidden">
          <div className="flex items-center justify-between px-4 py-3 border-b border-border-primary">
            <span className="text-xs font-mono font-semibold text-text-primary tracking-widest">PRICE HISTORY</span>
            <div className="flex gap-1">
              {INTERVALS.map((iv) => (
                <button
                  key={iv}
                  onClick={() => setInterval(iv)}
                  className={`px-2 py-0.5 text-[10px] font-mono rounded transition-colors ${
                    interval === iv
                      ? "bg-accent-cyan/20 text-accent-cyan"
                      : "text-text-dim hover:text-text-muted"
                  }`}
                >
                  {iv.toUpperCase()}
                </button>
              ))}
            </div>
          </div>

          <div className="h-48 px-2 py-3">
            {histLoading ? (
              <div className="h-full flex items-center justify-center text-xs font-mono text-text-dim">
                Loading…
              </div>
            ) : chartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-xs font-mono text-text-dim">
                No history data
              </div>
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={chartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="priceGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#00d4ff" stopOpacity={0.15} />
                      <stop offset="95%" stopColor="#00d4ff" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis
                    dataKey="time"
                    tick={{ fontSize: 9, fill: "#5a6478", fontFamily: "var(--font-jetbrains-mono)" }}
                    tickLine={false}
                    axisLine={false}
                    interval="preserveStartEnd"
                  />
                  <YAxis
                    domain={[0, 100]}
                    tick={{ fontSize: 9, fill: "#5a6478", fontFamily: "var(--font-jetbrains-mono)" }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={(v) => `${v}%`}
                    width={36}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#0f1117",
                      border: "1px solid #1e2433",
                      borderRadius: 4,
                      fontSize: 11,
                      fontFamily: "var(--font-jetbrains-mono)",
                    }}
                    formatter={(v: number) => [`${v.toFixed(1)}%`, "YES"]}
                    labelStyle={{ color: "#8892a4" }}
                  />
                  <ReferenceLine y={50} stroke="#1e2433" strokeDasharray="3 3" />
                  <Area
                    type="monotone"
                    dataKey="price"
                    stroke="#00d4ff"
                    strokeWidth={1.5}
                    fill="url(#priceGrad)"
                    dot={false}
                    activeDot={{ r: 3, fill: "#00d4ff" }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Orderbook + Trade Execution */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Orderbook */}
          <div className="bg-bg-secondary border border-border-primary rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-border-primary flex items-center justify-between">
              <span className="text-xs font-mono font-semibold text-text-primary tracking-widest">ORDER BOOK</span>
              {ob && (
                <span className="text-[10px] font-mono text-text-dim">
                  Mid <span className="text-text-muted">{ob.mid_price != null ? `${(ob.mid_price * 100).toFixed(1)}¢` : "—"}</span>
                  <span className="mx-2 text-border-primary">|</span>
                  Sprd <span className="text-text-muted">{ob.spread_cents != null ? `${ob.spread_cents.toFixed(1)}¢` : "—"}</span>
                </span>
              )}
            </div>
            {!ob ? (
              <div className="px-4 py-8 text-center text-xs font-mono text-text-dim">
                Waiting for orderbook data…
              </div>
            ) : (
              <div className="p-3 font-mono text-xs">
                {/* Asks */}
                <div className="space-y-0.5 mb-2">
                  {[...ob.asks].reverse().slice(0, 8).map((level, i) => {
                    const maxSize = Math.max(...ob.asks.map((l) => l.size), 1);
                    const pct = (level.size / maxSize) * 100;
                    return (
                      <div key={i} className="relative flex items-center justify-between px-2 py-0.5 rounded-sm overflow-hidden">
                        <div className="absolute inset-y-0 right-0 bg-accent-red/10" style={{ width: `${pct}%` }} />
                        <span className="relative text-accent-red">{(level.price * 100).toFixed(1)}¢</span>
                        <span className="relative text-text-dim">{level.size.toFixed(0)} USDC</span>
                      </div>
                    );
                  })}
                </div>
                <div className="text-center py-1.5 text-[10px] text-text-dim border-y border-border-primary">
                  {ob.spread_cents != null ? `${ob.spread_cents.toFixed(1)}¢ spread` : ""}
                  {ob.mid_price != null && (
                    <span className="ml-2 text-accent-cyan font-medium">{(ob.mid_price * 100).toFixed(1)}¢</span>
                  )}
                </div>
                {/* Bids */}
                <div className="space-y-0.5 mt-2">
                  {ob.bids.slice(0, 8).map((level, i) => {
                    const maxSize = Math.max(...ob.bids.map((l) => l.size), 1);
                    const pct = (level.size / maxSize) * 100;
                    return (
                      <div key={i} className="relative flex items-center justify-between px-2 py-0.5 rounded-sm overflow-hidden">
                        <div className="absolute inset-y-0 right-0 bg-accent-green/10" style={{ width: `${pct}%` }} />
                        <span className="relative text-accent-green">{(level.price * 100).toFixed(1)}¢</span>
                        <span className="relative text-text-dim">{level.size.toFixed(0)} USDC</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Trade Execution */}
          <div className="bg-bg-secondary border border-border-primary rounded-lg overflow-hidden">
            <div className="px-4 py-3 border-b border-border-primary">
              <span className="text-xs font-mono font-semibold text-text-primary tracking-widest">EXECUTE TRADE</span>
              <span className="ml-2 text-[10px] font-mono text-text-dim">[SIM]</span>
            </div>
            <div className="p-4 space-y-4">
              {/* Outcome selector */}
              <div>
                <div className="text-[10px] font-mono text-text-dim mb-2 tracking-wider">OUTCOME</div>
                <div className="grid grid-cols-2 gap-2">
                  {(["YES", "NO"] as const).map((side) => (
                    <button
                      key={side}
                      onClick={() => setOutcome(side)}
                      className={`py-2 text-xs font-mono font-semibold rounded transition-colors border ${
                        outcome === side
                          ? side === "YES"
                            ? "bg-accent-green/15 border-accent-green text-accent-green"
                            : "bg-accent-red/15 border-accent-red text-accent-red"
                          : "border-border-primary text-text-dim hover:border-border-secondary"
                      }`}
                    >
                      {side}
                    </button>
                  ))}
                </div>
              </div>

              {/* Size input */}
              <div>
                <div className="text-[10px] font-mono text-text-dim mb-2 tracking-wider">SIZE (USDC)</div>
                <input
                  type="number"
                  min="1"
                  value={sizeUsdc}
                  onChange={(e) => setSizeUsdc(e.target.value)}
                  className="w-full bg-bg-primary border border-border-primary rounded px-3 py-2 text-sm font-mono text-text-primary focus:outline-none focus:border-accent-cyan"
                  placeholder="10.00"
                />
                <div className="flex gap-1 mt-1.5">
                  {["5", "10", "25", "50"].map((v) => (
                    <button
                      key={v}
                      onClick={() => setSizeUsdc(v)}
                      className="px-2 py-0.5 text-[10px] font-mono text-text-dim border border-border-primary rounded hover:text-text-muted transition-colors"
                    >
                      ${v}
                    </button>
                  ))}
                </div>
              </div>

              {/* Order summary */}
              <div className="bg-bg-primary rounded p-3 space-y-1.5 text-xs font-mono border border-border-primary">
                <div className="flex justify-between">
                  <span className="text-text-dim">Entry price</span>
                  <span className="text-text-muted">{(entryPrice * 100).toFixed(1)}¢</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-dim">Max payout</span>
                  <span className="text-accent-green">
                    ${entryPrice > 0 ? ((parseFloat(sizeUsdc) || 0) / entryPrice).toFixed(2) : "—"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-text-dim">Mode</span>
                  <span className="text-accent-yellow">SIMULATION</span>
                </div>
              </div>

              {tradeResult && (
                <div className={`text-xs font-mono px-3 py-2 rounded border ${
                  tradeResult.startsWith("✓")
                    ? "bg-accent-green/5 border-accent-green/30 text-accent-green"
                    : "bg-accent-red/5 border-accent-red/30 text-accent-red"
                }`}>
                  {tradeResult}
                </div>
              )}

              <button
                onClick={handleTrade}
                disabled={submitting || !market || parseFloat(sizeUsdc) <= 0}
                className={`w-full py-2.5 text-sm font-mono font-semibold rounded transition-colors ${
                  outcome === "YES"
                    ? "bg-accent-green/20 hover:bg-accent-green/30 text-accent-green border border-accent-green/40"
                    : "bg-accent-red/20 hover:bg-accent-red/30 text-accent-red border border-accent-red/40"
                } disabled:opacity-40 disabled:cursor-not-allowed`}
              >
                {submitting ? "Submitting…" : `BUY ${outcome}`}
              </button>
            </div>
          </div>
        </div>

        {/* Market Info */}
        {market && (
          <div className="bg-bg-secondary border border-border-primary rounded-lg p-4">
            <div className="text-xs font-mono font-semibold text-text-primary tracking-widest mb-3">MARKET INFO</div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              {[
                { label: "VOLUME", value: `$${fmtVol(market.volume_usd)}` },
                { label: "MID", value: `${(market.mid_price * 100).toFixed(1)}¢` },
                { label: "SPREAD", value: `${market.spread_cents?.toFixed(1) ?? "—"}¢` },
                { label: "ENDS", value: new Date(market.end_date).toLocaleDateString() },
              ].map(({ label, value }) => (
                <div key={label} className="bg-bg-primary rounded p-3 border border-border-primary">
                  <div className="text-[10px] font-mono text-text-dim tracking-widest">{label}</div>
                  <div className="text-sm font-mono text-text-muted mt-1">{value}</div>
                </div>
              ))}
            </div>
            {opp && (
              <div className="mt-3 bg-accent-yellow/5 border border-accent-yellow/20 rounded p-3">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-accent-yellow animate-pulse" />
                  <span className="text-xs font-mono text-accent-yellow">Resolution Opportunity Detected</span>
                </div>
                <div className="grid grid-cols-3 gap-2 text-xs font-mono">
                  <div><span className="text-text-dim">Side: </span><span className="text-text-muted">{opp.side}</span></div>
                  <div><span className="text-text-dim">Edge: </span><span className="text-accent-green">+{opp.net_edge_cents.toFixed(1)}¢</span></div>
                  <div><span className="text-text-dim">Conf: </span><span className="text-text-muted">{(opp.confidence * 100).toFixed(0)}%</span></div>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function fmtVol(v: number): string {
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1)}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}K`;
  return v.toFixed(0);
}
