'use client'

import { cn } from '@/lib/utils'
import { AlertTriangle, GitBranch, Globe2, Layers, ShieldAlert, Zap } from 'lucide-react'
import type { Stats } from './types'

function Stat({
  icon: Icon,
  label,
  value,
  tone,
  hint,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: number | string
  tone?: string
  hint?: string
}) {
  return (
    <div className="flex items-center gap-2.5 rounded-lg border border-border bg-card/50 px-3 py-2">
      <div className={cn('flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted/50', tone)}>
        <Icon className="h-4 w-4" />
      </div>
      <div className="min-w-0">
        <div className="font-mono-data text-lg font-bold leading-none">{value}</div>
        <div className="mt-0.5 truncate text-[10px] uppercase tracking-wide text-muted-foreground">
          {label}
        </div>
        {hint && <div className="text-[9px] text-muted-foreground/70">{hint}</div>}
      </div>
    </div>
  )
}

export function StatsBar({ stats }: { stats: Stats | null }) {
  return (
    <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
      <Stat icon={Zap} label="Live shocks" value={stats?.shocks ?? '—'} tone="text-amber-400" />
      <Stat icon={Layers} label="Exposed regions" value={stats?.exposures ?? '—'} tone="text-orange-400" />
      <Stat icon={GitBranch} label="Pending reroutes" value={stats?.pendingReroutes ?? '—'} tone="text-zinc-300" hint="awaiting approval" />
      <Stat
        icon={ShieldAlert}
        label="Low-confidence"
        value={stats?.lowConfidence ?? '—'}
        tone="text-red-400"
        hint="equity-flagged"
      />
      <Stat icon={Globe2} label="Countries" value={stats?.countries ?? '—'} tone="text-cyan-300" />
      <Stat icon={AlertTriangle} label="Audit entries" value={stats?.decisions ?? '—'} tone="text-zinc-300" />
    </div>
  )
}
