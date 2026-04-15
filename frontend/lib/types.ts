export interface Market {
  condition_id: string;
  question: string;
  end_date: string;
  volume_usd: number;
  yes_token_id: string;
  no_token_id: string;
  category: string;
  is_active: boolean;
  hours_to_resolution: number;
  mid_price: number;
  spread_cents: number;
}

export interface PriceLevel {
  price: number;
  size: number;
}

export interface Orderbook {
  token_id: string;
  best_bid: number | null;
  best_ask: number | null;
  mid_price: number | null;
  spread_cents: number | null;
  bids: PriceLevel[];
  asks: PriceLevel[];
  timestamp: number;
}

export interface Position {
  token_id: string;
  market_id: string;
  question: string;
  side: "YES" | "NO";
  entry_price: number;
  current_price: number;
  size_usdc: number;
  unrealized_pnl: number;
  strategy: string;
  opened_at: string;
}

export interface PositionsData {
  total_capital: number;
  total_notional: number;
  unrealized_pnl: number;
  realized_pnl: number;
  daily_pnl: number;
  position_count: number;
  positions: Position[];
}

export interface Order {
  local_id: string;
  clob_id: string | null;
  token_id: string;
  market_id: string;
  question: string;
  side: string;
  outcome: string;
  price: number;
  size: number;
  state: string;
  filled_size: number;
  avg_fill_price: number | null;
  strategy: string;
  sim_mode: boolean;
  created_at: number;
}

export interface Opportunity {
  market_id: string;
  question: string;
  token_id: string;
  side: "YES" | "NO";
  entry_price: number;
  fair_value: number;
  gross_edge_cents: number;
  net_edge_cents: number;
  hours_to_resolution: number;
  confidence: number;
  category: string;
  sources: string[];
}

export interface PnLSnapshot {
  total_capital: number;
  total_notional: number;
  unrealized_pnl: number;
  realized_pnl: number;
  daily_pnl: number;
  position_count: number;
  sharpe_ratio?: number;
}

export interface SystemAlert {
  type: string;
  message: string;
  severity: "info" | "warning" | "critical";
  timestamp: number;
}

export interface SystemStatus {
  sim_mode: boolean;
  kill_switch: {
    active: boolean;
    fired_at: number | null;
    fire_reason: string | null;
    api_p99_ms: number;
    history: Array<{ timestamp: number; reason: string }>;
  };
  ws_connected: boolean;
  ws_gap_seconds: number;
  ws_clients: number;
  active_orders: number;
  orphaned_orders: number;
  strategy_enabled: Record<string, boolean>;
  last_cycle: Record<string, unknown> | null;
}

export interface CycleStats {
  markets_scanned: number;
  raw_opportunities: number;
  verified_opportunities: number;
  orders_submitted: number;
  cycle_id: string;
  timestamp: number;
}

export interface WsMessage {
  type: string;
  [key: string]: unknown;
}
