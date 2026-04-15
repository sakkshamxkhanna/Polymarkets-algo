"use client";
import { useEffect, useRef, useCallback } from "react";
import { useTradingStore } from "@/lib/store";

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000/ws";

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const backoffRef = useRef(1000);
  const { setWsConnected, setWsLatency, handleWsMessage } = useTradingStore();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setWsConnected(true);
      backoffRef.current = 1000;
    };

    ws.onclose = () => {
      setWsConnected(false);
      // Exponential backoff reconnect
      const delay = backoffRef.current;
      backoffRef.current = Math.min(delay * 2, 30_000);
      reconnectTimer.current = setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (event) => {
      const recv = Date.now();
      try {
        const msg = JSON.parse(event.data);
        // Rough latency estimate from timestamp in message
        if (msg.stats?.timestamp) {
          setWsLatency(recv - msg.stats.timestamp * 1000);
        }
        handleWsMessage(msg);
      } catch {
        // Ignore parse errors
      }
    };
  }, [setWsConnected, setWsLatency, handleWsMessage]);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);
}
