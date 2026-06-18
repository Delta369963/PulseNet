'use client'

import { ShieldCheck, AlertTriangle, UserCheck } from 'lucide-react'

export function ResponsibleAIPanel({ lowConfidenceCount }: { lowConfidenceCount: number }) {
  return (
    <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/[0.04] p-3">
      <div className="flex items-center gap-2">
        <ShieldCheck className="h-4 w-4 text-emerald-400" />
        <h2 className="text-xs font-semibold tracking-wide text-emerald-300">
          RESPONSIBLE AI · GOVERNANCE STANCE
        </h2>
      </div>
      <div className="mt-2 grid gap-2 text-[11px] leading-relaxed text-muted-foreground sm:grid-cols-3">
        <div className="flex items-start gap-1.5">
          <UserCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
          <span>
            <span className="font-semibold text-foreground">Decision-support only.</span> PulseNet
            predicts, explains, and proposes — it never executes a reroute. Every action ends at a
            human approval step.
          </span>
        </div>
        <div className="flex items-start gap-1.5">
          <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-red-400" />
          <span>
            <span className="font-semibold text-foreground">Equity-weighted, not blind.</span>{' '}
            Regions with sparse monitoring data are never silently treated as “no risk”.{' '}
            <span className="font-mono-data text-red-400">{lowConfidenceCount}</span> region(s) are
            currently flagged low-confidence — verify manually.
          </span>
        </div>
        <div className="flex items-start gap-1.5">
          <ShieldCheck className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
          <span>
            <span className="font-semibold text-foreground">Explainable by design.</span> LLMs parse
            unstructured signals into structured events; deterministic code runs the graph traversal
            and Monte Carlo. Every number is traceable to a source citation.
          </span>
        </div>
      </div>
    </div>
  )
}
