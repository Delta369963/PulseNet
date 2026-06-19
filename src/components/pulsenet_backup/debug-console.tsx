'use client'

import { useState } from 'react'
import { cn } from '@/lib/utils'
import { Terminal, ChevronDown, ChevronUp, X } from 'lucide-react'

export type LogEntry = {
  id: string
  ts: string
  level: 'info' | 'ok' | 'warn' | 'err'
  msg: string
}

const LEVEL_COLOR: Record<LogEntry['level'], string> = {
  info: 'text-cyan-400',
  ok:   'text-emerald-400',
  warn: 'text-amber-400',
  err:  'text-red-400',
}
const LEVEL_LABEL: Record<LogEntry['level'], string> = {
  info: 'INFO',
  ok:   'OK  ',
  warn: 'WARN',
  err:  'ERR ',
}

export function DebugConsole({
  entries,
  onClear,
}: {
  entries: LogEntry[]
  onClear: () => void
}) {
  const [open, setOpen] = useState(false)
  const recent = entries.slice(-30)

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/95 backdrop-blur transition-all',
        open ? 'h-52' : 'h-8',
      )}
    >
      {/* Toggle bar */}
      <div
        className="flex h-8 cursor-pointer items-center gap-2 px-3 hover:bg-muted/20"
        onClick={() => setOpen((v) => !v)}
      >
        <Terminal className="h-3.5 w-3.5 text-cyan-400" />
        <span className="font-mono text-[10px] font-semibold text-cyan-400/80">DEBUG CONSOLE</span>
        <span className="font-mono text-[10px] text-muted-foreground">{entries.length} entries</span>
        {entries.length > 0 && (
          <span className={cn('font-mono text-[10px]', LEVEL_COLOR[recent[recent.length - 1]?.level ?? 'info'])}>
            › {recent[recent.length - 1]?.msg.slice(0, 50)}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); onClear() }}
            className="rounded p-0.5 text-muted-foreground/50 hover:text-muted-foreground"
            title="Clear log"
          >
            <X className="h-3 w-3" />
          </button>
          {open ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />}
        </div>
      </div>

      {/* Log entries */}
      {open && (
        <div className="h-44 overflow-y-auto px-3 py-1 font-mono text-[10px]">
          {recent.length === 0 ? (
            <p className="text-muted-foreground/50 py-2">No log entries. Run ingestion or evaluate a ripple to see engine activity.</p>
          ) : (
            recent.map((e) => (
              <div key={e.id} className="flex items-baseline gap-2 py-0.5 border-b border-border/20 last:border-none">
                <span className="shrink-0 text-muted-foreground/50">{e.ts}</span>
                <span className={cn('shrink-0 font-bold', LEVEL_COLOR[e.level])}>{LEVEL_LABEL[e.level]}</span>
                <span className="text-foreground/80">{e.msg}</span>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  )
}
