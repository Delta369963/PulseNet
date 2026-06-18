import { NextResponse } from 'next/server'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

// GET /api/shocks/[id] — full detail: exposures + reroutes + monte carlo.
export async function GET(
  _req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  const shock = await db.shockEvent.findUnique({
    where: { id },
    include: {
      exposures: { orderBy: { riskScore: 'desc' } },
      reroutes: { orderBy: { createdAt: 'desc' } },
    },
  })
  if (!shock) return NextResponse.json({ error: 'not found' }, { status: 404 })
  return NextResponse.json({
    shock: {
      ...shock,
      countryCodes: JSON.parse(shock.countryCodes || '[]'),
      reroutes: shock.reroutes.map((r) => ({
        ...r,
        monteCarloOutcome: r.monteCarloOutcome ? JSON.parse(r.monteCarloOutcome) : null,
      })),
    },
  })
}

// PATCH /api/shocks/[id] — update status (e.g. dismiss).
export async function PATCH(
  req: Request,
  { params }: { params: Promise<{ id: string }> },
) {
  const { id } = await params
  const body = await req.json().catch(() => ({}))
  const status = body.status
  if (!['new', 'evaluated', 'dismissed'].includes(status)) {
    return NextResponse.json({ error: 'invalid status' }, { status: 400 })
  }
  const updated = await db.shockEvent.update({ where: { id }, data: { status } })
  if (status === 'dismissed') {
    await db.adminDecision.create({
      data: {
        action: 'dismiss',
        summary: `Dismissed shock: ${updated.title}`,
        actor: 'administrator',
        metadata: JSON.stringify({ shockId: id }),
      },
    })
  }
  return NextResponse.json({ ok: true, shock: updated })
}
