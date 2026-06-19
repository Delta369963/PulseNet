'use client'

import { cn } from '@/lib/utils'
import { Clock, AlertTriangle, ArrowRight, Globe2 } from 'lucide-react'
import { riskStyle } from './helpers'
import { ConfidenceBadge, LowConfidenceFlag } from './badges'
import type { ExposedRegion } from './types'

export function ExposedRegionsList({
  exposures,
  loading,
}: {
  exposures: ExposedRegion[]
  loading: boolean
}) {
  return (
    <div className="rounded-lg border border-border bg-card/50">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <Globe2 className="h-3.5 w-3.5 text-zinc-300" />
          <h2 className="text-xs font-semibold tracking-wide">EXPOSED REGIONS — DOWNSTREAM RISK</h2>
        </div>
        <span className="font-mono-data text-[10px] text-muted-foreground">{exposures.length}</span>
      </div>
      <div className="pn-scroll max-h-72 space-y-1.5 overflow-y-auto p-2">
        {loading ? (
          [0, 1, 2].map((i) => <div key={i} className="h-16 animate-pulse rounded bg-muted/40" />)
        ) : exposures.length === 0 ? (
          <p className="py-6 text-center text-[11px] text-muted-foreground">
            Select a shock and run ripple evaluation to see downstream exposure.
          </p>
        ) : (
          exposures.map((e) => {
            const r = riskStyle(e.riskScore)
            const lowConf = e.monitoringDensity < 0.55
            return (
              <div
                key={e.id}
                className={cn(
                  'rounded-md border bg-background/40 p-2.5',
                  lowConf ? 'border-red-500/30' : 'border-border',
                )}
              >
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold">{e.countryName}</span>
                  <span className="rounded bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                    {e.region}
                  </span>
                  <span className="ml-auto inline-flex items-center gap-1 rounded-md border border-border bg-muted/40 px-1.5 py-0.5 text-[10px] font-mono-data">
                    {e.commodityCode}
                  </span>
                </div>

                {/* risk bar */}
                <div className="mt-2 flex items-center gap-2">
                  <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                    <div
                      className={cn('h-full rounded-full', r.bar)}
                      style={{ width: `${Math.min(100, e.riskScore)}%` }}
                    />
                  </div>
                  <span className={cn('font-mono-data text-[11px] font-semibold', r.text)}>
                    {Math.round(e.riskScore)}
                  </span>
                  <span className={cn('text-[10px] font-semibold', r.text)}>{r.label}</span>
                </div>

                {/* meta row */}
                <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-muted-foreground">
                  <span className="inline-flex items-center gap-1">
                    <Clock className="h-3 w-3" /> shortage in ~{e.timeToShortageDays}d
                  </span>
                  <ConfidenceBadge confidence={e.confidence} />
                  {e.cascadeConfidence > 0 && (
                    <span
                      className="inline-flex items-center gap-1 rounded-md border border-cyan-500/30 bg-cyan-500/10 px-1.5 py-0.5 text-[10px] font-semibold text-cyan-400"
                      title={`Cascade P = exposure share × vulnerability (1−SRI). Reflects how likely this nation is to be hit given the shock, weighted by national resilience. Higher = more fragile nation with more exposure.`}
                    >
                      Cascade P: {Math.round(e.cascadeConfidence * 100)}%
                    </span>
                  )}
                  {lowConf && <LowConfidenceFlag />}
                </div>

                {/* causal path — full trace, no line-clamp */}
                <p className="mt-1.5 flex items-start gap-1 text-[10px] leading-relaxed text-muted-foreground">
                  <ArrowRight className="mt-0.5 h-2.5 w-2.5 shrink-0 text-zinc-300" />
                  <span>{e.exposurePath}</span>
                </p>

                {lowConf && (
                  <p className="mt-1 flex items-center gap-1 text-[10px] text-red-400/80">
                    <AlertTriangle className="h-2.5 w-2.5" />
                    Sparse monitoring — treat AI estimate as weak; verify on the ground.
                  </p>
                )}
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
