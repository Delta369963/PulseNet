import { NextResponse } from 'next/server'

export const dynamic = 'force-dynamic'

/**
 * POST /api/scenarios/inject
 * Body: { url: string, context?: string }
 *
 * Future: accepts a news article URL (or raw text) and runs it through
 * the full ingestion + ripple pipeline as a custom scenario, allowing
 * operators to test "what if this article is real?" against the trade graph.
 *
 * Architecture hook is ready — wire to FastAPI /ingest with a custom source
 * when the custom-scenario UI is fully built.
 */
export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}))
  const { url, context } = body as { url?: string; context?: string }

  if (!url) {
    return NextResponse.json({ ok: false, error: 'url is required' }, { status: 400 })
  }

  // TODO: forward to FastAPI engine with source="CustomScenario" and the article URL.
  // The engine will fetch the URL, run it through RSS parser + LLM agent + ripple evaluator.
  return NextResponse.json({
    ok: false,
    note: 'Custom scenario injection is not yet implemented. The architecture hook is in place.',
    receivedUrl: url,
    receivedContext: context ?? null,
  })
}
