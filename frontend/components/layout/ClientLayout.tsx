"use client";
import { useWebSocket } from "@/hooks/useWebSocket";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";
import { CommandFooter } from "./CommandFooter";

export function ClientLayout({ children }: { children: React.ReactNode }) {
  useWebSocket();

  return (
    <div className="flex h-full w-full overflow-hidden bg-bg-primary">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopBar />
        <main className="flex-1 min-h-0 overflow-y-auto overflow-x-hidden bg-bg-primary">
          {children}
        </main>
        <CommandFooter />
      </div>
    </div>
  );
}
