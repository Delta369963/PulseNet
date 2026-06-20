'use client'

import { useState, useCallback, useRef } from 'react'
import { cn } from '@/lib/utils'
import {
  Terminal, ChevronDown, ChevronUp, X, RefreshCw,
  Download, Cpu, Globe2, AlertTriangle, CheckCircle2,
  Zap, Info,
} from 'lucide-react'

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

type FeedInfo = { name: string; enabled: boolean; maxItems: number | null; isGNews: boolean; url: string | null }
type ShockSummary = {
  id: string; title: string; type: string; severity: string; status: string
  countryCodes: string[]; locationName: string; exposureCount: number; rerouteCount: number
}

function useLog() {
  const [entries, setEntries] = useState<LogEntry[]>([])
  const counter = useRef(0)
  const push = useCallback((level: LogEntry['level'], msg: string) => {
    const now = new Date()
    const ts = now.toTimeString().slice(0, 8)
    setEntries(prev => [
      ...prev.slice(-99),
      { id: `${++counter.current}`, ts, level, msg },
    ])
  }, [])
  const clear = useCallback(() => setEntries([]), [])
  return { entries, push, clear }
}

export function DebugConsole({
  entries: externalEntries,
  onClear: externalClear,
}: {
  entries: LogEntry[]
  onClear: () => void
}) {
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<'log' | 'shocks' | 'feeds'>('log')
  const { entries: localEntries, push, clear } = useLog()
  const [feeds, setFeeds] = useState<FeedInfo[] | null>(null)
  const [shocks, setShocks] = useState<ShockSummary[] | null>(null)
  const [loading, setLoading] = useState<Record<string, boolean>>({})
  const ENGINE = process.env.NEXT_PUBLIC_ENGINE_URL ?? 'http://localhost:8000'

  const allEntries = [...externalEntries, ...localEntries].sort((a, b) => a.ts.localeCompare(b.ts))
  const recent = allEntries.slice(-80)

  // ── Fetch helpers ──────────────────────────────────────────────────────────
  async function fetchFeeds() {
    setLoading(l => ({ ...l, feeds: true }))
    try {
      const r = await fetch(`${ENGINE}/debug/feeds`)
      const d = await r.json()
      setFeeds(d.feeds)
      push('ok', `Loaded ${d.total} feed sources from engine`)
    } catch (e) {
      push('err', `Failed to load feeds: ${(e as Error).message}`)
    } finally {
      setLoading(l => ({ ...l, feeds: false }))
    }
  }

  async function fetchShocks() {
    setLoading(l => ({ ...l, shocks: true }))
    try {
      const r = await fetch(`${ENGINE}/debug/shocks?limit=30`)
      const d = await r.json()
      setShocks(d.shocks)
      push('ok', `Loaded ${d.total} shocks from engine`)
    } catch (e) {
      push('err', `Failed to load shocks: ${(e as Error).message}`)
    } finally {
      setLoading(l => ({ ...l, shocks: false }))
    }
  }

  async function ingestSource(name: string) {
    setLoading(l => ({ ...l, [`ingest_${name}`]: true }))
    push('info', `Ingesting from ${name}…`)
    try {
      const r = await fetch(`/api/ingest?source=${encodeURIComponent(name)}`, { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        push('ok', `${name}: inserted=${d.inserted} skipped=${d.skipped} news=${d.newsSearched} usgs=${d.usgsFetched}`)
      } else {
        push('warn', `${name}: ${d.error ?? 'unknown error'}`)
      }
    } catch (e) {
      push('err', `${name} ingest failed: ${(e as Error).message}`)
    } finally {
      setLoading(l => ({ ...l, [`ingest_${name}`]: false }))
      fetchShocks()
    }
  }

  async function evaluateShock(shockId: string, title: string) {
    setLoading(l => ({ ...l, [`eval_${shockId}`]: true }))
    push('info', `Re-evaluating: ${title.slice(0, 50)}…`)
    try {
      const r = await fetch(`${ENGINE}/debug/evaluate/${shockId}`, { method: 'POST' })
      const d = await r.json()
      if (d.ok) {
        const { tradeIntel } = d
        const ti = tradeIntel?.tradeIntel ?? {}
        push('ok', `${title.slice(0, 40)}: exposures=${d.exposuresCreated} reroutes=${d.reroutesCreated}`)
        if (ti.disrupted?.length) push('info', `  Trade intel: disrupted exports=[${ti.disrupted.join(',')}]`)
        if (ti.inbound?.length) push('info', `  Trade intel: inbound needs=[${ti.inbound.join(',')}]`)
        if (!ti.fromLLM) push('warn', `  Trade intel: used default fallback (LLM not reachable)`)
      } else {
        push('err', `Evaluate failed: ${d.error ?? 'unknown'}`)
      }
    } catch (e) {
      push('err', `Evaluate failed: ${(e as Error).message}`)
    } finally {
      setLoading(l => ({ ...l, [`eval_${shockId}`]: false }))
      fetchShocks()
    }
  }

  const SEV_COLOR: Record<string, string> = {
    low: 'text-zinc-400', moderate: 'text-amber-400',
    high: 'text-orange-400', severe: 'text-red-400',
  }

  return (
    <div
      className={cn(
        'fixed bottom-0 left-0 right-0 z-50 border-t border-border bg-background/98 backdrop-blur transition-all duration-200',
        open ? 'h-80' : 'h-8',
      )}
    >
      {/* ── Toggle bar ──────────────────────────────────────────────────────── */}
      <div
        className="flex h-8 cursor-pointer items-center gap-2 px-3 hover:bg-muted/20 select-none"
        onClick={() => setOpen(v => !v)}
      >
        <Terminal className="h-3.5 w-3.5 text-cyan-400" />
        <span className="font-mono text-[10px] font-semibold text-cyan-400/80">DEBUG CONSOLE</span>
        <span className="font-mono text-[10px] text-muted-foreground">{allEntries.length} entries</span>
        {allEntries.length > 0 && (
          <span className={cn('font-mono text-[10px]', LEVEL_COLOR[recent[recent.length - 1]?.level ?? 'info'])}>
            › {recent[recent.length - 1]?.msg.slice(0, 60)}
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <button
            onClick={(e) => { e.stopPropagation(); externalClear(); clear() }}
            className="rounded p-0.5 text-muted-foreground/50 hover:text-muted-foreground"
            title="Clear log"
          >
            <X className="h-3 w-3" />
          </button>
          {open ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" /> : <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />}
        </div>
      </div>

      {/* ── Panel body ──────────────────────────────────────────────────────── */}
      {open && (
        <div className="flex h-72 flex-col">
          {/* Tab bar */}
          <div className="flex items-center gap-0 border-b border-border/40 px-2">
            {(['log', 'shocks', 'feeds'] as const).map(t => (
              <button
                key={t}
                onClick={() => {
                  setTab(t)
                  if (t === 'feeds' && !feeds) fetchFeeds()
                  if (t === 'shocks' && !shocks) fetchShocks()
                }}
                className={cn(
                  'px-3 py-1 font-mono text-[10px] uppercase tracking-wider transition-colors',
                  tab === t
                    ? 'border-b border-cyan-400 text-cyan-400'
                    : 'text-muted-foreground hover:text-foreground',
                )}
              >
                {t === 'log' && <><Terminal className="mr-1 inline h-3 w-3" />Log</>}
                {t === 'shocks' && <><Cpu className="mr-1 inline h-3 w-3" />Shocks ({shocks?.length ?? '?'})</>}
                {t === 'feeds' && <><Globe2 className="mr-1 inline h-3 w-3" />Feeds ({feeds?.length ?? '?'})</>}
              </button>
            ))}
            <button
              onClick={() => { fetchFeeds(); fetchShocks() }}
              className="ml-auto mr-1 rounded p-0.5 text-muted-foreground/50 hover:text-cyan-400"
              title="Refresh all"
            >
              <RefreshCw className="h-3 w-3" />
            </button>
          </div>

          {/* ── LOG TAB ─────────────────────────────────────────────────────── */}
          {tab === 'log' && (
            <div className="flex-1 overflow-y-auto px-3 py-1 font-mono text-[10px]">
              {recent.length === 0 ? (
                <p className="text-muted-foreground/50 py-4 text-center">
                  No log entries. Switch to Shocks or Feeds to interact.
                </p>
              ) : (
                recent.map((e) => (
                  <div key={e.id} className="flex items-baseline gap-2 border-b border-border/15 py-0.5 last:border-none">
                    <span className="shrink-0 text-muted-foreground/50">{e.ts}</span>
                    <span className={cn('shrink-0 font-bold', LEVEL_COLOR[e.level])}>{LEVEL_LABEL[e.level]}</span>
                    <span className="text-foreground/80 break-all">{e.msg}</span>
                  </div>
                ))
              )}
            </div>
          )}

          {/* ── SHOCKS TAB ──────────────────────────────────────────────────── */}
          {tab === 'shocks' && (
            <div className="flex-1 overflow-y-auto">
              {loading.shocks ? (
                <div className="py-6 text-center font-mono text-[10px] text-muted-foreground">Loading shocks…</div>
              ) : !shocks ? (
                <div className="py-6 text-center">
                  <button onClick={fetchShocks} className="font-mono text-[10px] text-cyan-400 hover:underline">
                    Load shocks from engine
                  </button>
                </div>
              ) : (
                <table className="w-full font-mono text-[10px]">
                  <thead className="sticky top-0 bg-background border-b border-border/30">
                    <tr>
                      {['Title', 'Type', 'Sev', 'Codes', 'Exp', 'Rer', 'Status', 'Action'].map(h => (
                        <th key={h} className="px-2 py-1 text-left text-muted-foreground font-semibold">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {shocks.map(sh => (
                      <tr key={sh.id} className="border-b border-border/15 hover:bg-muted/10">
                        <td className="px-2 py-0.5 max-w-[180px] truncate text-foreground/80" title={sh.title}>
                          {sh.title.slice(0, 40)}
                        </td>
                        <td className="px-2 py-0.5 text-cyan-400/70">{sh.type}</td>
                        <td className={cn('px-2 py-0.5 font-bold', SEV_COLOR[sh.severity] ?? 'text-zinc-400')}>
                          {sh.severity.slice(0, 3).toUpperCase()}
                        </td>
                        <td className="px-2 py-0.5 text-zinc-400">
                          {sh.countryCodes.join(',') || sh.locationName?.slice(0, 10) || '—'}
                        </td>
                        <td className={cn('px-2 py-0.5', sh.exposureCount > 0 ? 'text-emerald-400' : 'text-red-400/70')}>
                          {sh.exposureCount}
                        </td>
                        <td className={cn('px-2 py-0.5', sh.rerouteCount > 0 ? 'text-emerald-400' : 'text-zinc-500')}>
                          {sh.rerouteCount}
                        </td>
                        <td className="px-2 py-0.5">
                          {sh.status === 'evaluated' ? (
                            <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                          ) : sh.status === 'new' ? (
                            <AlertTriangle className="h-3 w-3 text-amber-400" />
                          ) : (
                            <Info className="h-3 w-3 text-zinc-400" />
                          )}
                        </td>
                        <td className="px-2 py-0.5">
                          <button
                            disabled={!!loading[`eval_${sh.id}`]}
                            onClick={() => evaluateShock(sh.id, sh.title)}
                            className="rounded border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[9px] text-cyan-400 hover:bg-cyan-500/20 disabled:opacity-40 flex items-center gap-1"
                          >
                            {loading[`eval_${sh.id}`]
                              ? <RefreshCw className="h-2.5 w-2.5 animate-spin" />
                              : <Zap className="h-2.5 w-2.5" />}
                            Eval
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* ── FEEDS TAB ───────────────────────────────────────────────────── */}
          {tab === 'feeds' && (
            <div className="flex-1 overflow-y-auto">
              {loading.feeds ? (
                <div className="py-6 text-center font-mono text-[10px] text-muted-foreground">Loading feeds…</div>
              ) : !feeds ? (
                <div className="py-6 text-center">
                  <button onClick={fetchFeeds} className="font-mono text-[10px] text-cyan-400 hover:underline">
                    Load feed config from engine
                  </button>
                </div>
              ) : (
                <table className="w-full font-mono text-[10px]">
                  <thead className="sticky top-0 bg-background border-b border-border/30">
                    <tr>
                      {['Feed', 'Type', 'Max', 'Action'].map(h => (
                        <th key={h} className="px-2 py-1 text-left text-muted-foreground font-semibold">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {feeds.map(f => (
                      <tr key={f.name} className="border-b border-border/15 hover:bg-muted/10">
                        <td className="px-2 py-0.5 text-foreground/80">
                          {f.isGNews && <span className="mr-1 text-amber-400/60">[GN]</span>}
                          {f.name}
                        </td>
                        <td className="px-2 py-0.5 text-zinc-400">{f.isGNews ? 'google-news' : 'rss'}</td>
                        <td className="px-2 py-0.5 text-zinc-500">{f.maxItems ?? '—'}</td>
                        <td className="px-2 py-0.5">
                          <button
                            disabled={!!loading[`ingest_${f.name}`]}
                            onClick={() => ingestSource(f.name)}
                            className="rounded border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[9px] text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-40 flex items-center gap-1"
                          >
                            {loading[`ingest_${f.name}`]
                              ? <RefreshCw className="h-2.5 w-2.5 animate-spin" />
                              : <Download className="h-2.5 w-2.5" />}
                            Ingest
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
