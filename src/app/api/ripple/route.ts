import { NextResponse } from 'next/server'
import { evaluateRipple } from '@/lib/pulsenet/ripple'

export const dynamic = 'force-dynamic'

// POST /api/ripple — run the ripple evaluator for a shock.
// Body: { shockId: string }
export async function POST(req: Request) {
  try {
    const { shockId } = await req.json().catch(() => ({}))
    if (!shockId) return NextResponse.json({ error: 'shockId required' }, { status: 400 })
    const result = await evaluateRipple(shockId)
    return NextResponse.json({ ok: true, ...result })
  } catch (err) {
    console.error('[ripple] error:', err)
    return NextResponse.json(
      { ok: false, error: (err as Error).message },
      { status: 500 },
    )
  }
}
