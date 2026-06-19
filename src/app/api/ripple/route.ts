import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

/**
 * POST /api/ripple
 * Body: { shockId: string }
 *
 * Tries the FastAPI engine first (deterministic graph traversal + SRI cascade + Monte Carlo).
 * Falls back to the in-process TS ripple evaluator if the engine is offline.
 */
export async function POST(req: Request) {
  const { shockId } = await req.json().catch(() => ({}))
  if (!shockId) return NextResponse.json({ error: 'shockId required' }, { status: 400 })

  const engineUrl = process.env.PULSENET_ENGINE_URL ?? 'http://localhost:8000'

  // --- 1. Try FastAPI engine ---
  try {
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 90_000)
    const res = await fetch(`${engineUrl}/ripple`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ shockId }),
      signal: ctrl.signal,
    })
    clearTimeout(timer)
    if (res.ok) {
      const body = await res.json()
      return NextResponse.json({ ok: true, ...body })
    }
    if (res.status === 404) {
      const body = await res.json().catch(() => ({}))
      return NextResponse.json({ ok: false, error: body.detail ?? 'Shock not found' }, { status: 404 })
    }
    console.warn(`[ripple] engine returned ${res.status}, falling back to TS pipeline`)
  } catch (err) {
    console.warn('[ripple] engine unreachable, falling back to TS pipeline:', (err as Error).message)
  }

  // --- 2. TS fallback ---
  try {
    const { evaluateRipple } = await import('@/lib/pulsenet/ripple')
    const result = await evaluateRipple(shockId)
    return NextResponse.json({ ok: true, ...result })
  } catch (err) {
    console.error('[ripple] fallback error:', err)
    return NextResponse.json({ ok: false, error: (err as Error).message }, { status: 500 })
  }
}
