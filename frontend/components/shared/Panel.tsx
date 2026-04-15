"use client";
import { clsx } from "clsx";
import type { ReactNode } from "react";

interface Props {
  title?: string;
  subtitle?: string;
  icon?: ReactNode;
  right?: ReactNode;
  badge?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClassName?: string;
  flush?: boolean;       // remove body padding
  scroll?: boolean;
}

/**
 * Terminal-style panel with hairline border, sharp corners, and a header strip.
 * The signature primitive of the dashboard.
 */
export function Panel({
  title, subtitle, icon, right, badge, children, className, bodyClassName, flush, scroll,
}: Props) {
  return (
    <section className={clsx("term-panel flex flex-col min-h-0", className)}>
      {(title || right) && (
        <header className="term-panel-header flex-shrink-0">
          {icon && <span className="text-text-dim flex items-center">{icon}</span>}
          {title && (
            <span className="term-label text-text-secondary">{title}</span>
          )}
          {subtitle && (
            <span className="text-2xs font-mono text-text-dim ml-1">{subtitle}</span>
          )}
          {badge}
          {right && <div className="ml-auto flex items-center gap-2">{right}</div>}
        </header>
      )}
      <div
        className={clsx(
          "flex-1 min-h-0",
          !flush && "p-3",
          scroll && "overflow-y-auto",
          bodyClassName,
        )}
      >
        {children}
      </div>
    </section>
  );
}
