"use client";
import { create } from "zustand";
import type {
  Market, Orderbook, Position, PositionsData, Order,
  Opportunity, PnLSnapshot, SystemAlert, SystemStatus, CycleStats,
} from "./types";

interface TradingStore {
  // Connection
  wsConnected: boolean;
  wsLatencyMs: number;
  setWsConnected: (v: boolean) => void;
  setWsLatency: (ms: number) => void;

  // Markets
  markets: Market[];
  setMarkets: (m: Market[]) => void;

  // Orderbooks
  orderbooks: Record<string, Orderbook>;
  updateOrderbook: (ob: Orderbook) => void;

  // Positions & P&L
  positions: PositionsData | null;
  setPositions: (p: PositionsData) => void;

  pnl: PnLSnapshot | null;
  setPnl: (p: PnLSnapshot) => void;

  // Orders
  orders: Order[];
  setOrders: (o: Order[]) => void;

  // Opportunities (resolution timing alerts)
  opportunities: Opportunity[];
  setOpportunities: (o: Opportunity[]) => void;

  // Alerts
  alerts: SystemAlert[];
  addAlert: (a: SystemAlert) => void;
  clearAlerts: () => void;

  // System status
  systemStatus: SystemStatus | null;
  setSystemStatus: (s: SystemStatus) => void;

  // Kill switch
  killSwitchActive: boolean;
  setKillSwitchActive: (v: boolean) => void;

  // Sim mode
  simMode: boolean;
  setSimMode: (v: boolean) => void;

  // Cycle stats
  cycleStats: CycleStats | null;
  setCycleStats: (s: CycleStats) => void;

  // Handle incoming WS message
  handleWsMessage: (msg: Record<string, unknown>) => void;
}

export const useTradingStore = create<TradingStore>((set, get) => ({
  wsConnected: false,
  wsLatencyMs: 0,
  setWsConnected: (v) => set({ wsConnected: v }),
  setWsLatency: (ms) => set({ wsLatencyMs: ms }),

  markets: [],
  setMarkets: (m) => set({ markets: m }),

  orderbooks: {},
  updateOrderbook: (ob) =>
    set((s) => ({ orderbooks: { ...s.orderbooks, [ob.token_id]: ob } })),

  positions: null,
  setPositions: (p) => set({ positions: p }),

  pnl: null,
  setPnl: (p) => set({ pnl: p }),

  orders: [],
  setOrders: (o) => set({ orders: o }),

  opportunities: [],
  setOpportunities: (o) => set({ opportunities: o }),

  alerts: [],
  addAlert: (a) =>
    set((s) => ({ alerts: [a, ...s.alerts].slice(0, 50) })),
  clearAlerts: () => set({ alerts: [] }),

  systemStatus: null,
  setSystemStatus: (s) => set({ systemStatus: s }),

  killSwitchActive: false,
  setKillSwitchActive: (v) => set({ killSwitchActive: v }),

  simMode: true,
  setSimMode: (v) => set({ simMode: v }),

  cycleStats: null,
  setCycleStats: (s) => set({ cycleStats: s }),

  handleWsMessage: (msg) => {
    const { type } = msg as { type: string };
    const store = get();

    if (type === "cycle_update") {
      const m = msg as Record<string, unknown>;
      if (m.positions) store.setPositions(m.positions as PositionsData);
      if (m.pnl) store.setPnl(m.pnl as PnLSnapshot);
      if (m.opportunities) store.setOpportunities(m.opportunities as Opportunity[]);
      if (m.markets) store.setMarkets(m.markets as Market[]);
      if (m.stats) store.setCycleStats(m.stats as CycleStats);
      if (m.kill_switch !== undefined) store.setKillSwitchActive(m.kill_switch as boolean);
      if (Array.isArray(m.alerts)) {
        (m.alerts as SystemAlert[]).forEach((a) => store.addAlert(a));
      }
    } else if (type === "kill_switch") {
      store.setKillSwitchActive(true);
      if (msg.alert) store.addAlert(msg.alert as SystemAlert);
    } else if (type === "system_alert") {
      store.addAlert({
        type: "SYSTEM",
        message: (msg.message as string) || "",
        severity: (msg.severity as SystemAlert["severity"]) || "info",
        timestamp: Date.now() / 1000,
      });
    }
  },
}));
