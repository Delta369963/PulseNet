import { NextResponse } from 'next/server'
import { db } from '@/lib/db'
import { seedDemo, clearDemo } from '@/lib/pulsenet/demo-seed'

export const dynamic = 'force-dynamic'

/** GET /api/demo — check if demo data is currently active. */
export async function GET() {
  const count = await db.shockEvent.count({ where: { externalId: { startsWith: 'replay-' } } })
  return NextResponse.json({ isDemo: count > 0, count })
}

/** POST /api/demo { action: 'seed' | 'clear' } */
export async function POST(req: Request) {
  const { action } = await req.json().catch(() => ({}))
  if (action === 'seed') {
    const result = await seedDemo()
    return NextResponse.json({ ok: true, ...result })
  }
  if (action === 'clear') {
    const result = await clearDemo()
    return NextResponse.json({ ok: true, ...result })
  }
  return NextResponse.json({ ok: false, error: 'action must be "seed" or "clear"' }, { status: 400 })
}
