"use client";
import { clsx } from "clsx";
import type { ReactNode } from "react";

type Variant = "cyan" | "amber" | "green" | "red" | "yellow" | "muted" | "purple" | "outline";

interface Props {
  children: ReactNode;
  variant?: Variant;
  size?: "xs" | "sm";
  className?: string;
  dot?: boolean;
}

const variants: Record<Variant, string> = {
  cyan:    "bg-accent-cyan/10  text-accent-cyan  border-accent-cyan/35",
  amber:   "bg-accent-amber/10 text-accent-amber border-accent-amber/35",
  green:   "bg-accent-green/10 text-accent-green border-accent-green/35",
  red:     "bg-accent-red/10   text-accent-red   border-accent-red/35",
  yellow:  "bg-accent-yellow/10 text-accent-yellow border-accent-yellow/35",
  muted:   "bg-bg-tertiary     text-text-muted   border-border-primary",
  purple:  "bg-accent-purple/10 text-accent-purple border-accent-purple/35",
  outline: "bg-transparent     text-text-muted   border-border-strong",
};

const dotColors: Record<Variant, string> = {
  cyan:    "bg-accent-cyan",
  amber:   "bg-accent-amber",
  green:   "bg-accent-green",
  red:     "bg-accent-red",
  yellow:  "bg-accent-yellow",
  muted:   "bg-text-dim",
  purple:  "bg-accent-purple",
  outline: "bg-text-dim",
};

export function Badge({ children, variant = "muted", size = "sm", className, dot }: Props) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 border font-mono font-medium uppercase tracking-term",
        size === "xs" ? "text-3xs px-1.5 h-[14px]" : "text-2xs px-1.5 h-[16px]",
        "rounded-[2px]",
        variants[variant],
        className,
      )}
    >
      {dot && <span className={clsx("w-1 h-1 rounded-full", dotColors[variant])} />}
      {children}
    </span>
  );
}
