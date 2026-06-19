'use client'

import { cn } from '@/lib/utils'
import { project, severityStyle, riskStyle, timeAgo } from './helpers'
import type { ExposedRegion, GraphData, ShockListItem } from './types'

type Props = {
  shocks: ShockListItem[]
  exposures: ExposedRegion[] // for the selected shock
  selectedShockId: string | null
  countries: GraphData['countries']
  onSelectShock: (id: string) => void
}

function effectiveCoords(
  shock: ShockListItem,
  countries: GraphData['countries'],
): { lat: number; lng: number } | null {
  if (typeof shock.lat === 'number' && typeof shock.lng === 'number') {
    return { lat: shock.lat, lng: shock.lng }
  }
  for (const code of shock.countryCodes) {
    const c = countries.find((x) => x.code === code)
    if (c) return { lat: c.lat, lng: c.lng }
  }
  return null
}

export function ThreatMap({ shocks, exposures, selectedShockId, countries, onSelectShock }: Props) {
  const plottedShocks = shocks
    .map((s) => ({ shock: s, coords: effectiveCoords(s, countries) }))
    .filter((x) => x.coords) as { shock: ShockListItem; coords: { lat: number; lng: number } }[]

  const selected = plottedShocks.find((x) => x.shock.id === selectedShockId) ?? null
  const rippleExposures = selected
    ? exposures.map((e) => ({ e, p: project(e.lat, e.lng) }))
    : []

  return (
    <div className="relative h-[280px] overflow-hidden rounded-lg border border-border bg-card sm:h-[340px]">
      {/* Decorative world-map backdrop */}
      <img
        src="/world-map.png"
        alt="World map"
        className="pointer-events-none absolute inset-0 h-full w-full object-cover opacity-25 dark:opacity-20"
      />
      {/* Coordinate grid overlay */}
      <div className="ops-grid-bg pointer-events-none absolute inset-0 opacity-60" />
      {/* Equator + prime meridian reference lines */}
      <div className="pointer-events-none absolute inset-x-0 top-1/2 h-px bg-zinc-400/10" />
      <div className="pointer-events-none absolute inset-y-0 left-1/2 w-px bg-zinc-400/10" />

      {/* Ripple flow lines (selected shock -> each exposure) */}
      <svg
        className="pointer-events-none absolute inset-0 h-full w-full"
        viewBox="0 0 1000 500"
        preserveAspectRatio="none"
      >
        {selected &&
          rippleExposures.map(({ e, p }, i) => {
            const sp = project(selected.coords.lat, selected.coords.lng)
            const x1 = sp.x * 1000
            const y1 = sp.y * 500
            const x2 = p.x * 1000
            const y2 = p.y * 500
            const mx = (x1 + x2) / 2
            const my = (y1 + y2) / 2
            const cy = my - Math.abs(x2 - x1) * 0.12 - 20
            const r = riskStyle(e.riskScore)
            return (
              <g key={i}>
                <path
                  d={`M ${x1} ${y1} Q ${mx} ${cy} ${x2} ${y2}`}
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={1.2}
                  className={cn(r.text, 'opacity-40')}
                  strokeDasharray="4 4"
                />
              </g>
            )
          })}
      </svg>

      {/* Exposure region dots (selected shock) */}
      {selected &&
        rippleExposures.map(({ e, p }) => {
          const r = riskStyle(e.riskScore)
          return (
            <button
              key={e.id}
              className="group absolute flex h-4 w-4 items-center justify-center"
              style={{ left: `${p.x * 100}%`, top: `${p.y * 100}%`, transform: 'translate(-50%, -50%)' }}
              title={`${e.countryName} · ${e.commodityName} · risk ${Math.round(e.riskScore)}`}
            >
              <span className={cn('block h-2 w-2 rounded-full ring-2 ring-background', r.bar)} />
              <span className="pointer-events-none absolute left-1/2 top-4 z-20 hidden -translate-x-1/2 whitespace-nowrap rounded border border-border bg-popover px-1.5 py-1 text-[10px] text-popover-foreground shadow group-hover:block">
                <span className={cn('font-semibold', r.text)}>{e.countryName}</span> · {e.commodityName} · {Math.round(e.riskScore)}
              </span>
            </button>
          )
        })}

      {/* Shock epicenter markers */}
      {plottedShocks.map(({ shock, coords }) => {
        const p = project(coords.lat, coords.lng)
        const s = severityStyle(shock.severity)
        const isSel = shock.id === selectedShockId
        return (
          <button
            key={shock.id}
            className="group absolute flex h-5 w-5 items-center justify-center"
            style={{ left: `${p.x * 100}%`, top: `${p.y * 100}%`, transform: 'translate(-50%, -50%)' }}
            onClick={() => onSelectShock(shock.id)}
            title={`${shock.title} · ${shock.locationName}`}
          >
            <span
              className={cn(
                'pn-pulse-ring absolute inset-0 rounded-full',
                s.dot,
                isSel ? 'opacity-70' : 'opacity-50',
              )}
            />
            <span
              className={cn(
                'relative rounded-full ring-2 ring-background',
                s.dot,
                isSel ? 'h-3 w-3' : 'h-2.5 w-2.5',
              )}
            />
            {isSel && (
              <span className="pointer-events-none absolute left-1/2 top-5 z-30 -translate-x-1/2 whitespace-nowrap rounded border border-border bg-popover px-2 py-1 text-[10px] font-medium text-popover-foreground shadow-lg">
                {shock.locationName}
              </span>
            )}
          </button>
        )
      })}

      {/* Legend */}
      <div className="absolute bottom-2 left-2 flex flex-wrap items-center gap-x-3 gap-y-1 rounded-md border border-border/60 bg-background/70 px-2 py-1.5 text-[10px] backdrop-blur">
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-red-500" /> Severe</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-orange-500" /> High</span>
        <span className="flex items-center gap-1"><span className="h-2 w-2 rounded-full bg-amber-500" /> Moderate</span>
        <span className="hidden items-center gap-1 sm:flex"><span className="h-2 w-2 rounded-full bg-zinc-400" /> Exposure</span>
      </div>

      {/* Count + last-update */}
      <div className="absolute right-2 top-2 rounded-md border border-border/60 bg-background/70 px-2 py-1 text-[10px] backdrop-blur">
        <span className="font-mono-data text-muted-foreground">{plottedShocks.length} plotted</span>
        {selected && (
          <span className="ml-2 text-zinc-300">● {timeAgo(selected.shock.occurredAt)}</span>
        )}
      </div>

      {/* Empty hint */}
      {plottedShocks.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center text-xs text-muted-foreground">
          No geolocated shocks. Run ingestion to pull live signals.
        </div>
      )}
    </div>
  )
}
