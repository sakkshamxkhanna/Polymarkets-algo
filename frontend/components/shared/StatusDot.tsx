"use client";
import { clsx } from "clsx";

type Status = "online" | "offline" | "warning" | "idle";

interface Props {
  status: Status;
  label?: string;
  size?: "sm" | "md";
  pulse?: boolean;
}

const dotBg: Record<Status, string> = {
  online:  "bg-accent-green",
  offline: "bg-accent-red",
  warning: "bg-accent-amber",
  idle:    "bg-text-dim",
};

const pulseClass: Record<Status, string> = {
  online:  "dot-pulse-green",
  offline: "dot-pulse-red",
  warning: "dot-pulse-amber",
  idle:    "",
};

const labelColor: Record<Status, string> = {
  online:  "text-accent-green",
  offline: "text-accent-red",
  warning: "text-accent-amber",
  idle:    "text-text-muted",
};

export function StatusDot({ status, label, size = "md", pulse = true }: Props) {
  const dotSize = size === "sm" ? "w-1.5 h-1.5" : "w-2 h-2";
  return (
    <div className="inline-flex items-center gap-2">
      <span
        className={clsx(
          "rounded-full",
          dotSize,
          dotBg[status],
          pulse && pulseClass[status],
        )}
      />
      {label && (
        <span className={clsx("text-2xs font-mono uppercase tracking-term", labelColor[status])}>
          {label}
        </span>
      )}
    </div>
  );
}
