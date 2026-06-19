'use client'

import { ShieldCheck, AlertTriangle, UserCheck, BookLock } from 'lucide-react'
import { cn } from '@/lib/utils'
import { timeAgo } from './helpers'
import type { LedgerRow } from './types'

/** Delta colour: green = agents agreed, amber = some divergence, red = major disagreement */
function deltaStyle(d: number): string {
  if (d < 0.15) return 'text-emerald-400'
  if (d < 0.45) return 'text-amber-400'
  return 'text-red-400'
}

function deltaLabel(d: number): string {
  if (d < 0.15) return 'High consensus'
  if (d < 0.45) return 'Moderate divergence'
  return 'Low consensus'
}

export function ResponsibleAIPanel({
  lowConfidenceCount,
  ledger = [],
}: {
  lowConfidenceCount: number
  ledger?: LedgerRow[]
}) {
  return (
    <div className="space-y-2">
      {/* Governance stance */}
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
              Regions with sparse monitoring data are never silently treated as "no risk".{' '}
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

      {/* Consensus ledger */}
      <div className="rounded-lg border border-border bg-card/40 p-3">
        <div className="flex items-center gap-2">
          <BookLock className="h-3.5 w-3.5 text-cyan-400" />
          <h2 className="text-xs font-semibold tracking-wide text-cyan-300">
            CONSENSUS LEDGER · AGENT AGREEMENT TRACE
          </h2>
          <span className="ml-auto text-[10px] text-muted-foreground">
            Alpha ∥ Beta → Gamma · Byzantine delta logged per crisis
          </span>
        </div>

        {ledger.length === 0 ? (
          <p className="mt-2 text-[11px] text-muted-foreground">
            No ledger entries yet. Run ingestion or evaluate a ripple to populate — engine must be running.
          </p>
        ) : (
          <div className="mt-2 space-y-1">
            {ledger.slice(0, 8).map((row) => (
              <div
                key={row.crisisId}
                className="flex flex-wrap items-center gap-x-3 gap-y-0.5 rounded border border-border/40 bg-muted/20 px-2 py-1 text-[10px]"
              >
                <span className={cn('font-semibold', deltaStyle(row.byzantineAgreementDelta))}>
                  δ {row.byzantineAgreementDelta.toFixed(2)}
                </span>
                <span className={cn('hidden sm:inline', deltaStyle(row.byzantineAgreementDelta))}>
                  {deltaLabel(row.byzantineAgreementDelta)}
                </span>
                <span className="text-muted-foreground">·</span>
                <span className="max-w-[28ch] truncate text-foreground/80">
                  {row.detectedShockVector?.initialAsset ?? row.sourceFeedUrl}
                </span>
                {row.detectedShockVector?.severity && (
                  <span className="text-muted-foreground capitalize">
                    {row.detectedShockVector.severity}
                  </span>
                )}
                {row.humanInTheLoopOverride && (
                  <span className="rounded bg-amber-500/15 px-1 py-0.5 text-amber-400">HITL override</span>
                )}
                <span className="ml-auto text-muted-foreground">{timeAgo(row.timestamp)}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
