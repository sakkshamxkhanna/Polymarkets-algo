"use client";
import { useEffect, useState } from "react";
import { clsx } from "clsx";

interface Props {
  hoursToResolution: number;
  className?: string;
}

function formatHours(hours: number): string {
  if (hours <= 0) return "RESOLVED";
  if (hours < 1) return `${Math.floor(hours * 60)}m`;
  if (hours < 24) {
    const h = Math.floor(hours);
    const m = Math.floor((hours - h) * 60);
    return `${h}h ${m.toString().padStart(2, "0")}m`;
  }
  return `${Math.floor(hours / 24)}d ${Math.floor(hours % 24)}h`;
}

export function ResolutionCountdown({ hoursToResolution, className }: Props) {
  const [hours, setHours] = useState(hoursToResolution);

  useEffect(() => {
    setHours(hoursToResolution);
    const interval = setInterval(() => {
      setHours((h) => Math.max(0, h - 1 / 3600));
    }, 1000);
    return () => clearInterval(interval);
  }, [hoursToResolution]);

  const isUrgent = hours < 2 && hours > 0;
  const isNear   = hours < 6 && hours >= 2;

  return (
    <span
      className={clsx(
        "font-mono text-xs tracking-tight",
        hours <= 0 && "text-accent-green",
        isUrgent  && "text-accent-red",
        isNear    && "text-accent-amber",
        !isNear && !isUrgent && hours > 0 && "text-text-muted",
        className,
      )}
    >
      {formatHours(hours)}
    </span>
  );
}
