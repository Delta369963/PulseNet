import { NextResponse } from 'next/server'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

// GET /api/decisions — audit trail, newest first.
// Query params: ?actor=X (filter by actor), ?limit=N (default 100)
export async function GET(req: Request) {
  const { searchParams } = new URL(req.url)
  const actorFilter = searchParams.get('actor') || undefined
  const limit = Math.min(500, parseInt(searchParams.get('limit') || '100', 10))

  const decisions = await db.adminDecision.findMany({
    where: actorFilter ? { actor: actorFilter } : undefined,
    orderBy: { createdAt: 'desc' },
    take: limit,
  })
  return NextResponse.json({
    total: decisions.length,
    decisions: decisions.map((d) => ({
      ...d,
      metadata: d.metadata ? JSON.parse(d.metadata) : null,
    })),
  })
}

// POST /api/decisions — approve / reject / adjust a reroute suggestion (human-in-the-loop).
// Body: { suggestionId, action: 'approve'|'reject'|'adjust', note?, actor? }
export async function POST(req: Request) {
  const { suggestionId, action, note, actor } = await req.json().catch(() => ({}))
  if (!suggestionId || !['approve', 'reject', 'adjust'].includes(action)) {
    return NextResponse.json({ error: 'suggestionId + action(approve|reject|adjust) required' }, { status: 400 })
  }
  const suggestion = await db.rerouteSuggestion.findUnique({ where: { id: suggestionId } })
  if (!suggestion) return NextResponse.json({ error: 'suggestion not found' }, { status: 404 })

  const status = action === 'approve' ? 'approved' : action === 'reject' ? 'rejected' : 'adjusted'
  const updated = await db.rerouteSuggestion.update({
    where: { id: suggestionId },
    data: {
      status,
      adminNote: note ?? null,
      decidedAt: new Date(),
      decidedBy: actor || 'administrator',
    },
  })

  const verb = action === 'approve' ? 'Approved' : action === 'reject' ? 'Rejected' : 'Adjusted'
  await db.adminDecision.create({
    data: {
      action,
      summary: `${verb} reroute — ${suggestion.title}`,
      actor: actor || 'administrator',
      metadata: JSON.stringify({
        suggestionId,
        shockId: suggestion.shockId,
        region: suggestion.affectedRegion,
        commodity: suggestion.commodityName,
        note: note ?? null,
      }),
    },
  })

  return NextResponse.json({ ok: true, suggestion: updated })
}
