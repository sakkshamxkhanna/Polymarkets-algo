const BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) throw new Error(`API ${path} → ${res.status}`);
  return res.json();
}

export const api = {
  getMarkets: (limit = 50) => req<{ markets: unknown[]; total: number }>(`/api/markets?limit=${limit}`),
  getOrderbook: (tokenId: string) => req<unknown>(`/api/orderbook/${tokenId}`),
  getPositions: () => req<unknown>("/api/positions"),
  getPnl: () => req<unknown>("/api/pnl"),
  getTrades: (limit = 50) => req<{ trades: unknown[] }>(`/api/trades?limit=${limit}`),
  getSystemStatus: () => req<unknown>("/api/system/status"),
  getCalibration: () => req<unknown>("/api/calibration"),

  fireKillSwitch: () =>
    req("/api/system/kill-switch", { method: "POST", body: JSON.stringify({ action: "fire" }) }),
  resetKillSwitch: () =>
    req("/api/system/kill-switch", { method: "POST", body: JSON.stringify({ action: "reset" }) }),

  toggleStrategy: (name: string, enabled: boolean) =>
    req(`/api/strategy/${name}/toggle`, { method: "POST", body: JSON.stringify({ enabled }) }),

  setSimMode: (enabled: boolean) =>
    req("/api/system/sim-mode", { method: "POST", body: JSON.stringify({ enabled }) }),

  subscribeTokens: (tokenIds: string[]) =>
    req<{ subscribed: number }>("/api/subscribe", { method: "POST", body: JSON.stringify({ token_ids: tokenIds }) }),

  getPriceHistory: (tokenId: string, interval = "1d") =>
    req<{ history: { t: number; p: number }[] }>(`/api/history/${tokenId}?interval=${interval}`),

  submitManualOrder: (order: {
    token_id: string;
    market_id: string;
    question: string;
    outcome: "YES" | "NO";
    price: number;
    size_usdc: number;
  }) =>
    req<{ status: string; local_id: string; order: unknown }>(
      "/api/orders/manual",
      { method: "POST", body: JSON.stringify(order) },
    ),

  runStrategyNow: () =>
    req<{ status: string; message: string }>(
      "/api/strategy/run-now",
      { method: "POST" },
    ),

  closeAllPositions: () =>
    req<{ closed: number; realized_pnl: number }>(
      "/api/positions/close-all",
      { method: "POST" },
    ),
};
