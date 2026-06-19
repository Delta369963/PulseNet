import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

/**
 * POST /api/shocks/ingest
 *
 * Tries the FastAPI engine first (RSS-first, multi-agent Gemini consensus).
 * If the engine is offline, falls back to the legacy in-process TS pipeline
 * so the dashboard keeps working without the Python service running.
 */
export async function POST(req: Request) {
  const engineUrl = process.env.PULSENET_ENGINE_URL ?? 'http://localhost:8000'
  const body = await req.json().catch(() => ({}))
  const sourceQuery = body.source ? `?source=${encodeURIComponent(body.source)}` : ''

  // --- 1. Try FastAPI engine ---
  try {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 120_000)
    const res = await fetch(`${engineUrl}/ingest${sourceQuery}`, {
      method: 'POST',
      signal: ctrl.signal,
    })
    clearTimeout(timer)
    if (res.ok) {
      const body = await res.json()
      return NextResponse.json({ ok: true, ...body })
    }
    // Engine returned an error status — fall through to TS fallback.
    console.warn(`[ingest] engine returned ${res.status}, falling back to TS pipeline`)
  } catch (err) {
    // Engine not reachable (not started, crashed, etc.)
    console.warn('[ingest] engine unreachable, falling back to TS pipeline:', (err as Error).message)
  }

  // --- 2. TS fallback (legacy in-process pipeline) ---
  try {
    const { runIngestion } = await import('@/lib/pulsenet/ingest')
    const result = await runIngestion()
    return NextResponse.json({ ok: true, ...result })
  } catch (err) {
    console.error('[ingest] fallback error:', err)
    return NextResponse.json({ ok: false, error: (err as Error).message }, { status: 500 })
  }
}
