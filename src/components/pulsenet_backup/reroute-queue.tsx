'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { toast } from 'sonner'
import {
  Check,
  X,
  Pencil,
  ArrowRight,
  Gauge,
  DollarSign,
  Clock,
  Activity,
  ExternalLink,
  GitBranch,
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import {
  ConfidenceBadge,
  LowConfidenceFlag,
  RerouteStatusBadge,
} from './badges'
import { timeAgo } from './helpers'
import type { RerouteSuggestion } from './types'

function Metric({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  tone?: string
}) {
  return (
    <div className="rounded-md border border-border bg-background/40 px-2 py-1.5">
      <div className="flex items-center gap-1 text-[9px] uppercase tracking-wide text-muted-foreground">
        <Icon className="h-2.5 w-2.5" /> {label}
      </div>
      <div className={cn('font-mono-data text-xs font-semibold', tone)}>{value}</div>
    </div>
  )
}

function RerouteCard({
  reroute,
  sourceUrl,
  onDecide,
}: {
  reroute: RerouteSuggestion
  sourceUrl: string | null
  onDecide: (id: string, action: 'approve' | 'reject' | 'adjust', note?: string) => Promise<void>
}) {
  const [adjusting, setAdjusting] = useState(false)
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const lowConf = reroute.confidence < 0.5
  const mc = reroute.monteCarloOutcome
  const successPct = mc ? Math.round(mc.successProb * 100) : null

  async function handle(action: 'approve' | 'reject' | 'adjust', n?: string) {
    setBusy(true)
    try {
      await onDecide(reroute.id, action, n)
      setAdjusting(false)
      setNote('')
    } catch {
      toast.error('Decision could not be recorded.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div
      className={cn(
        'rounded-lg border bg-card p-3',
        reroute.status === 'pending'
          ? lowConf
            ? 'border-red-500/30'
            : 'border-border'
          : 'border-border opacity-80',
      )}
    >
      <div className="flex items-start gap-2">
        <GitBranch className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-400" />
        <div className="min-w-0 flex-1">
          <h3 className="text-sm font-semibold leading-snug">{reroute.title}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-1.5">
            <RerouteStatusBadge status={reroute.status} />
            <ConfidenceBadge confidence={reroute.confidence} />
            {lowConf && reroute.status === 'pending' && <LowConfidenceFlag />}
          </div>
        </div>
      </div>

      <p className="mt-2 line-clamp-3 text-[11px] leading-relaxed text-muted-foreground">
        {reroute.rationale}
      </p>

      {/* from -> to */}
      <div className="mt-2 flex items-center gap-1.5 rounded-md border border-border bg-background/40 px-2 py-1.5 text-[11px]">
        <span className="truncate font-medium text-amber-300/90">{reroute.fromSupplier}</span>
        <ArrowRight className="h-3 w-3 shrink-0 text-emerald-400" />
        <span className="truncate font-semibold text-emerald-400">{reroute.toSupplier}</span>
      </div>

      {/* metrics */}
      <div className="mt-2 grid grid-cols-2 gap-1.5">
        <Metric icon={Activity} label="Success prob" value={successPct != null ? `${successPct}%` : '—'} tone={successPct != null && successPct >= 50 ? 'text-emerald-400' : successPct != null && successPct >= 35 ? 'text-amber-400' : 'text-red-400'} />
        <Metric icon={Clock} label="Shortage window" value={mc ? `~${mc.medianShortageWindow}d (p95 ${mc.p95ShortageWindow}d)` : '—'} tone="text-amber-300" />
        <Metric icon={DollarSign} label="Cost increase" value={`+${reroute.estimatedCostIncrease}%`} tone="text-orange-300" />
        <Metric icon={Clock} label="Time to add" value={`+${reroute.estimatedTimeToAddDays}d`} />
        <Metric icon={Gauge} label="Feasibility" value={`${Math.round(reroute.feasibilityScore * 100)}%`} tone={reroute.feasibilityScore >= 0.6 ? 'text-emerald-400' : 'text-amber-400'} />
        <Metric icon={Activity} label="MC trials" value={mc ? String(mc.trials) : '—'} />
      </div>

      {sourceUrl && (
        <a
          href={sourceUrl}
          target="_blank"
          rel="noreferrer"
          className="mt-2 inline-flex items-center gap-1 text-[10px] text-cyan-400 hover:underline"
        >
          <ExternalLink className="h-2.5 w-2.5" /> source citation
        </a>
      )}

      {/* decided state */}
      {reroute.status !== 'pending' && (
        <div className="mt-2 rounded-md border border-border bg-muted/30 px-2 py-1.5 text-[10px] text-muted-foreground">
          <span className="font-semibold text-foreground">{reroute.decidedBy}</span> ·{' '}
          {reroute.decidedAt ? timeAgo(reroute.decidedAt) : ''}
          {reroute.adminNote && <p className="mt-0.5 italic">“{reroute.adminNote}”</p>}
        </div>
      )}

      {/* HITL controls */}
      {reroute.status === 'pending' && (
        <div className="mt-2.5">
          {!adjusting ? (
            <div className="flex gap-1.5">
              <Button
                size="sm"
                disabled={busy}
                onClick={() => handle('approve')}
                className="h-7 flex-1 bg-emerald-600 text-white hover:bg-emerald-500"
              >
                <Check className="h-3.5 w-3.5" /> Approve
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => setAdjusting(true)}
                className="h-7 flex-1 border-amber-500/40 text-amber-300 hover:bg-amber-500/10"
              >
                <Pencil className="h-3.5 w-3.5" /> Adjust
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={busy}
                onClick={() => handle('reject')}
                className="h-7 flex-1"
              >
                <X className="h-3.5 w-3.5" /> Reject
              </Button>
            </div>
          ) : (
            <div className="space-y-1.5">
              <Textarea
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Administrator note (what to adjust and why)…"
                className="h-16 resize-none text-[11px]"
              />
              <div className="flex gap-1.5">
                <Button
                  size="sm"
                  disabled={busy}
                  onClick={() => handle('adjust', note || undefined)}
                  className="h-7 flex-1 bg-amber-600 text-white hover:bg-amber-500"
                >
                  Submit adjustment
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => {
                    setAdjusting(false)
                    setNote('')
                  }}
                  className="h-7"
                >
                  Cancel
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export function RerouteQueue({
  reroutes,
  sourceUrl,
  loading,
  onDecide,
}: {
  reroutes: RerouteSuggestion[]
  sourceUrl: string | null
  loading: boolean
  onDecide: (id: string, action: 'approve' | 'reject' | 'adjust', note?: string) => Promise<void>
}) {
  const pending = reroutes.filter((r) => r.status === 'pending')
  const decided = reroutes.filter((r) => r.status !== 'pending')
  return (
    <div className="flex h-full flex-col rounded-lg border border-border bg-card/50">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <GitBranch className="h-3.5 w-3.5 text-emerald-400" />
          <h2 className="text-xs font-semibold tracking-wide">REROUTE QUEUE · HUMAN APPROVAL</h2>
        </div>
        <span className="font-mono-data text-[10px] text-amber-300">{pending.length} pending</span>
      </div>
      <div className="pn-scroll max-h-[calc(100vh-220px)] min-h-[200px] flex-1 space-y-2 overflow-y-auto p-2">
        {loading ? (
          [0, 1].map((i) => <div key={i} className="h-48 animate-pulse rounded-lg bg-muted/40" />)
        ) : reroutes.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 py-12 text-center text-muted-foreground">
            <GitBranch className="h-8 w-8 opacity-40" />
            <p className="text-xs">No reroutes for this shock.</p>
            <p className="text-[11px]">Select a shock and click <span className="font-semibold text-emerald-400">Evaluate Ripple</span>.</p>
          </div>
        ) : (
          <>
            {pending.map((r) => (
              <RerouteCard key={r.id} reroute={r} sourceUrl={sourceUrl} onDecide={onDecide} />
            ))}
            {decided.length > 0 && (
              <div className="pt-1">
                <div className="mb-1.5 px-1 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
                  Decided ({decided.length})
                </div>
                {decided.map((r) => (
                  <RerouteCard key={r.id} reroute={r} sourceUrl={sourceUrl} onDecide={onDecide} />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
