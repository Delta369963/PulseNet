import { NextResponse } from 'next/server'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

// GET /api/stats — dashboard headline numbers.
export async function GET() {
  const [shocks, exposures, reroutes, pendingReroutes, decisions, countries, edges] = await Promise.all([
    db.shockEvent.count(),
    db.exposedRegion.count(),
    db.rerouteSuggestion.count(),
    db.rerouteSuggestion.count({ where: { status: 'pending' } }),
    db.adminDecision.count(),
    db.country.count(),
    db.tradeEdge.count(),
  ])
  // Low-confidence exposure count (monitoring density < 0.55) — the equity signal.
  const lowConfidence = await db.exposedRegion.count({ where: { monitoringDensity: { lt: 0.55 } } })
  return NextResponse.json({
    shocks,
    exposures,
    reroutes,
    pendingReroutes,
    decisions,
    countries,
    edges,
    lowConfidence,
  })
}
