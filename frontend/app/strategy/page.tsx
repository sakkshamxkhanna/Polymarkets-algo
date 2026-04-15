"use client";
import { useEffect, useState } from "react";
import { useTradingStore } from "@/lib/store";
import { api } from "@/lib/api";
import { Badge } from "@/components/shared/Badge";
import { clsx } from "clsx";
import {
  AlertTriangle, Shield, Settings, Zap, Power, RefreshCw, CheckCircle,
} from "lucide-react";
import type { SystemStatus } from "@/lib/types";

export default function StrategyPage() {
  const { killSwitchActive, setKillSwitchActive, simMode, setSimMode, systemStatus, setSystemStatus } = useTradingStore();
  const [confirmKill, setConfirmKill] = useState(false);
  const [confirmLive, setConfirmLive] = useState(false);
  const [loading, setLoading] = useState<string | null>(null);

  useEffect(() => {
    api.getSystemStatus().then((d) => setSystemStatus(d as SystemStatus)).catch(() => {});
  }, [setSystemStatus]);

  async function handleKillSwitch(action: "fire" | "reset") {
    setLoading(action);
    try {
      if (action === "fire") {
        await api.fireKillSwitch();
        setKillSwitchActive(true);
        setConfirmKill(false);
      } else {
        await api.resetKillSwitch();
        setKillSwitchActive(false);
      }
      const d = await api.getSystemStatus();
      setSystemStatus(d as SystemStatus);
    } catch (_e) { /* ignore */ } finally { setLoading(null); }
  }

  async function handleSimToggle(enabled: boolean) {
    if (!enabled && !confirmLive) { setConfirmLive(true); return; }
    setLoading("sim"); setConfirmLive(false);
    try { await api.setSimMode(enabled); setSimMode(enabled); }
    catch (_e) { /* ignore */ } finally { setLoading(null); }
  }

  async function handleStrategyToggle(name: string, enabled: boolean) {
    setLoading(name);
    try {
      await api.toggleStrategy(name, enabled);
      const d = await api.getSystemStatus();
      setSystemStatus(d as SystemStatus);
    } catch (_e) { /* ignore */ } finally { setLoading(null); }
  }

  const strategies = [{
    name: "resolution_timing",
    label: "Resolution Timing",
    description: "Buy winning shares before UMA oracle confirms. Targets markets within 6h of resolution with ≥6¢ net edge.",
    enabled: systemStatus?.strategy_enabled?.["resolution_timing"] ?? false,
  }];

  const ks = systemStatus?.kill_switch;

  return (
    <div className="h-full overflow-y-auto bg-bg-primary">
      <div className="p-3 space-y-2">

        {/* Kill Switch */}
        <div className={clsx(
          "term-panel",
          killSwitchActive && "border-accent-red bg-accent-red/5",
        )}>
          <div className="term-panel-header justify-between">
            <div className="flex items-center gap-2">
              <AlertTriangle className={clsx("w-3 h-3", killSwitchActive ? "text-accent-red" : "text-text-muted")} />
              <span className={clsx("term-label", killSwitchActive && "text-accent-red")}>Kill Switch</span>
            </div>
            <Badge variant={killSwitchActive ? "red" : "muted"} dot={killSwitchActive}>
              {killSwitchActive ? "ACTIVE" : "STANDBY"}
            </Badge>
          </div>

          <div className="p-3 space-y-3">
            {ks && (
              <div className="grid grid-cols-3 divide-x divide-border-primary border border-border-primary">
                <Cell label="API P99" value={`${ks.api_p99_ms.toFixed(0)}ms`} warn={ks.api_p99_ms > 500} />
                <Cell label="Fired At" value={ks.fired_at ? new Date(ks.fired_at * 1000).toLocaleTimeString() : "—"} />
                <Cell label="Reason" value={ks.fire_reason ?? "—"} />
              </div>
            )}

            {ks && ks.history.length > 0 && (
              <div>
                <div className="text-3xs font-mono text-text-dim uppercase tracking-term mb-1">Recent Events</div>
                <div className="space-y-0.5">
                  {ks.history.slice(0, 5).map((ev, i) => (
                    <div key={i} className="flex items-center gap-2 text-2xs font-mono">
                      <span className="text-text-dim tabular-nums">{new Date(ev.timestamp * 1000).toLocaleTimeString()}</span>
                      <span className="text-accent-red">{ev.reason}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-center gap-2">
              {killSwitchActive ? (
                <button
                  onClick={() => handleKillSwitch("reset")}
                  disabled={loading === "reset"}
                  className="term-btn term-btn-active border-accent-green/50 text-accent-green"
                >
                  <RefreshCw className={clsx("w-3 h-3", loading === "reset" && "animate-spin")} />
                  {loading === "reset" ? "RESETTING…" : "RESET KILL SWITCH"}
                </button>
              ) : confirmKill ? (
                <div className="flex items-center gap-2">
                  <span className="text-2xs font-mono text-accent-red">Confirm fire?</span>
                  <button
                    onClick={() => handleKillSwitch("fire")}
                    disabled={loading === "fire"}
                    className="term-btn border-accent-red text-accent-red bg-accent-red/10"
                  >
                    {loading === "fire" ? "FIRING…" : "YES, FIRE"}
                  </button>
                  <button onClick={() => setConfirmKill(false)} className="term-btn">CANCEL</button>
                </div>
              ) : (
                <button onClick={() => setConfirmKill(true)} className="term-btn border-accent-red/40 text-accent-red">
                  <AlertTriangle className="w-3 h-3" />
                  FIRE KILL SWITCH
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Sim / Live mode */}
        <div className="term-panel">
          <div className="term-panel-header justify-between">
            <div className="flex items-center gap-2">
              <Shield className="w-3 h-3 text-accent-purple" />
              <span className="term-label">Trading Mode</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={simMode ? "purple" : "red"} dot>{simMode ? "SIMULATION" : "LIVE"}</Badge>
              <button
                onClick={() => handleSimToggle(!simMode)}
                disabled={loading === "sim"}
                className={clsx(
                  "term-btn",
                  simMode ? "border-accent-red/40 text-accent-red" : "border-accent-green/40 text-accent-green",
                )}
              >
                {loading === "sim" ? "SWITCHING…" : simMode ? "SWITCH TO LIVE" : "SWITCH TO SIM"}
              </button>
            </div>
          </div>

          {confirmLive && (
            <div className="mx-3 mb-3 p-3 bg-accent-red/8 border border-accent-red/40">
              <p className="text-2xs font-mono text-accent-red mb-2">
                LIVE MODE will submit real orders to Polymarket CLOB using your API keys.
                Ensure you have tested thoroughly in simulation first.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={() => { setConfirmLive(false); handleSimToggle(false); }}
                  className="term-btn border-accent-red text-accent-red bg-accent-red/10"
                >
                  I UNDERSTAND — GO LIVE
                </button>
                <button onClick={() => setConfirmLive(false)} className="term-btn">CANCEL</button>
              </div>
            </div>
          )}
        </div>

        {/* Strategies */}
        <div className="term-panel">
          <div className="term-panel-header">
            <Settings className="w-3 h-3 text-text-dim" />
            <span className="term-label">Strategies</span>
          </div>
          <div className="divide-y divide-border-faint">
            {strategies.map((s) => (
              <div key={s.name} className={clsx("p-3 flex items-start justify-between gap-3", s.enabled && "bg-accent-cyan/3")}>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-mono font-medium text-text-primary">{s.label}</span>
                    <Badge variant={s.enabled ? "cyan" : "muted"} size="xs">{s.enabled ? "ENABLED" : "DISABLED"}</Badge>
                  </div>
                  <p className="text-2xs font-mono text-text-dim">{s.description}</p>
                  {systemStatus?.last_cycle && s.enabled && (
                    <div className="mt-2 flex gap-4 text-3xs font-mono text-text-dim">
                      <span>scanned <span className="text-text-muted tabular-nums">{(systemStatus.last_cycle as Record<string, number>).markets_scanned ?? 0}</span></span>
                      <span>opp <span className="text-text-muted tabular-nums">{(systemStatus.last_cycle as Record<string, number>).verified_opportunities ?? 0}</span></span>
                    </div>
                  )}
                </div>
                <button
                  onClick={() => handleStrategyToggle(s.name, !s.enabled)}
                  disabled={loading === s.name}
                  className={clsx(
                    "term-btn flex-shrink-0",
                    s.enabled ? "border-accent-red/40 text-accent-red" : "border-accent-green/40 text-accent-green",
                  )}
                >
                  {loading === s.name ? <RefreshCw className="w-3 h-3 animate-spin" /> : s.enabled ? <Power className="w-3 h-3" /> : <CheckCircle className="w-3 h-3" />}
                  {loading === s.name ? "…" : s.enabled ? "DISABLE" : "ENABLE"}
                </button>
              </div>
            ))}
          </div>
        </div>

        {/* Risk Parameters */}
        <div className="term-panel">
          <div className="term-panel-header">
            <Zap className="w-3 h-3 text-accent-amber" />
            <span className="term-label">Risk Parameters</span>
            <span className="ml-auto text-3xs font-mono text-text-faint">configured in .env</span>
          </div>
          <div className="p-3 grid grid-cols-2 gap-0 divide-border-primary">
            {[
              ["Daily Drawdown Limit",        "8%",     "Hard stop on daily P&L loss"],
              ["Max Position Size",           "3%",     "% of total capital per position"],
              ["Min Edge Threshold",          "6¢",     "Minimum net edge to enter"],
              ["Kelly Fraction",              "25%",    "Fraction of full Kelly sizing"],
              ["Oracle Risk Buffer (A)",      "0.5%",   "Sports, official govt data"],
              ["Oracle Risk Buffer (other)",  "2.0%",   "All other markets"],
              ["API Latency Threshold",       "500ms",  "Kill switch trigger"],
              ["WS Gap Threshold",            "10s",    "Kill switch trigger"],
            ].map(([label, value, detail]) => (
              <div key={label} className="flex items-center justify-between px-3 py-2 border-b border-border-faint last:border-0">
                <div>
                  <div className="text-3xs font-mono text-text-dim uppercase tracking-term">{label}</div>
                  <div className="text-3xs font-mono text-text-faint">{detail}</div>
                </div>
                <span className="text-xs font-mono font-medium text-accent-cyan tabular-nums">{value}</span>
              </div>
            ))}
          </div>
        </div>

        {/* System Status */}
        {systemStatus && (
          <div className="term-panel">
            <div className="term-panel-header">
              <span className="term-label">System Status</span>
            </div>
            <div className="grid grid-cols-2 divide-x divide-border-primary border-t border-border-primary">
              <Cell label="Active Orders"   value={systemStatus.active_orders.toString()} />
              <Cell label="Orphaned Orders" value={systemStatus.orphaned_orders.toString()} warn={systemStatus.orphaned_orders > 0} />
              <Cell label="WS Clients"      value={systemStatus.ws_clients.toString()} />
              <Cell label="WS Gap"          value={`${systemStatus.ws_gap_seconds.toFixed(1)}s`} warn={systemStatus.ws_gap_seconds > 5} />
            </div>
          </div>
        )}

      </div>
    </div>
  );
}

function Cell({ label, value, warn = false }: { label: string; value: string; warn?: boolean }) {
  return (
    <div className="px-3 py-2 border-b border-border-faint">
      <div className="text-3xs font-mono text-text-dim uppercase tracking-term mb-0.5">{label}</div>
      <span className={clsx("text-xs font-mono tabular-nums", warn ? "text-accent-amber" : "text-text-muted")}>{value}</span>
    </div>
  );
}
