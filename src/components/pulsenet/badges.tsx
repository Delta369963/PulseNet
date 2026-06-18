import { cn } from '@/lib/utils'
import {
  confidenceStyle,
  rerouteStatusStyle,
  severityStyle,
  shockStatusStyle,
  sourceStyle,
} from './helpers'
import type { RerouteStatus, Severity, ShockStatus } from './types'

export function SeverityBadge({ severity, className }: { severity: Severity; className?: string }) {
  const s = severityStyle(severity)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide',
        s.border,
        s.bg,
        s.text,
        className,
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', s.dot)} />
      {s.label}
    </span>
  )
}

export function ConfidenceBadge({ confidence, className }: { confidence: number; className?: string }) {
  const s = confidenceStyle(confidence)
  const pct = Math.round(confidence * 100)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide',
        s.border,
        s.bg,
        s.text,
        className,
      )}
      title={`Model confidence: ${pct}%`}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', s.text.replace('text-', 'bg-'))} />
      {s.label.toUpperCase()} · {pct}%
    </span>
  )
}

export function RerouteStatusBadge({ status, className }: { status: RerouteStatus; className?: string }) {
  const s = rerouteStatusStyle(status)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide',
        s.border,
        s.bg,
        s.text,
        className,
      )}
    >
      {s.label}
    </span>
  )
}

export function ShockStatusBadge({ status, className }: { status: ShockStatus; className?: string }) {
  const s = shockStatusStyle(status)
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border border-zinc-500/30 bg-zinc-500/10 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide',
        s.text,
        className,
      )}
    >
      <span className={cn('h-1.5 w-1.5 rounded-full', s.dot)} />
      {s.label}
    </span>
  )
}

export function SourceBadge({ source, className }: { source: string; className?: string }) {
  const s = sourceStyle(source)
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-mono-data tracking-wide',
        s.border,
        s.bg,
        s.text,
        className,
      )}
    >
      {source}
    </span>
  )
}

export function LowConfidenceFlag({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border border-red-500/40 bg-red-500/10 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-red-400',
        className,
      )}
      title="This region has low monitoring density. The AI's estimate here is weak — verify manually."
    >
      ⚠ LOW CONFIDENCE — VERIFY
    </span>
  )
}
