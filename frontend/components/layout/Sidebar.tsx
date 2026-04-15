"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import {
  LayoutDashboard, TrendingUp, Wallet,
  ScrollText, Settings,
} from "lucide-react";
import { useTradingStore } from "@/lib/store";

const NAV = [
  { href: "/",         label: "Dashboard", short: "DASH",  key: "F1", icon: LayoutDashboard },
  { href: "/markets",  label: "Markets",   short: "MKTS",  key: "F2", icon: TrendingUp },
  { href: "/positions",label: "Positions", short: "POS",   key: "F3", icon: Wallet },
  { href: "/journal",  label: "Journal",   short: "JRNL",  key: "F4", icon: ScrollText },
  { href: "/strategy", label: "Strategy",  short: "STRAT", key: "F5", icon: Settings },
];

export function Sidebar() {
  const pathname = usePathname();
  const { opportunities, killSwitchActive } = useTradingStore();

  return (
    <aside className="w-[60px] flex-shrink-0 flex flex-col h-full bg-bg-secondary border-r border-border-primary">
      {/* Logo block */}
      <div className="h-[56px] flex flex-col items-center justify-center border-b border-border-primary">
        <div className="relative w-7 h-7 flex items-center justify-center">
          <div
            className={clsx(
              "absolute inset-0 border rounded-[2px]",
              killSwitchActive
                ? "border-accent-red bg-accent-red/10"
                : "border-accent-cyan/60 bg-accent-cyan/5",
            )}
          />
          <span
            className={clsx(
              "relative text-[11px] font-display font-bold tracking-tight",
              killSwitchActive ? "text-accent-red" : "text-accent-cyan",
            )}
          >
            PT
          </span>
        </div>
        <span className="text-3xs font-mono text-text-dim mt-1 uppercase tracking-term">
          v0.1
        </span>
      </div>

      {/* Nav rail */}
      <nav className="flex-1 flex flex-col items-stretch py-2">
        {NAV.map(({ href, label, short, key, icon: Icon }) => {
          const active = pathname === href || (href !== "/" && pathname.startsWith(href));
          const showBadge = label === "Markets" && opportunities.length > 0;

          return (
            <Link
              key={href}
              href={href}
              className={clsx(
                "group relative flex flex-col items-center justify-center gap-0.5 mx-1 my-0.5 py-2.5",
                "transition-colors duration-100",
                active
                  ? "bg-accent-cyan/8 text-accent-cyan"
                  : "text-text-dim hover:bg-bg-elevated hover:text-text-primary",
              )}
            >
              {/* Active indicator bar (left edge) */}
              {active && (
                <span className="absolute left-0 top-0 bottom-0 w-[2px] bg-accent-cyan" />
              )}

              <Icon className={clsx("w-4 h-4", active && "text-accent-cyan")} />
              <span
                className={clsx(
                  "text-3xs font-mono uppercase tracking-term",
                  active ? "text-accent-cyan" : "text-text-dim group-hover:text-text-muted",
                )}
              >
                {short}
              </span>

              {/* Tooltip on hover — rises to the right */}
              <span className="pointer-events-none absolute left-full top-1/2 -translate-y-1/2 ml-2 z-50 opacity-0 group-hover:opacity-100 transition-opacity duration-100 whitespace-nowrap">
                <span className="flex items-center gap-2 bg-bg-elevated border border-border-strong rounded-[2px] px-2.5 py-1 shadow-panel">
                  <span className="text-xs text-text-primary">{label}</span>
                  <span className="fkey">{key}</span>
                </span>
              </span>

              {/* Notification badge */}
              {showBadge && (
                <span className="absolute top-1 right-1 min-w-[14px] h-[14px] px-1 flex items-center justify-center bg-accent-amber text-bg-primary text-3xs font-mono font-bold rounded-[2px]">
                  {opportunities.length}
                </span>
              )}
            </Link>
          );
        })}
      </nav>

      {/* Sidebar footer: status indicator */}
      <div className="border-t border-border-primary p-2 flex flex-col items-center gap-1.5">
        <div
          className={clsx(
            "w-5 h-5 flex items-center justify-center border rounded-[2px]",
            killSwitchActive
              ? "border-accent-red/60 bg-accent-red/10"
              : "border-border-strong bg-bg-tertiary",
          )}
        >
          <span
            className={clsx(
              "text-3xs font-mono font-bold",
              killSwitchActive ? "text-accent-red" : "text-text-dim",
            )}
          >
            KS
          </span>
        </div>
        <span className="text-3xs font-mono text-text-faint uppercase tracking-term">
          {killSwitchActive ? "FIRED" : "ARM"}
        </span>
      </div>
    </aside>
  );
}
