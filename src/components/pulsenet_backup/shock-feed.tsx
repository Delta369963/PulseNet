'use client'

import { cn } from '@/lib/utils'
import { MapPin, Layers, GitBranch, Inbox } from 'lucide-react'
import { timeAgo, shockTypeMeta } from './helpers'
import { ConfidenceBadge, ModeBadge, SeverityBadge, ShockStatusBadge, SourceBadge } from './badges'

import type { ShockListItem } from './types'

function ShockCard({
  shock,
  selected,
  onSelect,
}: {
  shock: ShockListItem
  selected: boolean
  onSelect: () => void
}) {
  const meta = shockTypeMeta(shock.type)
  return (
    <button
      onClick={onSelect}
      className={cn(
        'group w-full rounded-lg border bg-card p-3 text-left transition-all hover:border-emerald-500/40 hover:bg-accent/40',
        selected ? 'border-emerald-500/60 ring-1 ring-emerald-500/40' : 'border-border',
      )}
    >
      <div className="flex items-start gap-2">
        <span className="mt-0.5 text-base leading-none">{meta.icon}</span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <SeverityBadge severity={shock.severity} />
            <ShockStatusBadge status={shock.status} />
            <span className="ml-auto font-mono-data text-[10px] text-muted-foreground">
              {timeAgo(shock.occurredAt)}
            </span>
          </div>
          <h3 className="mt-1.5 line-clamp-2 text-sm font-semibold leading-snug">
            {shock.title}
          </h3>
          <div className="mt-1 flex items-center gap-1 text-[11px] text-muted-foreground">
            <MapPin className="h-3 w-3 shrink-0" />
            <span className="truncate">{shock.locationName}</span>
          </div>
        </div>
      </div>

      <p className="mt-2 line-clamp-2 text-[11px] leading-relaxed text-muted-foreground">
        {shock.description}
      </p>

      <div className="mt-2.5 flex flex-wrap items-center gap-1.5">
        <SourceBadge source={shock.source} />
        <ModeBadge title={shock.title} />
        <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted/40 px-1.5 py-0.5 text-[10px] text-muted-foreground">
          <Layers className="h-2.5 w-2.5" /> {shock.exposureCount} exp
        </span>
        <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted/40 px-1.5 py-0.5 text-[10px] text-muted-foreground">
          <GitBranch className="h-2.5 w-2.5" /> {shock.rerouteCount} routes
        </span>
        <ConfidenceBadge confidence={shock.confidence} className="ml-auto" />
      </div>
      {shock.title.toLowerCase().includes('(replay)') && shock.status === 'evaluated' && (
        <p className="mt-2 rounded border border-amber-500/20 bg-amber-500/5 px-2 py-1 text-[10px] text-amber-400/80">
          ✓ Backward-chain validated — this scenario's ripple predictions have been tested against known historical outcomes (<code className="font-mono">test_backward_chain.py</code>).
        </p>
      )}
    </button>

  )
}

export function ShockFeed({
  shocks,
  selectedId,
  onSelect,
  loading,
}: {
  shocks: ShockListItem[]
  selectedId: string | null
  onSelect: (id: string) => void
  loading: boolean
}) {
  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-card/50">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="pn-pulse-ring absolute inline-flex h-full w-full rounded-full bg-emerald-400" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500" />
          </span>
          <h2 className="text-xs font-semibold tracking-wide text-foreground">LIVE SHOCK FEED</h2>
        </div>
        <span className="font-mono-data text-[10px] text-muted-foreground">{shocks.length}</span>
      </div>
      <div className="pn-scroll max-h-[calc(100vh-220px)] min-h-[200px] flex-1 space-y-2 overflow-y-auto p-2">
        {loading && shocks.length === 0 ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-28 animate-pulse rounded-lg bg-muted/40" />
            ))}
          </div>
        ) : shocks.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-center text-muted-foreground">
            <Inbox className="h-8 w-8 opacity-40" />
            <p className="text-xs">No shocks ingested yet.</p>
            <p className="text-[11px]">Click <span className="font-semibold text-emerald-400">Run Ingestion</span> to pull live signals.</p>
          </div>
        ) : (
          shocks.map((s) => (
            <ShockCard
              key={s.id}
              shock={s}
              selected={s.id === selectedId}
              onSelect={() => onSelect(s.id)}
            />
          ))
        )}
      </div>
    </div>
  )
}
