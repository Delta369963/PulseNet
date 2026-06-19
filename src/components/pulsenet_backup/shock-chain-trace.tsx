'use client'

import { cn } from '@/lib/utils'
import { ExternalLink, ArrowRight, Zap, Globe2, GitBranch, AlertTriangle } from 'lucide-react'
import { riskStyle } from './helpers'
import { ConfidenceBadge, LowConfidenceFlag } from './badges'
import type { ExposedRegion, RerouteSuggestion, ShockListItem, ShockDetail } from './types'

/** The detail shock shape (missing exposureCount/rerouteCount vs ShockListItem). */
type ShockBase = ShockListItem | ShockDetail['shock']


function MetricPill({
  label, value, color = 'text-muted-foreground',
}: { label: string; value: string; color?: string }) {
  return (
    <span className="inline-flex items-baseline gap-0.5 rounded bg-muted/40 px-1.5 py-0.5 font-mono text-[10px]">
      <span className="text-muted-foreground">{label}:</span>
      <span className={cn('font-semibold', color)}>{value}</span>
    </span>
  )
}

function ChainNode({ step, label, icon }: { step: number; label: string; icon: React.ReactNode }) {
  return (
    <div className="flex items-center gap-2">
      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded border border-cyan-500/40 bg-cyan-500/10 text-[10px] font-bold text-cyan-400">{step}</span>
      <span className="flex items-center gap-1.5 text-[11px] font-semibold text-cyan-300/80">
        {icon} {label}
      </span>
    </div>
  )
}

function ExposureRow({ e }: { e: ExposedRegion }) {
  const r = riskStyle(e.riskScore)
  const lowConf = e.monitoringDensity < 0.55
  return (
    <div className={cn('rounded border bg-background/30 p-2', lowConf ? 'border-red-500/20' : 'border-border/50')}>
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-[12px] font-bold text-foreground">{e.countryName}</span>
        <span className="rounded bg-muted/60 px-1 py-0.5 text-[10px] text-muted-foreground">{e.region}</span>
        <span className={cn('ml-auto font-mono text-[11px] font-bold', r.text)}>{Math.round(e.riskScore)} risk</span>
        <span className="font-mono text-[10px] font-semibold text-muted-foreground">{e.commodityCode}</span>
      </div>
      <div className="mt-1 h-1 overflow-hidden rounded bg-muted/60">
        <div className={cn('h-full rounded', r.bar)} style={{ width: `${Math.min(100, e.riskScore)}%` }} />
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1">
        <MetricPill label="exposure" value={`${Math.round((e.cascadeConfidence / Math.max(e.cascadeConfidence, 0.01)) * 100 * (e.cascadeConfidence > 0 ? 1 : 0))}%`} color="text-muted-foreground" />
        {e.cascadeConfidence > 0 && (
          <span
            className="inline-flex items-baseline gap-0.5 rounded border border-cyan-500/30 bg-cyan-500/8 px-1.5 py-0.5 font-mono text-[10px]"
            title="Cascade P = exposure share × (1−SRI). Weighted by national resilience."
          >
            <span className="text-muted-foreground">cascade:</span>
            <span className="font-semibold text-cyan-400">{Math.round(e.cascadeConfidence * 100)}%</span>
          </span>
        )}
        <MetricPill label="shortage" value={`~${e.timeToShortageDays}d`} color="text-amber-400" />
        <ConfidenceBadge confidence={e.confidence} />
        {lowConf && <LowConfidenceFlag />}
      </div>
      <p className="mt-1.5 flex items-start gap-1 text-[10px] leading-relaxed text-muted-foreground">
        <ArrowRight className="mt-0.5 h-2.5 w-2.5 shrink-0 text-emerald-400/70" />
        <span>{e.exposurePath}</span>
      </p>
    </div>
  )
}

function RerouteRow({ r }: { r: RerouteSuggestion }) {
  const mc = r.monteCarloOutcome
  const statusColor = r.status === 'approved' ? 'text-emerald-400' : r.status === 'rejected' ? 'text-red-400/70' : 'text-amber-400'
  return (
    <div className="rounded border border-border/40 bg-background/20 p-2">
      <div className="flex items-start gap-2">
        <GitBranch className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
        <div className="flex-1 min-w-0">
          <p className="text-[11px] font-semibold text-foreground/90 leading-snug">{r.title}</p>
          <p className="mt-0.5 text-[10px] text-muted-foreground leading-relaxed">{r.rationale}</p>
        </div>
        <span className={cn('shrink-0 text-[10px] font-semibold uppercase tracking-wide', statusColor)}>
          {r.status}
        </span>
      </div>
      {mc && (
        <div className="mt-1.5 flex flex-wrap gap-1">
          <MetricPill label="success" value={`${Math.round(mc.successProb * 100)}%`} color={mc.successProb > 0.6 ? 'text-emerald-400' : 'text-amber-400'} />
          <MetricPill label="median-window" value={`${mc.medianShortageWindow}d`} />
          <MetricPill label="p95" value={`${mc.p95ShortageWindow}d`} />
          <MetricPill label="cost+" value={`${r.estimatedCostIncrease}%`} />
          <MetricPill label="feasibility" value={`${Math.round(r.feasibilityScore * 100)}%`} />
          <MetricPill label="tta" value={`${r.estimatedTimeToAddDays}d`} />
        </div>
      )}
      {r.adminNote && (
        <p className="mt-1 text-[10px] italic text-muted-foreground/70">Admin: {r.adminNote}</p>
      )}
    </div>
  )
}

export function ShockChainTrace({
  shock, exposures, reroutes, loading,
}: {
  shock: ShockBase | null

  exposures: ExposedRegion[]
  reroutes: RerouteSuggestion[]
  loading: boolean
}) {
  if (!shock) {
    return (
      <div className="flex h-40 items-center justify-center rounded-lg border border-border bg-card/30 text-[11px] text-muted-foreground">
        Select a shock event to trace its downstream forward chain.
      </div>
    )
  }

  const evaluated = shock.status === 'evaluated'

  return (
    <div className="space-y-2">
      {/* Source strip */}
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border/50 bg-card/30 px-3 py-2 text-[10px] text-muted-foreground">
        <Zap className="h-3 w-3 text-amber-400" />
        <span className="font-semibold text-foreground/80">Source:</span>
        <span className="font-mono text-muted-foreground">{shock.source}</span>
        {shock.sourceUrl && (
          <a href={shock.sourceUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-cyan-400 hover:underline">
            <ExternalLink className="h-2.5 w-2.5" /> {shock.sourceUrl.replace(/^https?:\/\//, '').split('/')[0]}
          </a>
        )}
        <span className="ml-auto">Ingest confidence: <span className="font-semibold text-foreground/80">{Math.round(shock.confidence * 100)}%</span></span>
      </div>

      {/* Chain */}
      <div className="rounded-lg border border-border/50 bg-card/20 p-3 space-y-3">
        {/* Step 1: Shock */}
        <div>
          <ChainNode step={1} label="SHOCK EVENT" icon={<Zap className="h-3 w-3" />} />
          <div className="ml-7 mt-1 flex flex-wrap gap-1 text-[10px]">
            <MetricPill label="type" value={shock.type.replace('_', ' ')} color="text-red-400" />
            <MetricPill label="severity" value={shock.severity} color="text-orange-400" />
            <MetricPill label="region(s)" value={shock.countryCodes.length.toString()} />
            <MetricPill label="loc" value={shock.locationName.slice(0, 30)} />
          </div>
        </div>

        <div className="ml-3 text-muted-foreground/40">│</div>

        {/* Step 2: Supplier halt */}
        <div>
          <ChainNode step={2} label={`SUPPLIER HALT (${shock.countryCodes.join(', ')})`} icon={<Globe2 className="h-3 w-3" />} />
          <p className="ml-7 mt-1 text-[10px] text-muted-foreground leading-relaxed">{shock.description}</p>
        </div>

        {evaluated && exposures.length > 0 && (
          <>
            <div className="ml-3 text-muted-foreground/40">│</div>
            {/* Step 3: Exposures */}
            <div>
              <ChainNode step={3} label={`DOWNSTREAM EXPOSURE (${exposures.length} nation-commodity pairs)`} icon={<AlertTriangle className="h-3 w-3" />} />
              <div className="ml-7 mt-2 space-y-1.5">
                {loading
                  ? [0, 1, 2].map((i) => <div key={i} className="h-16 animate-pulse rounded bg-muted/30" />)
                  : exposures.map((e) => <ExposureRow key={e.id} e={e} />)
                }
              </div>
            </div>
          </>
        )}

        {evaluated && reroutes.length > 0 && (
          <>
            <div className="ml-3 text-muted-foreground/40">│</div>
            {/* Step 4: Reroutes */}
            <div>
              <ChainNode step={4} label={`REROUTE OPTIONS (${reroutes.length} proposals)`} icon={<GitBranch className="h-3 w-3" />} />
              <div className="ml-7 mt-2 space-y-1.5">
                {reroutes.map((r) => <RerouteRow key={r.id} r={r} />)}
              </div>
            </div>
          </>
        )}

        {!evaluated && (
          <p className="ml-7 text-[10px] text-muted-foreground italic">
            Run Evaluate Ripple to generate forward-chain trace.
          </p>
        )}
      </div>
    </div>
  )
}
