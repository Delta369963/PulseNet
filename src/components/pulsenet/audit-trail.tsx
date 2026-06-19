'use client'

import { cn } from '@/lib/utils'
import { History, Check, X, Pencil, Ban, Zap, Activity, RotateCcw } from 'lucide-react'
import { timeAgo } from './helpers'
import type { Decision } from './types'

const ACTION_META: Record<string, { icon: React.ComponentType<{ className?: string }>; tone: string; label: string }> = {
  approve: { icon: Check, tone: 'text-zinc-300 bg-zinc-400/10', label: 'APPROVED' },
  reject: { icon: X, tone: 'text-zinc-400 bg-zinc-500/10', label: 'REJECTED' },
  adjust: { icon: Pencil, tone: 'text-amber-400 bg-amber-500/10', label: 'ADJUSTED' },
  dismiss: { icon: Ban, tone: 'text-zinc-400 bg-zinc-500/10', label: 'DISMISSED' },
  ingest: { icon: Zap, tone: 'text-cyan-300 bg-cyan-500/10', label: 'INGESTED' },
  evaluate: { icon: Activity, tone: 'text-violet-300 bg-violet-500/10', label: 'EVALUATED' },
  reset: { icon: RotateCcw, tone: 'text-zinc-300 bg-zinc-500/10', label: 'RESET' },
}

export function AuditTrail({ decisions, loading }: { decisions: Decision[]; loading: boolean }) {
  return (
    <div className="rounded-lg border border-border bg-card/50">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <History className="h-3.5 w-3.5 text-zinc-300" />
          <h2 className="text-xs font-semibold tracking-wide">DECISION LOG · AUDIT TRAIL</h2>
        </div>
        <span className="font-mono-data text-[10px] text-muted-foreground">{decisions.length}</span>
      </div>
      <div className="pn-scroll max-h-56 overflow-y-auto p-2">
        {loading ? (
          [0, 1, 2, 3].map((i) => <div key={i} className="mb-1.5 h-8 animate-pulse rounded bg-muted/40" />)
        ) : decisions.length === 0 ? (
          <p className="py-4 text-center text-[11px] text-muted-foreground">No decisions logged yet.</p>
        ) : (
          <ul className="space-y-1">
            {decisions.map((d) => {
              const m = ACTION_META[d.action] ?? ACTION_META.reset
              const Icon = m.icon
              return (
                <li
                  key={d.id}
                  className="flex items-center gap-2 rounded-md border border-transparent px-2 py-1.5 hover:border-border hover:bg-muted/30"
                >
                  <span className={cn('flex h-6 w-6 shrink-0 items-center justify-center rounded-md', m.tone)}>
                    <Icon className="h-3 w-3" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[11px] leading-tight">{d.summary}</p>
                    <p className="text-[9px] text-muted-foreground">
                      <span className="font-mono-data">{d.actor}</span> · {timeAgo(d.createdAt)}
                    </p>
                  </div>
                  <span className={cn('font-mono-data text-[9px] font-semibold', m.tone.split(' ')[0])}>
                    {m.label}
                  </span>
                </li>
              )
            })}
          </ul>
        )}
      </div>
    </div>
  )
}
