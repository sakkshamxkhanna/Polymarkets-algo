"use client";
import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { clsx } from "clsx";
import {
  Activity, TrendingUp, Zap, ArrowUpRight,
  AlertTriangle, Radio, Cpu, Shield, Target, Gauge, Play, CheckCircle,
} from "lucide-react";
import { useTradingStore } from "@/lib/store";
import { api } from "@/lib/api";
import { Panel } from "@/components/shared/Panel";
import { StatCard } from "@/components/shared/StatCard";
import { Badge } from "@/components/shared/Badge";
import { ResolutionCountdown } from "@/components/shared/ResolutionCountdown";
import type {
  Opportunity, PositionsData, Order, SystemAlert, CycleStats,
} from "@/lib/types";

export default function Dashboard() {
  const {
    pnl, positions, opportunities, orders, alerts,
    killSwitchActive, cycleStats, systemStatus, wsConnected,
    setPositions, setPnl, setSystemStatus,
  } = useTradingStore();

  useEffect(() => {
    api.getPositions().then((d) => setPositions(d as PositionsData)).catch(() => {});
    api.getPnl().then((d) => setPnl(d as Parameters<typeof setPnl>[0])).catch(() => {});
    api.getSystemStatus().then((d) => setSystemStatus(d as Parameters<typeof setSystemStatus>[0])).catch(() => {});
  }, [setPositions, setPnl, setSystemStatus]);

  const totalCapital  = pnl?.total_capital  ?? 0;
  const dailyPnl      = pnl?.daily_pnl      ?? 0;
  const unrealizedPnl = pnl?.unrealized_pnl ?? 0;
  const realizedPnl   = pnl?.realized_pnl   ?? 0;
  const sharpe        = pnl?.sharpe_ratio;
  const totalNotional = positions?.total_notional ?? 0;
  const deployPct     = totalCapital > 0 ? (totalNotional / totalCapital) * 100 : 0;

  const recentFills = orders.filter((o) => o.state === "FILLED").slice(0, 8);

  return (
    <div className="h-full bg-bg-primary overflow-y-auto">
      {/* Kill switch banner */}
      {killSwitchActive && (
        <div className="mx-3 mt-3 flex items-center gap-3 bg-accent-red/10 border border-accent-red/60 px-3 py-2.5">
          <AlertTriangle className="w-4 h-4 text-accent-red flex-shrink-0" />
          <div className="flex-1">
            <span className="text-xs font-mono font-bold text-accent-red uppercase tracking-term">
              KILL SWITCH ACTIVE · ALL EXECUTION HALTED
            </span>
            {systemStatus?.kill_switch?.fire_reason && (
              <span className="text-2xs font-mono text-accent-red/80 ml-3">
                {systemStatus.kill_switch.fire_reason}
              </span>
            )}
          </div>
          <Link
            href="/strategy"
            className="text-2xs font-mono uppercase tracking-term text-accent-red hover:text-white border border-accent-red/50 px-2 py-1 rounded-[2px]"
          >
            MANAGE →
          </Link>
        </div>
      )}

      {/* Portfolio row */}
      <div className="grid grid-cols-5 gap-2 p-3">
        <StatCard
          label="TOTAL CAPITAL"
          value={`$${totalCapital.toLocaleString("en-US", { maximumFractionDigits: 0 })}`}
          hint="USDC"
          highlight="cyan"
        />
        <StatCard
          label="DAILY P&L"
          value={fmtMoney(dailyPnl)}
          delta={totalCapital > 0 ? (dailyPnl / totalCapital) * 100 : 0}
        />
        <StatCard
          label="UNREALIZED"
          value={fmtMoney(unrealizedPnl)}
          delta={totalCapital > 0 ? (unrealizedPnl / totalCapital) * 100 : 0}
        />
        <StatCard
          label="REALIZED"
          value={fmtMoney(realizedPnl)}
          hint="SESSION"
        />
        <StatCard
          label="SHARPE"
          value={sharpe != null ? sharpe.toFixed(2) : "—"}
          hint="TTM"
          highlight={sharpe != null && sharpe >= 1 ? "green" : "none"}
        />
      </div>

      {/* System health + deployment gauge */}
      <div className="grid grid-cols-12 gap-2 px-3">
        <div className="col-span-8">
          <Panel
            title="SYSTEM HEALTH"
            icon={<Activity className="w-3 h-3" />}
            flush
          >
            <div className="grid grid-cols-4 divide-x divide-border-primary">
              <HealthCell
                icon={<Radio className="w-3 h-3" />}
                label="DATA FEED"
                value={wsConnected ? "LIVE" : "OFFLINE"}
                detail={wsConnected ? "ws-subscription" : "reconnecting"}
                status={wsConnected ? "online" : "offline"}
              />
              <HealthCell
                icon={<Cpu className="w-3 h-3" />}
                label="EXECUTION"
                value={killSwitchActive ? "HALTED" : wsConnected ? "READY" : "IDLE"}
                detail={killSwitchActive ? "kill switch" : "order router"}
                status={killSwitchActive ? "offline" : wsConnected ? "online" : "idle"}
              />
              <HealthCell
                icon={<Shield className="w-3 h-3" />}
                label="RISK ENGINE"
                value={killSwitchActive ? "HALTED" : "MONITORING"}
                detail={`p99 ${(systemStatus?.kill_switch?.api_p99_ms ?? 0).toFixed(0)}ms`}
                status={killSwitchActive ? "offline" : "online"}
              />
              <HealthCell
                icon={<Zap className="w-3 h-3" />}
                label="KILL SWITCH"
                value={killSwitchActive ? "FIRED" : "ARMED"}
                detail={killSwitchActive ? "execution off" : "standby"}
                status={killSwitchActive ? "offline" : "online"}
              />
            </div>
          </Panel>
        </div>

        <div className="col-span-4">
          <Panel
            title="CAPITAL DEPLOYED"
            icon={<Gauge className="w-3 h-3" />}
            right={
              <span className="text-3xs font-mono text-text-dim uppercase tracking-term">
                {totalCapital > 0 ? `$${totalNotional.toFixed(0)} / $${totalCapital.toFixed(0)}` : "—"}
              </span>
            }
          >
            <div className="flex items-center gap-3 h-[42px]">
              <div className="flex-1 h-1.5 bg-bg-tertiary border border-border-primary relative overflow-hidden">
                <div
                  className={clsx(
                    "absolute inset-y-0 left-0 transition-all",
                    deployPct >= 80 ? "bg-accent-red" :
                    deployPct >= 50 ? "bg-accent-amber" :
                    "bg-accent-cyan",
                  )}
                  style={{ width: `${Math.min(deployPct, 100)}%` }}
                />
              </div>
              <span className={clsx(
                "text-lg font-mono font-medium tabular-nums",
                deployPct >= 80 ? "text-accent-red" :
                deployPct >= 50 ? "text-accent-amber" :
                "text-accent-cyan",
              )}>
                {deployPct.toFixed(1)}%
              </span>
            </div>
          </Panel>
        </div>
      </div>

      {/* Main 2-col content */}
      <div className="grid grid-cols-12 gap-2 p-3 pt-2">
        <div className="col-span-8 space-y-2">
          <OpportunitiesPanel
            opportunities={opportunities}
            cycleStats={cycleStats}
            killSwitchActive={killSwitchActive}
          />
          <PositionsSummaryPanel positions={positions} />
        </div>

        <div className="col-span-4 space-y-2">
          <RecentFillsPanel fills={recentFills} />
          <AlertsPanel alerts={alerts} />
        </div>
      </div>
    </div>
  );
}

/* ─── Health cell ──────────────────────────────────────────── */

function HealthCell({
  icon, label, value, detail, status,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
  detail: string;
  status: "online" | "offline" | "idle";
}) {
  const iconColor =
    status === "online"  ? "text-accent-green" :
    status === "offline" ? "text-accent-red"   :
    "text-text-dim";
  const valueColor =
    status === "online"  ? "text-accent-green" :
    status === "offline" ? "text-accent-red"   :
    "text-text-muted";

  return (
    <div className="flex items-center gap-2.5 px-3 py-2.5">
      <div className={clsx("flex items-center justify-center w-6 h-6 border border-border-primary bg-bg-tertiary", iconColor)}>
        {icon}
      </div>
      <div className="min-w-0">
        <div className="text-3xs font-mono text-text-dim uppercase tracking-term">{label}</div>
        <div className={clsx("text-xs font-mono font-medium mt-0.5", valueColor)}>{value}</div>
        <div className="text-3xs font-mono text-text-faint mt-0.5 truncate">{detail}</div>
      </div>
    </div>
  );
}

/* ─── Opportunities panel ──────────────────────────────────── */

type ExecState = "idle" | "loading" | "done" | "error";

function OpportunitiesPanel({
  opportunities, cycleStats, killSwitchActive,
}: {
  opportunities: Opportunity[];
  cycleStats: CycleStats | null;
  killSwitchActive: boolean;
}) {
  const [execState, setExecState] = useState<ExecState>("idle");
  const [execMsg, setExecMsg] = useState("");

  const handleExecute = useCallback(async () => {
    setExecState("loading");
    setExecMsg("");
    try {
      const res = await api.runStrategyNow();
      setExecState("done");
      setExecMsg(res.message);
    } catch (err: unknown) {
      setExecState("error");
      setExecMsg(err instanceof Error ? err.message : "Execution failed");
    } finally {
      // Reset button after 4 seconds
      setTimeout(() => { setExecState("idle"); setExecMsg(""); }, 4000);
    }
  }, []);

  return (
    <Panel
      title="ACTIVE OPPORTUNITIES"
      icon={<Target className="w-3 h-3" />}
      badge={
        opportunities.length > 0 ? (
          <Badge variant="amber" dot>
            {opportunities.length}
          </Badge>
        ) : null
      }
      right={
        <div className="flex items-center gap-2">
          {execMsg && (
            <span className={clsx(
              "text-3xs font-mono truncate max-w-[180px]",
              execState === "error" ? "text-accent-red" : "text-accent-green",
            )}>
              {execMsg}
            </span>
          )}
          <button
            onClick={handleExecute}
            disabled={execState === "loading" || killSwitchActive || opportunities.length === 0}
            title={killSwitchActive ? "Kill switch active" : opportunities.length === 0 ? "No opportunities" : "Execute all opportunities now"}
            className={clsx(
              "flex items-center gap-1.5 px-2.5 py-1 text-3xs font-mono uppercase tracking-term border transition-all",
              execState === "loading"
                ? "border-accent-amber/40 text-accent-amber bg-accent-amber/5 cursor-wait"
                : execState === "done"
                ? "border-accent-green/50 text-accent-green bg-accent-green/5"
                : execState === "error"
                ? "border-accent-red/50 text-accent-red bg-accent-red/5"
                : killSwitchActive || opportunities.length === 0
                ? "border-border-primary text-text-faint cursor-not-allowed opacity-50"
                : "border-accent-cyan/40 text-accent-cyan bg-accent-cyan/5 hover:bg-accent-cyan/10 hover:border-accent-cyan/60 cursor-pointer",
            )}
          >
            {execState === "loading" ? (
              <span className="w-3 h-3 border border-accent-amber/60 border-t-accent-amber rounded-full animate-spin" />
            ) : execState === "done" ? (
              <CheckCircle className="w-3 h-3" />
            ) : (
              <Play className="w-3 h-3" />
            )}
            {execState === "loading" ? "RUNNING" : execState === "done" ? "TRIGGERED" : "EXECUTE ALL"}
          </button>
          <Link href="/markets" className="text-3xs font-mono uppercase tracking-term text-text-dim hover:text-accent-cyan">
            VIEW ALL →
          </Link>
        </div>
      }
      flush
    >
      {opportunities.length === 0 ? (
        <div className="px-3 py-8 flex flex-col items-center gap-2">
          <div className="w-8 h-8 border border-border-primary bg-bg-tertiary flex items-center justify-center">
            <Target className="w-3.5 h-3.5 text-text-dim" />
          </div>
          <span className="text-2xs font-mono text-text-dim uppercase tracking-term">
            no opportunities this cycle
          </span>
          {cycleStats && (
            <span className="text-3xs font-mono text-text-faint">
              scanned {cycleStats.markets_scanned} · raw {cycleStats.raw_opportunities}
            </span>
          )}
        </div>
      ) : (
        <>
          <div className="grid grid-cols-[1fr_54px_70px_70px_80px_60px] gap-2 px-3 py-1.5 border-b border-border-primary text-3xs font-mono uppercase tracking-term text-text-dim">
            <span>MARKET</span>
            <span>SIDE</span>
            <span className="text-right">ENTRY</span>
            <span className="text-right">FAIR</span>
            <span className="text-right">NET EDGE</span>
            <span className="text-right">T−0</span>
          </div>
          <div className="divide-y divide-border-faint">
            {opportunities.slice(0, 7).map((opp) => (
              <div
                key={`${opp.market_id}-${opp.token_id}`}
                className="grid grid-cols-[1fr_54px_70px_70px_80px_60px] gap-2 items-center px-3 py-2 data-row"
              >
                <div className="min-w-0 flex items-center gap-2">
                  <span className="w-1 h-1 rounded-full bg-accent-amber dot-pulse-amber flex-shrink-0" />
                  <div className="min-w-0">
                    <div className="text-xs text-text-primary truncate">{opp.question}</div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      <Badge variant="outline" size="xs">{opp.category}</Badge>
                      <span className="text-3xs font-mono text-text-dim">
                        conf <span className="text-text-muted">{(opp.confidence * 100).toFixed(0)}%</span>
                      </span>
                    </div>
                  </div>
                </div>
                <Badge variant={opp.side === "YES" ? "green" : "red"} size="xs">
                  {opp.side}
                </Badge>
                <span className="text-right text-xs font-mono text-text-muted">
                  {opp.entry_price.toFixed(3)}
                </span>
                <span className="text-right text-xs font-mono text-text-muted">
                  {opp.fair_value.toFixed(3)}
                </span>
                <span className="text-right text-xs font-mono font-medium text-accent-green">
                  +{opp.net_edge_cents.toFixed(1)}¢
                </span>
                <div className="text-right">
                  <ResolutionCountdown hoursToResolution={opp.hours_to_resolution} />
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </Panel>
  );
}

/* ─── Positions summary ────────────────────────────────────── */

function PositionsSummaryPanel({ positions }: { positions: PositionsData | null }) {
  return (
    <Panel
      title="OPEN POSITIONS"
      icon={<TrendingUp className="w-3 h-3" />}
      badge={
        positions && positions.position_count > 0 ? (
          <Badge variant="cyan">{positions.position_count}</Badge>
        ) : null
      }
      right={
        <Link
          href="/positions"
          className="text-3xs font-mono uppercase tracking-term text-text-dim hover:text-accent-cyan"
        >
          MANAGE →
        </Link>
      }
      flush
    >
      {!positions || positions.positions.length === 0 ? (
        <div className="px-3 py-6 flex flex-col items-center gap-1">
          <span className="text-2xs font-mono text-text-dim uppercase tracking-term">
            no open positions
          </span>
          <span className="text-3xs font-mono text-text-faint">
            capital idle · awaiting signal
          </span>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-[1fr_54px_110px_80px_90px] gap-2 px-3 py-1.5 border-b border-border-primary text-3xs font-mono uppercase tracking-term text-text-dim">
            <span>MARKET</span>
            <span>SIDE</span>
            <span className="text-right">ENTRY → MARK</span>
            <span className="text-right">SIZE</span>
            <span className="text-right">UNR. P&L</span>
          </div>
          <div className="divide-y divide-border-faint">
            {positions.positions.slice(0, 5).map((pos) => {
              const pnlPct = pos.entry_price > 0
                ? ((pos.current_price - pos.entry_price) / pos.entry_price) * 100
                : 0;
              return (
                <div
                  key={pos.token_id}
                  className="grid grid-cols-[1fr_54px_110px_80px_90px] gap-2 items-center px-3 py-2 data-row"
                >
                  <div className="min-w-0 text-xs text-text-primary truncate">{pos.question}</div>
                  <Badge variant={pos.side === "YES" ? "green" : "red"} size="xs">
                    {pos.side}
                  </Badge>
                  <div className="text-right font-mono text-xs">
                    <span className="text-text-dim">{pos.entry_price.toFixed(3)}</span>
                    <span className="text-text-faint mx-1">→</span>
                    <span className={pnlPct >= 0 ? "text-accent-green" : "text-accent-red"}>
                      {pos.current_price.toFixed(3)}
                    </span>
                  </div>
                  <span className="text-right text-xs font-mono text-text-muted">
                    ${pos.size_usdc.toFixed(0)}
                  </span>
                  <div className="text-right">
                    <span className={clsx(
                      "text-xs font-mono font-medium",
                      pos.unrealized_pnl >= 0 ? "text-accent-green" : "text-accent-red",
                    )}>
                      {pos.unrealized_pnl >= 0 ? "+" : ""}${pos.unrealized_pnl.toFixed(2)}
                    </span>
                    <div className={clsx(
                      "text-3xs font-mono",
                      pnlPct >= 0 ? "text-accent-green/70" : "text-accent-red/70",
                    )}>
                      {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
          <div className="flex items-center justify-between px-3 py-2 border-t border-border-primary bg-bg-tertiary/50">
            <span className="text-3xs font-mono uppercase tracking-term text-text-dim">
              NOTIONAL · <span className="text-text-muted">${positions.total_notional.toFixed(0)}</span>
            </span>
            <span className={clsx(
              "text-3xs font-mono uppercase tracking-term font-medium",
              positions.unrealized_pnl >= 0 ? "text-accent-green" : "text-accent-red",
            )}>
              TOTAL UNREAL · {positions.unrealized_pnl >= 0 ? "+" : ""}${positions.unrealized_pnl.toFixed(2)}
            </span>
          </div>
        </>
      )}
    </Panel>
  );
}

/* ─── Recent fills ─────────────────────────────────────────── */

function RecentFillsPanel({ fills }: { fills: Order[] }) {
  return (
    <Panel
      title="RECENT FILLS"
      icon={<ArrowUpRight className="w-3 h-3" />}
      right={
        <Link
          href="/journal"
          className="text-3xs font-mono uppercase tracking-term text-text-dim hover:text-accent-cyan"
        >
          JOURNAL →
        </Link>
      }
      flush
    >
      {fills.length === 0 ? (
        <div className="px-3 py-6 text-center text-2xs font-mono text-text-dim uppercase tracking-term">
          no fills yet
        </div>
      ) : (
        <div className="divide-y divide-border-faint">
          {fills.map((fill) => (
            <div key={fill.local_id} className="px-3 py-2 flex items-start gap-2 data-row">
              <Badge variant={fill.outcome === "YES" ? "green" : "red"} size="xs">
                {fill.outcome}
              </Badge>
              <div className="flex-1 min-w-0">
                <div className="text-2xs text-text-primary truncate">{fill.question}</div>
                <div className="text-3xs font-mono text-text-dim mt-0.5 flex items-center gap-1">
                  <span>{fill.strategy}</span>
                  {fill.sim_mode && (
                    <span className="text-accent-purple">[SIM]</span>
                  )}
                </div>
              </div>
              <div className="text-right flex-shrink-0">
                <div className="text-xs font-mono text-text-primary">
                  {(fill.avg_fill_price ?? fill.price).toFixed(3)}
                </div>
                <div className="text-3xs font-mono text-text-dim">
                  ${fill.filled_size.toFixed(0)}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

/* ─── Alerts ───────────────────────────────────────────────── */

function AlertsPanel({ alerts }: { alerts: SystemAlert[] }) {
  const severityColor = {
    info:     "text-accent-cyan",
    warning:  "text-accent-amber",
    critical: "text-accent-red",
  };
  const severityDot = {
    info:     "bg-accent-cyan",
    warning:  "bg-accent-amber",
    critical: "bg-accent-red",
  };

  return (
    <Panel
      title="SYSTEM ALERTS"
      icon={<AlertTriangle className="w-3 h-3" />}
      badge={alerts.length > 0 ? <Badge variant="outline">{alerts.length}</Badge> : null}
      flush
    >
      {alerts.length === 0 ? (
        <div className="px-3 py-6 text-center text-2xs font-mono text-text-dim uppercase tracking-term">
          no alerts
        </div>
      ) : (
        <div className="divide-y divide-border-faint max-h-[220px] overflow-y-auto">
          {alerts.slice(0, 10).map((alert, i) => (
            <div key={i} className="px-3 py-2 flex items-start gap-2 data-row">
              <span className={clsx("w-1 h-1 rounded-full mt-1.5 flex-shrink-0", severityDot[alert.severity])} />
              <div className="flex-1 min-w-0">
                <div className={clsx("text-2xs font-mono leading-snug", severityColor[alert.severity])}>
                  {alert.message}
                </div>
                <div className="text-3xs font-mono text-text-faint mt-0.5 tabular-nums">
                  {new Date(alert.timestamp * 1000).toLocaleTimeString()}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </Panel>
  );
}

/* ─── Helpers ──────────────────────────────────────────────── */

function fmtMoney(n: number): string {
  if (n === 0) return "$0.00";
  return `${n >= 0 ? "+" : "-"}$${Math.abs(n).toFixed(2)}`;
}
