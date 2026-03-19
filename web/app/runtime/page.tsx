import { Activity } from "lucide-react";

import { OperatorShell } from "@/components/operator-shell";
import { Badge } from "@/components/ui/badge";

export default function Runtime() {
  return (
    <OperatorShell>
      <div className="rounded-[2rem] border border-white/10 bg-[linear-gradient(135deg,rgba(8,13,19,0.94),rgba(10,18,27,0.78))] px-6 py-10 shadow-[0_20px_70px_rgba(0,0,0,0.28)]">
        <div className="flex max-w-2xl flex-col gap-5">
          <Badge variant="neutral">Next slice</Badge>
          <div className="flex items-center gap-3 text-cyan-200">
            <Activity className="h-5 w-5" />
            <span className="text-sm uppercase tracking-[0.22em]">Runtime surface</span>
          </div>
          <h2 className="text-4xl font-semibold tracking-tight text-white">
            Runtime controls will land here next.
          </h2>
          <p className="text-sm text-slate-300">
            The current implementation focus is the market-sync workflow. This route exists so the
            operator shell stays navigable while the runtime slice is still being built.
          </p>
        </div>
      </div>
    </OperatorShell>
  );
}
