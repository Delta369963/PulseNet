import { NextResponse } from 'next/server'
import { runIngestion } from '@/lib/pulsenet/ingest'

export const dynamic = 'force-dynamic'

// POST /api/shocks/ingest — run the ingestion agent (USGS + web-search + LLM parse).
export async function POST() {
  try {
    const result = await runIngestion()
    return NextResponse.json({ ok: true, ...result })
  } catch (err) {
    console.error('[ingest] error:', err)
    return NextResponse.json(
      { ok: false, error: (err as Error).message },
      { status: 500 },
    )
  }
}
