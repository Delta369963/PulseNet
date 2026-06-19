'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import {
  Activity,
  RefreshCw,
  Radio,
  Clock,
  PlayCircle,
  Loader2,
  Ban,
  ExternalLink,
  Scale,
  Link2,
} from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import { ThemeToggle } from '@/components/theme-toggle'
import { StatsBar } from '@/components/pulsenet/stats-bar'
import { ShockFeed } from '@/components/pulsenet/shock-feed'
import { ThreatMap } from '@/components/pulsenet/threat-map'

import { RerouteQueue } from '@/components/pulsenet/reroute-queue'
import { AuditTrail } from '@/components/pulsenet/audit-trail'
import { ResponsibleAIPanel } from '@/components/pulsenet/responsible-ai'
import { SeverityBadge, SourceBadge, ShockStatusBadge } from '@/components/pulsenet/badges'
import { ShockChainTrace } from '@/components/pulsenet/shock-chain-trace'
import { DebugConsole } from '@/components/pulsenet/debug-console'
import type { LogEntry } from '@/components/pulsenet/debug-console'

import { timeAgo, fmtClock, shockTypeMeta } from '@/components/pulsenet/helpers'
import type {
  Decision,
  GraphData,
  LedgerRow,
  RerouteSuggestion,
  ShockDetail,
  ShockListItem,
  Stats,
} from '@/components/pulsenet/types'


export default function PulseNetDashboard() {
  const [stats, setStats] = useState<Stats | null>(null)
  const [shocks, setShocks] = useState<ShockListItem[]>([])
  const [decisions, setDecisions] = useState<Decision[]>([])
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [detail, setDetail] = useState<ShockDetail | null>(null)
  const [loadingList, setLoadingList] = useState(true)
  const [loadingDetail, setLoadingDetail] = useState(false)
  const [ingesting, setIngesting] = useState(false)
  const [evaluating, setEvaluating] = useState(false)
  const [now, setNow] = useState<Date | null>(null) // null on SSR → avoids hydration mismatch; set after mount
  const [ledger, setLedger] = useState<LedgerRow[]>([])
  const [isDemo, setIsDemo] = useState(false)
  const [demoLoading, setDemoLoading] = useState(false)
  const [logEntries, setLogEntries] = useState<LogEntry[]>([])
  const detailReqId = useRef(0)

  const log = useCallback((level: LogEntry['level'], msg: string) => {
    const ts = new Date().toTimeString().slice(0, 8)
    setLogEntries((prev) => [...prev.slice(-99), { id: `${Date.now()}`, ts, level, msg }])
  }, [])



  const refreshAll = useCallback(async () => {
    // cache: 'no-store' bypasses the browser HTTP cache so newly-ingested
    // shocks always appear immediately after a POST /api/shocks/ingest call.
    const noCache = { cache: 'no-store' as RequestCache }
    const [s, d, decs] = await Promise.all([
      fetch('/api/stats', noCache).then((r) => r.json()).catch(() => null),
      fetch('/api/shocks', noCache).then((r) => r.json()).catch(() => ({ shocks: [] })),
      fetch('/api/decisions', noCache).then((r) => r.json()).catch(() => ({ decisions: [] })),
    ])

    const shockList = (d as { shocks: ShockListItem[] }).shocks || []
    if (s) setStats(s as Stats)
    setShocks(shockList)
    setDecisions((decs as { decisions: Decision[] }).decisions || [])
    setLoadingList(false)
    // Debug: show count in console so you can verify fetch is returning data
    log('info', `Feed refreshed — ${shockList.length} shock(s) in DB`)
  }, [log])


  const loadGraph = useCallback(async () => {
    const g = await fetch('/api/graph').then((r) => r.json()).catch(() => null)
    if (g) setGraph(g as GraphData)
  }, [])

  const loadLedger = useCallback(async () => {
    const res = await fetch('/api/ledger?limit=10').then((r) => r.json()).catch(() => null)
    if (res?.ledger) setLedger(res.ledger as LedgerRow[])
  }, [])

  const loadDemoStatus = useCallback(async () => {
    const res = await fetch('/api/demo').then((r) => r.json()).catch(() => null)
    if (res) setIsDemo(res.isDemo)
  }, [])

  const toggleDemo = useCallback(async () => {
    setDemoLoading(true)
    const action = isDemo ? 'clear' : 'seed'
    log('info', `${action === 'seed' ? 'Activating' : 'Clearing'} demo mode…`)
    try {
      const res = await fetch('/api/demo', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action }),
      }).then((r) => r.json())
      if (res?.ok) {
        setIsDemo(action === 'seed')
        const n = res.created ?? res.removed ?? 0
        log('ok', `Demo ${action === 'seed' ? 'loaded' : 'cleared'} — ${n} event(s).`)
        toast.success(action === 'seed' ? 'Demo mode activated — 2 replay scenarios loaded.' : 'Live mode — demo data cleared.')
        await refreshAll()
      } else {
        log('err', `Demo ${action} failed.`)
      }
    } catch {
      log('err', 'Demo toggle request failed.')
    } finally {
      setDemoLoading(false)
    }
  }, [isDemo, refreshAll, log])



  const refreshDetail = useCallback(async (id: string) => {
    const reqId = ++detailReqId.current
    setLoadingDetail(true)
    const res = await fetch(`/api/shocks/${id}`).then((r) => r.json()).catch(() => null)
    if (reqId !== detailReqId.current) return // stale
    if (res?.shock) setDetail(res as ShockDetail)
    setLoadingDetail(false)
  }, [])

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshAll()
    loadGraph()
    loadLedger()
    loadDemoStatus()
    log('info', 'PulseNet initialised — fetching data…')


    // Start the live clock only on the client (after hydration) to avoid
    // a server/client timestamp mismatch hydration error.
    setTimeout(() => setNow(new Date()), 0)


    const tick = setInterval(() => setNow(new Date()), 1000)
    const poll = setInterval(() => refreshAll(), 60000)
    // Refresh ledger every 5 min (it only changes when the engine runs).
    const ledgerPoll = setInterval(() => loadLedger(), 300_000)
    return () => {
      clearInterval(tick)
      clearInterval(poll)
      clearInterval(ledgerPoll)
    }
  }, [refreshAll, loadGraph, loadLedger])


  // Auto-select the most recent shock on first load.
  useEffect(() => {
    if (!selectedId && shocks.length > 0) {
      const first = shocks.find((s) => s.status !== 'dismissed') ?? shocks[0]
      const select = () => {
        setSelectedId(first.id)
        refreshDetail(first.id)
      }
      select()
    }
  }, [shocks, selectedId, refreshDetail])


  const onSelectShock = useCallback(
    (id: string) => {
      setSelectedId(id)
      refreshDetail(id)
    },
    [refreshDetail],
  )

  const runIngestion = useCallback(async () => {
    setIngesting(true)
    log('info', 'Ingestion started — USGS + RSS feeds + consensus agents…')
    toast.info('Ingestion agent running — polling USGS + web-search, LLM parsing signals…')
    try {
      const res = await fetch('/api/shocks/ingest', { method: 'POST' }).then((r) => r.json())
      if (res?.ok) {
        log('ok', `Ingested ${res.inserted} events · USGS:${res.usgsFetched} · news:${res.newsSearched} · deduped:${res.skipped}${res.consensusMode ? ' · dual-agent consensus' : ''}`)
        toast.success(
          `Ingested ${res.inserted} new event(s) · ${res.usgsFetched} USGS + ${res.newsSearched} news scanned · ${res.skipped} deduped.`,
        )

        await refreshAll()
        // Always select the top shock after a successful ingest so the user
        // can immediately see the newly-ingested event.
        if (res.inserted > 0 || !selectedId) {
          const fresh = await fetch('/api/shocks', { cache: 'no-store' }).then((r) => r.json())
          const list = (fresh?.shocks || []) as ShockListItem[]
          if (list.length > 0) {
            setSelectedId(list[0].id)
            refreshDetail(list[0].id)
          }
        }

      } else {
        toast.error(res?.error || 'Ingestion failed.')
      }
    } catch {
      toast.error('Ingestion request failed.')
    } finally {
      setIngesting(false)
    }
  }, [refreshAll, refreshDetail, selectedId])

  const evaluateRipple = useCallback(async () => {
    if (!selectedId) return
    setEvaluating(true)
    log('info', `Ripple eval starting — graph traversal + SRI cascade + Monte Carlo…`)
    toast.info('Ripple evaluator running — graph traversal + Monte Carlo + reroute generation…')
    try {
      const res = await fetch('/api/ripple', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ shockId: selectedId }),
      }).then((r) => r.json())
      if (res?.ok) {
        log('ok', `Ripple complete — ${res.exposuresCreated} exposures, ${res.reroutesCreated} reroutes${res.correlationId ? ' · cid:' + res.correlationId.slice(0,8) : ''}`)
        toast.success(
          `Ripple evaluated — ${res.exposuresCreated} exposed regions, ${res.reroutesCreated} reroutes proposed.`,
        )
        await Promise.all([refreshDetail(selectedId), refreshAll()])
      } else {
        log('err', res?.error || 'Evaluation failed')
        toast.error(res?.error || 'Evaluation failed.')
      }
    } catch {
      log('err', 'Ripple evaluation request failed')
      toast.error('Evaluation request failed.')
    } finally {
      setEvaluating(false)
    }
  }, [selectedId, refreshDetail, refreshAll, log])


  const dismissShock = useCallback(async () => {
    if (!selectedId) return
    await fetch(`/api/shocks/${selectedId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ status: 'dismissed' }),
    })
    toast('Shock dismissed.')
    await Promise.all([refreshDetail(selectedId), refreshAll()])
  }, [selectedId, refreshDetail, refreshAll])

  const decide = useCallback(
    async (id: string, action: 'approve' | 'reject' | 'adjust', note?: string) => {
      const res = await fetch('/api/decisions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ suggestionId: id, action, note }),
      }).then((r) => r.json())
      if (res?.ok) {
        const verb = action === 'approve' ? 'Reroute approved' : action === 'reject' ? 'Reroute rejected' : 'Reroute adjusted'
        toast.success(`${verb} — logged to audit trail. No autonomous execution.`)
        if (selectedId) await Promise.all([refreshDetail(selectedId), refreshAll()])
      } else {
        toast.error(res?.error || 'Decision failed.')
      }
    },
    [selectedId, refreshDetail, refreshAll],
  )

  const selShock = detail?.shock
  const exposures = detail?.shock.exposures ?? []
  const reroutes: RerouteSuggestion[] = detail?.shock.reroutes ?? []
  const selMeta = selShock ? shockTypeMeta(selShock.type) : null

  return (
    <div className="flex min-h-screen flex-col bg-background text-foreground">
      {/* Sticky header */}
      <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur supports-[backdrop-filter]:bg-background/70">
        <div className="mx-auto flex max-w-[1600px] items-center gap-3 px-3 py-2 sm:px-5">
          <div className="flex items-center gap-2.5">
            <div className="relative flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-400/15 ring-1 ring-zinc-400/30">
              <Activity className="h-5 w-5 text-zinc-300" />
              <span className="absolute -right-0.5 -top-0.5 flex h-2.5 w-2.5">
                <span className="pn-pulse-ring absolute inline-flex h-full w-full rounded-full bg-zinc-300" />
                <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-zinc-400" />
              </span>
            </div>
            <div className="leading-tight">
              <div className="flex items-center gap-2">
                <h1 className="text-base font-bold tracking-tight">PulseNet</h1>
                <span className="hidden rounded border border-zinc-400/30 bg-zinc-400/10 px-1.5 py-0.5 text-[9px] font-semibold text-zinc-300 sm:inline">
                  v0.9 · BETA
                </span>
              </div>
              <p className="hidden text-[10px] text-muted-foreground sm:block">
                Predictive decision-support · critical resource shortages
              </p>
            </div>
          </div>

          <div className="ml-2 hidden items-center gap-1.5 lg:flex">
            <span className="inline-flex items-center gap-1 rounded-md border border-zinc-400/30 bg-zinc-400/10 px-2 py-1 text-[10px] font-semibold text-zinc-300">
              <Radio className="h-3 w-3" /> FEEDS LIVE
            </span>
            <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted/40 px-2 py-1 font-mono-data text-[10px] text-muted-foreground">
              <Clock className="h-3 w-3" /> {now ? fmtClock(now) : '--:--:-- UTC'}
            </span>
            {stats && (
              <span className="inline-flex items-center gap-1 rounded-md border border-border bg-muted/40 px-2 py-1 text-[10px] text-muted-foreground">
                <Scale className="h-3 w-3" /> {stats.pendingReroutes} pending · {stats.lowConfidence} low-conf
              </span>
            )}
          </div>

          <div className="ml-auto flex items-center gap-1.5">
            <button
              onClick={toggleDemo}
              disabled={demoLoading}
              title={isDemo ? 'Demo mode — click to switch to Live' : 'Live mode — click to load validated replay scenarios'}
              className={cn(
                'hidden h-9 items-center gap-1.5 rounded-md border px-2.5 text-[10px] font-semibold tracking-wide transition-colors sm:inline-flex',
                isDemo
                  ? 'border-amber-500/40 bg-amber-500/10 text-amber-400 hover:bg-amber-500/20'
                  : 'border-zinc-400/30 bg-zinc-400/10 text-zinc-300 hover:bg-zinc-400/20',
              )}
            >
              {demoLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : null}
              {isDemo ? '⏪ DEMO' : '● LIVE'}
            </button>
            <Button
              disabled
              variant="outline"
              size="sm"
              title="Custom scenario injection — paste a news article URL to test the forward-chaining pipeline against any event. Architecture hook ready; coming soon."
              className="hidden h-9 opacity-50 sm:inline-flex"
            >
              <Link2 className="h-4 w-4" />
              <span className="hidden lg:inline">Inject Scenario</span>
            </Button>

            <Button
              onClick={runIngestion}
              disabled={ingesting}
              className="bg-zinc-500 text-white hover:bg-zinc-400"
            >
              {ingesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
              <span className="hidden sm:inline">Run Ingestion</span>
            </Button>
            <ThemeToggle />
          </div>

        </div>
      </header>

      {/* Main */}
      <main className="mx-auto w-full max-w-[1600px] flex-1 space-y-3 px-3 py-3 sm:px-5 sm:py-4">
        <StatsBar stats={stats} />

        {/* 3-column ops grid */}
        <div className="grid grid-cols-1 gap-3 lg:grid-cols-12">
          {/* Left: shock feed */}
          <div className="lg:col-span-3">
            <ShockFeed
              shocks={shocks}
              selectedId={selectedId}
              onSelect={onSelectShock}
              loading={loadingList}
            />
          </div>

          {/* Center: threat board + exposed regions */}
          <div className="space-y-3 lg:col-span-6">
            <div className="rounded-lg border border-border bg-card/50">
              <div className="flex flex-wrap items-center gap-2 border-b border-border px-3 py-2">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-semibold tracking-wide">GLOBAL THREAT BOARD</span>
                </div>
                {selShock ? (
                  <>
                    <span className="text-zinc-600">·</span>
                    <span className="text-base leading-none">{selMeta?.icon}</span>
                    <span className="line-clamp-1 text-xs font-medium">{selShock.title}</span>
                    <SeverityBadge severity={selShock.severity} />
                    <ShockStatusBadge status={selShock.status} />
                  </>
                ) : (
                  <span className="text-xs text-muted-foreground">Select a shock to trace its downstream ripple.</span>
                )}
                <div className="ml-auto flex items-center gap-1.5">
                  {selShock?.sourceUrl && (
                    <a
                      href={selShock.sourceUrl}
                      target="_blank"
                      rel="noreferrer"
                      className="inline-flex items-center gap-1 text-[10px] text-cyan-400 hover:underline"
                    >
                      <ExternalLink className="h-2.5 w-2.5" /> source
                    </a>
                  )}
                  {selShock && selShock.status !== 'dismissed' && (
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={dismissShock}
                      className="hidden h-7 sm:inline-flex"
                    >
                      <Ban className="h-3.5 w-3.5" /> Dismiss
                    </Button>
                  )}
                  <Button
                    size="sm"
                    onClick={evaluateRipple}
                    disabled={!selectedId || evaluating || selShock?.status === 'dismissed'}
                    className="h-7 bg-zinc-500 text-white hover:bg-zinc-400"
                  >
                    {evaluating ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <PlayCircle className="h-3.5 w-3.5" />
                    )}
                    {selShock?.status === 'evaluated' ? 'Re-evaluate' : 'Evaluate Ripple'}
                  </Button>
                </div>
              </div>

              {/* shock context strip */}
              {selShock && (
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1 border-b border-border px-3 py-1.5 text-[10px] text-muted-foreground">
                  <SourceBadge source={selShock.source} />
                  <span>📍 {selShock.locationName}</span>
                  <span>⏱ occurred {timeAgo(selShock.occurredAt)}</span>
                  <span>🌐 {selShock.countryCodes.length} supplier region(s) hit</span>
                  {selShock.lat != null && (
                    <span className="font-mono-data">
                      {selShock.lat.toFixed(2)}, {selShock.lng?.toFixed(2)}
                    </span>
                  )}
                  <span className="ml-auto line-clamp-1 max-w-[40%]">{selShock.description}</span>
                </div>
              )}

              <div className="p-2">
                <ThreatMap
                  shocks={shocks}
                  exposures={exposures}
                  selectedShockId={selectedId}
                  countries={graph?.countries ?? []}
                  onSelectShock={onSelectShock}
                />
              </div>
            </div>

            {/* Forward-chain detail trace — verbose step-by-step breakdown */}
            <div className="pn-scroll max-h-[52vh] overflow-y-auto rounded-lg">
              <ShockChainTrace
                shock={selShock ?? null}
                exposures={exposures}
                reroutes={reroutes}
                loading={loadingDetail}
              />
            </div>

          </div>

          {/* Right: reroute queue */}
          <div className="lg:col-span-3">
            <RerouteQueue
              reroutes={reroutes}
              sourceUrl={selShock?.sourceUrl ?? null}
              loading={loadingDetail}
              onDecide={decide}
            />
          </div>
        </div>

        {/* Responsible AI + audit */}
        <ResponsibleAIPanel lowConfidenceCount={stats?.lowConfidence ?? 0} ledger={ledger} />

        <AuditTrail decisions={decisions} loading={loadingList} />
      </main>

      {/* Debug console — fixed bottom bar (click to expand) */}
      <DebugConsole entries={logEntries} onClear={() => setLogEntries([])} />

      {/* Sticky footer */}
      <footer className="mt-auto border-t border-border bg-card/40 pb-8">

        <div className="mx-auto flex max-w-[1600px] flex-col gap-1 px-3 py-2.5 text-[10px] text-muted-foreground sm:flex-row sm:items-center sm:px-5">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5">
            <span className="font-semibold text-foreground/80">Data sources:</span>
            <span className="font-mono-data">USGS</span>
            <span className="text-zinc-600">·</span>
            <span className="font-mono-data">GDACS</span>
            <span className="text-zinc-600">·</span>
            <span className="font-mono-data">ACLED</span>
            <span className="text-zinc-600">·</span>
            <span className="font-mono-data">UN Comtrade</span>
            <span className="text-zinc-600">·</span>
            <span className="font-mono-data">OEC</span>
            <span className="text-zinc-600">·</span>
            <span className="font-mono-data">Reuters RSS</span>
          </div>
          <div className="sm:ml-auto flex flex-wrap items-center gap-x-2">
            <span className="inline-flex items-center gap-1 text-zinc-300">
              <span className="h-1.5 w-1.5 rounded-full bg-zinc-400" /> Decision-support only
            </span>
            <span className="text-zinc-600">·</span>
            <span>No autonomous execution</span>
            <span className="text-zinc-600">·</span>
            <span>Human-in-the-loop</span>
          </div>
        </div>
      </footer>
    </div>
  )
}
