import type { Severity, RerouteStatus, ShockStatus, ShockType } from './types'

export function timeAgo(iso: string): string {
  const d = new Date(iso).getTime()
  const diff = Date.now() - d
  const min = Math.floor(diff / 60000)
  if (min < 1) return 'just now'
  if (min < 60) return `${min}m ago`
  const hr = Math.floor(min / 60)
  if (hr < 24) return `${hr}h ago`
  const day = Math.floor(hr / 24)
  if (day < 30) return `${day}d ago`
  return new Date(iso).toLocaleDateString()
}

export function fmtClock(d: Date): string {
  return d.toISOString().slice(11, 19) + ' UTC'
}

export function severityStyle(s: Severity) {
  switch (s) {
    case 'severe':
      return { label: 'SEVERE', dot: 'bg-red-500', text: 'text-red-400', border: 'border-red-500/40', bg: 'bg-red-500/10', ring: 'shadow-red-500/30' }
    case 'high':
      return { label: 'HIGH', dot: 'bg-orange-500', text: 'text-orange-400', border: 'border-orange-500/40', bg: 'bg-orange-500/10', ring: 'shadow-orange-500/30' }
    case 'moderate':
      return { label: 'MODERATE', dot: 'bg-amber-500', text: 'text-amber-400', border: 'border-amber-500/40', bg: 'bg-amber-500/10', ring: 'shadow-amber-500/30' }
    default:
      return { label: 'LOW', dot: 'bg-zinc-400', text: 'text-zinc-400', border: 'border-zinc-500/40', bg: 'bg-zinc-500/10', ring: 'shadow-zinc-500/30' }
  }
}

export function riskStyle(risk: number) {
  if (risk >= 75) return { bar: 'bg-red-500', text: 'text-red-400', label: 'CRITICAL' }
  if (risk >= 55) return { bar: 'bg-orange-500', text: 'text-orange-400', label: 'HIGH' }
  if (risk >= 40) return { bar: 'bg-amber-500', text: 'text-amber-400', label: 'ELEVATED' }
  return { bar: 'bg-emerald-500', text: 'text-emerald-400', label: 'MODERATE' }
}

export function confidenceStyle(conf: number) {
  if (conf >= 0.7) return { label: 'high', text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' }
  if (conf >= 0.5) return { label: 'moderate', text: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/30' }
  return { label: 'low', text: 'text-red-400', bg: 'bg-red-500/10', border: 'border-red-500/30' }
}

export function rerouteStatusStyle(status: RerouteStatus) {
  switch (status) {
    case 'approved':
      return { label: 'APPROVED', text: 'text-emerald-400', bg: 'bg-emerald-500/10', border: 'border-emerald-500/40' }
    case 'rejected':
      return { label: 'REJECTED', text: 'text-zinc-400', bg: 'bg-zinc-500/10', border: 'border-zinc-500/40' }
    case 'adjusted':
      return { label: 'ADJUSTED', text: 'text-amber-400', bg: 'bg-amber-500/10', border: 'border-amber-500/40' }
    default:
      return { label: 'PENDING', text: 'text-amber-300', bg: 'bg-amber-500/10', border: 'border-amber-500/30' }
  }
}

export function shockStatusStyle(status: ShockStatus) {
  switch (status) {
    case 'evaluated':
      return { label: 'EVALUATED', text: 'text-emerald-400', dot: 'bg-emerald-500' }
    case 'dismissed':
      return { label: 'DISMISSED', text: 'text-zinc-500', dot: 'bg-zinc-600' }
    default:
      return { label: 'NEW', text: 'text-amber-300', dot: 'bg-amber-400 pn-blink' }
  }
}

const SHOCK_TYPE_META: Record<ShockType, { label: string; icon: string }> = {
  earthquake: { label: 'Earthquake', icon: '⛰️' },
  flood: { label: 'Flood', icon: '🌊' },
  cyclone: { label: 'Cyclone', icon: '🌀' },
  conflict: { label: 'Conflict', icon: '⚔️' },
  port_closure: { label: 'Port Closure', icon: '⚓' },
  grid_failure: { label: 'Grid Failure', icon: '⚡' },
  border_restriction: { label: 'Border Restriction', icon: '🚧' },
  strike: { label: 'Strike', icon: '✊' },
}

export function shockTypeMeta(t: ShockType) {
  return SHOCK_TYPE_META[t] ?? { label: t, icon: '•' }
}

export function sourceStyle(source: string) {
  switch (source) {
    case 'USGS':
      return { text: 'text-cyan-300', bg: 'bg-cyan-500/10', border: 'border-cyan-500/30' }
    case 'GDACS':
      return { text: 'text-emerald-300', bg: 'bg-emerald-500/10', border: 'border-emerald-500/30' }
    case 'ACLED':
      return { text: 'text-orange-300', bg: 'bg-orange-500/10', border: 'border-orange-500/30' }
    case 'WebSearch':
      return { text: 'text-violet-300', bg: 'bg-violet-500/10', border: 'border-violet-500/30' }
    default:
      return { text: 'text-zinc-300', bg: 'bg-zinc-500/10', border: 'border-zinc-500/30' }
  }
}

/** Equirectangular projection to 0..1 plane. */
export function project(lat: number, lng: number): { x: number; y: number } {
  return { x: (lng + 180) / 360, y: (90 - lat) / 180 }
}
