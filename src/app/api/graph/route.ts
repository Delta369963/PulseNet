import { NextResponse } from 'next/server'
import { db } from '@/lib/db'

export const dynamic = 'force-dynamic'

// GET /api/graph — the static trade dependency graph for visualization.
export async function GET() {
  const [countries, commodities, edges] = await Promise.all([
    db.country.findMany({ orderBy: { name: 'asc' } }),
    db.commodity.findMany({ orderBy: { name: 'asc' } }),
    db.tradeEdge.findMany({ include: { supplier: true, consumer: true, commodity: true } }),
  ])
  return NextResponse.json({
    countries: countries.map((c) => ({
      code: c.code,
      name: c.name,
      region: c.region,
      lat: c.lat,
      lng: c.lng,
      monitoringDensity: c.monitoringDensity,
    })),
    commodities: commodities.map((c) => ({
      code: c.code,
      name: c.name,
      category: c.category,
      unit: c.unit,
    })),
    edges: edges.map((e) => ({
      supplier: e.supplier.code,
      consumer: e.consumer.code,
      commodity: e.commodity.code,
      volume: e.volume,
      share: e.share,
    })),
  })
}
