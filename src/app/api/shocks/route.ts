import { NextResponse } from 'next/server'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

// GET /api/shocks — list all shock events with exposure/reroute counts.
export async function GET() {
  const shocks = await db.shockEvent.findMany({
    orderBy: { ingestedAt: 'desc' },

    include: {
      _count: { select: { exposures: true, reroutes: true } },
    },
  })
  const data = shocks.map((s) => ({
    id: s.id,
    source: s.source,
    sourceUrl: s.sourceUrl,
    title: s.title,
    description: s.description,
    type: s.type,
    severity: s.severity,
    lat: s.lat,
    lng: s.lng,
    locationName: s.locationName,
    countryCodes: JSON.parse(s.countryCodes || '[]') as string[],
    occurredAt: s.occurredAt,
    ingestedAt: s.ingestedAt,
    status: s.status,
    confidence: s.confidence,
    exposureCount: s._count.exposures,
    rerouteCount: s._count.reroutes,
  }))
  return NextResponse.json({ shocks: data }, {
    headers: { 'Cache-Control': 'no-store, no-cache, must-revalidate' },
  })

}
