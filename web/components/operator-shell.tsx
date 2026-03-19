import type { ReactNode } from "react";
import { Activity, AreaChart, Bot, ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";

type OperatorShellProps = {
  children: ReactNode;
};

const navItems = [
  { label: "Overview", icon: AreaChart, state: "Live now" },
  { label: "Runtime", icon: Activity, state: "Next slice" },
  { label: "Controls", icon: ShieldCheck, state: "Planned" },
];

export function OperatorShell({ children }: OperatorShellProps) {
  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(56,189,248,0.14),_transparent_24%),linear-gradient(180deg,_#071019_0%,_#02060a_100%)] text-white">
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col px-4 py-4 lg:flex-row lg:px-6">
        <aside className="mb-4 w-full rounded-[2rem] border border-white/10 bg-[rgba(6,10,14,0.92)] p-5 shadow-[0_20px_80px_rgba(0,0,0,0.3)] lg:mb-0 lg:mr-5 lg:w-[280px]">
          <div className="flex items-center gap-3 border-b border-white/10 pb-5">
            <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-cyan-400/10 text-cyan-200">
              <Bot className="h-6 w-6" />
            </div>
            <div>
              <p className="text-[11px] uppercase tracking-[0.28em] text-cyan-200/80">
                Trading Bot
              </p>
              <h1 className="text-xl font-semibold tracking-tight text-white">
                Operator Terminal
              </h1>
            </div>
          </div>

          <div className="mt-5 space-y-3">
            {navItems.map(({ label, icon: Icon, state }) => (
              <div
                className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3"
                key={label}
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className="rounded-xl bg-white/5 p-2 text-slate-200">
                      <Icon className="h-4 w-4" />
                    </div>
                    <span className="text-sm font-medium text-slate-100">{label}</span>
                  </div>
                  <span className="text-[10px] uppercase tracking-[0.16em] text-slate-500">
                    {state}
                  </span>
                </div>
              </div>
            ))}
          </div>

          <div className="mt-6 rounded-[1.6rem] border border-cyan-400/15 bg-cyan-400/5 p-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-[11px] uppercase tracking-[0.22em] text-cyan-200/90">
                  Foundation
                </p>
                <p className="mt-2 text-sm text-slate-300">
                  New Next.js dashboard shell replacing the old HTML layout one slice at a time.
                </p>
              </div>
              <Badge variant="info">v1</Badge>
            </div>
          </div>
        </aside>

        <main className="flex-1">{children}</main>
      </div>
    </div>
  );
}
