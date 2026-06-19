import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

/**
 * GET /api/ledger?limit=25
 *
 * Returns recent consensus-ledger rows from the FastAPI engine.
 * Used by the Responsible-AI panel to surface Byzantine agreement deltas.
 * Returns empty ledger gracefully if the engine is offline.
 */
export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const limit = searchParams.get('limit') ?? '25'
  const engineUrl = process.env.PULSENET_ENGINE_URL ?? 'http://localhost:8000'

  try {
    const ctrl = new AbortController()
    setTimeout(() => ctrl.abort(), 8_000)
    const res = await fetch(`${engineUrl}/ledger?limit=${limit}`, { signal: ctrl.signal })
    if (res.ok) return NextResponse.json(await res.json())
  } catch {
    // Engine offline — return empty ledger rather than erroring the UI.
  }

  return NextResponse.json({ ledger: [] })
}
