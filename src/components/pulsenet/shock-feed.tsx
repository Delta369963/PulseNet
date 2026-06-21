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
        'group w-full rounded-sm border bg-card p-2 text-left transition-all hover:border-zinc-400/40 hover:bg-accent/40',
        selected ? 'border-zinc-400/60 ring-1 ring-zinc-400/40' : 'border-border',
      )}
    >
      <div className="flex flex-col gap-1.5">
        {/* Top Row: Meta + Title */}
        <div className="flex items-center gap-2">
          <span className="font-mono-data text-[10px] text-muted-foreground w-12 shrink-0">{timeAgo(shock.occurredAt)}</span>
          <SeverityBadge severity={shock.severity} />
          <span className="truncate text-xs font-semibold leading-none">{shock.title}</span>
        </div>

        {/* Bottom Row: Location & Data */}
        <div className="flex items-center gap-2 pl-14 w-full overflow-hidden pr-2">
          <div className="flex items-center gap-1 text-[10px] text-muted-foreground shrink-0 max-w-[100px]">
            <MapPin className="h-2.5 w-2.5 shrink-0" />
            <span className="truncate">{shock.locationName}</span>
          </div>
          <SourceBadge source={shock.source} className="shrink-0 max-w-[80px]" />
          <span className="font-mono-data text-[9px] text-muted-foreground border border-border px-1 rounded-sm bg-muted/40 shrink-0">EXP:{shock.exposureCount}</span>
          <span className="font-mono-data text-[9px] text-muted-foreground border border-border px-1 rounded-sm bg-muted/40 shrink-0">RT:{shock.rerouteCount}</span>
          <ConfidenceBadge confidence={shock.confidence} className="ml-auto shrink-0 scale-90 origin-right" />
        </div>
      </div>
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
    <div className="flex h-full flex-col rounded-sm border border-border bg-card/50">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2 w-2">
            <span className="pn-pulse-ring absolute inline-flex h-full w-full rounded-full bg-zinc-300" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-zinc-400" />
          </span>
          <h2 className="text-xs font-semibold tracking-wide text-foreground">LIVE SHOCK FEED</h2>
        </div>
        <span className="font-mono-data text-[10px] text-muted-foreground">{shocks.length}</span>
      </div>
      <div className="pn-scroll max-h-[calc(100vh-220px)] min-h-[200px] flex-1 space-y-2 overflow-y-auto p-2">
        {loading && shocks.length === 0 ? (
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-16 animate-pulse rounded-sm bg-muted/40" />
            ))}
          </div>
        ) : shocks.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-center text-muted-foreground">
            <Inbox className="h-8 w-8 opacity-40" />
            <p className="text-xs">No shocks ingested yet.</p>
            <p className="text-[11px]">Click <span className="font-semibold text-zinc-300">Run Ingestion</span> to pull live signals.</p>
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
