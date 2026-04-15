"use client";
import { clsx } from "clsx";
import type { ReactNode } from "react";

interface Props {
  label: string;
  value: string | number;
  delta?: number;
  prefix?: string;
  suffix?: string;
  hint?: string;
  highlight?: "cyan" | "amber" | "green" | "red" | "none";
  size?: "sm" | "md";
  trailing?: ReactNode;   // small inline meta on the right of value
}

export function StatCard({
  label, value, delta, prefix, suffix, hint,
  highlight = "none", size = "md", trailing,
}: Props) {
  const isPositive = delta !== undefined && delta > 0;
  const isNegative = delta !== undefined && delta < 0;

  const valueColor =
    isPositive ? "text-accent-green" :
    isNegative ? "text-accent-red"   :
    highlight === "cyan"  ? "text-accent-cyan"  :
    highlight === "amber" ? "text-accent-amber" :
    "text-text-primary";

  const accentBar =
    highlight === "cyan"  ? "before:bg-accent-cyan" :
    highlight === "amber" ? "before:bg-accent-amber" :
    highlight === "green" ? "before:bg-accent-green" :
    highlight === "red"   ? "before:bg-accent-red"   :
    "before:bg-border-strong";

  return (
    <div
      className={clsx(
        "relative bg-bg-secondary border border-border-primary px-3 py-2.5",
        "before:absolute before:left-0 before:top-0 before:bottom-0 before:w-[2px]",
        accentBar,
      )}
    >
      <div className="flex items-center justify-between mb-1">
        <span className="term-label text-text-dim">{label}</span>
        {hint && (
          <span className="text-3xs font-mono text-text-faint uppercase tracking-term">
            {hint}
          </span>
        )}
      </div>
      <div className="flex items-baseline gap-1.5">
        {prefix && (
          <span className="text-text-dim text-xs font-mono">{prefix}</span>
        )}
        <span
          className={clsx(
            "font-mono font-medium tracking-tight",
            size === "sm" ? "text-base" : "text-xl",
            valueColor,
          )}
        >
          {value}
        </span>
        {suffix && (
          <span className="text-text-dim text-xs font-mono">{suffix}</span>
        )}
        {trailing && <span className="ml-auto">{trailing}</span>}
      </div>
      {delta !== undefined && (
        <div
          className={clsx(
            "mt-0.5 text-2xs font-mono flex items-center gap-1",
            isPositive ? "text-accent-green" : isNegative ? "text-accent-red" : "text-text-dim",
          )}
        >
          <span>{isPositive ? "▲" : isNegative ? "▼" : "—"}</span>
          <span>{Math.abs(delta).toFixed(2)}%</span>
        </div>
      )}
    </div>
  );
}
