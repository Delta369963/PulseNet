import { db } from '@/lib/db'
import { llmComplete, parseJsonArray } from './zai'

const SEVERITY_WEIGHT: Record<string, number> = {
  low: 0.2,
  moderate: 0.5,
  high: 0.75,
  severe: 1.0,
}

function randn(): number {
  // Box–Muller
  let u = 0
  let v = 0
  while (u === 0) u = Math.random()
  while (v === 0) v = Math.random()
  return Math.sqrt(-2 * Math.log(u)) * Math.cos(2 * Math.PI * v)
}

const round1 = (n: number) => Math.round(n * 10) / 10
const round2 = (n: number) => Math.round(n * 100) / 100

/** Monte Carlo: reroute supply arrives at TTA; shortage starts at TTS. Estimate shortage window. */
function monteCarlo(ttsDays: number, ttaDays: number, trials = 4000) {
  let success = 0
  const windows: number[] = []
  for (let i = 0; i < trials; i++) {
    const tta = Math.max(1, ttaDays * (0.75 + 0.5 * randn()))
    const tts = Math.max(1, ttsDays * (0.9 + 0.25 * randn()))
    const w = Math.max(0, tta - tts)
    windows.push(w)
    if (tta <= tts) success++
  }
  windows.sort((a, b) => a - b)
  return {
    trials,
    medianShortageWindow: round1(windows[Math.floor(trials * 0.5)]),
    p95ShortageWindow: round1(windows[Math.floor(trials * 0.95)]),
    successProb: round2(success / trials),
  }
}

type RerouteDraft = {
  tempId: string
  region: string
  commodity: string
  fromSuppliers: string
  toSupplier: string
  toSupplierShare: number
  exposurePct: number
  costIncrease: number
  timeToAdd: number
  feasibility: number
  confidence: number
  monitoringDensity: number
}

/** LLM enriches deterministic reroute drafts with a concrete, approvable title + rationale. */
async function enrichReroutes(drafts: RerouteDraft[]): Promise<Map<string, { title: string; rationale: string }>> {
  const out = new Map<string, { title: string; rationale: string }>()
  if (drafts.length === 0) return out
  const system = `You are PulseNet's Ripple Evaluator. For each proposed reroute, write a concise, specific, human-approvable title (<=90 chars) and rationale (2-3 sentences).
The rationale must name the alternative supplier, why it is viable given its existing share, and — if the affected region has LOW monitoring density (<0.55) — add an explicit equity caveat that a human should verify on the ground.
Return ONLY a JSON array (no markdown) of {"id": string, "title": string, "rationale": string}.`
  const user = `Reroute drafts:\n${drafts
    .map(
      (d) =>
        `id=${d.tempId} | region=${d.region} | commodity=${d.commodity} | from=${d.fromSuppliers} | to=${d.toSupplier} (existing share ${Math.round(d.toSupplierShare * 100)}%) | exposure=${Math.round(d.exposurePct)}% | cost+${d.costIncrease}% | +${d.timeToAdd}d | feasibility=${d.feasibility} | confidence=${d.confidence} | monitoringDensity=${d.monitoringDensity}`,
    )
    .join('\n')}`
  const raw = await llmComplete(system, user)
  const parsed = parseJsonArray<{ id: string; title: string; rationale: string }>(raw)
  for (const p of parsed) {
    if (p?.id && p.title && p.rationale) out.set(p.id, { title: p.title, rationale: p.rationale })
  }
  return out
}

export type EvalResult = {
  shockId: string
  exposuresCreated: number
  reroutesCreated: number
  note?: string
}

export async function evaluateRipple(shockId: string): Promise<EvalResult> {
  const shock = await db.shockEvent.findUnique({ where: { id: shockId } })
  if (!shock) throw new Error('Shock not found')

  // Clear any prior evaluation for this shock (idempotent re-runs).
  await db.rerouteSuggestion.deleteMany({ where: { shockId } })
  await db.exposedRegion.deleteMany({ where: { shockId } })

  const supplierCodes: string[] = JSON.parse(shock.countryCodes || '[]')
  if (supplierCodes.length === 0) {
    await db.shockEvent.update({ where: { id: shockId }, data: { status: 'evaluated' } })
    await db.adminDecision.create({
      data: {
        action: 'evaluate',
        summary: `Evaluated ripple for "${shock.title}" — no mapped supplier countries; no downstream exposure.`,
        actor: 'ripple-agent',
        metadata: JSON.stringify({ shockId }),
      },
    })
    return { shockId, exposuresCreated: 0, reroutesCreated: 0, note: 'No mapped supplier countries for this event.' }
  }

  const suppliers = await db.country.findMany({ where: { code: { in: supplierCodes } } })
  const supplierIds = suppliers.map((s) => s.id)
  const supplierNameList = suppliers.map((s) => s.name).join(' / ')

  // All edges where an affected country is the supplier.
  const edges = await db.tradeEdge.findMany({
    where: { supplierId: { in: supplierIds } },
    include: { consumer: true, commodity: true, supplier: true },
  })

  // Group by (consumer, commodity) and aggregate exposure.
  type Acc = {
    consumer: (typeof edges)[number]['consumer']
    commodity: (typeof edges)[number]['commodity']
    suppliers: { code: string; name: string; share: number }[]
    exposureShare: number
  }
  const map = new Map<string, Acc>()
  for (const e of edges) {
    const key = `${e.consumerId}:${e.commodityId}`
    if (!map.has(key))
      map.set(key, { consumer: e.consumer, commodity: e.commodity, suppliers: [], exposureShare: 0 })
    const acc = map.get(key)!
    acc.suppliers.push({ code: e.supplier.code, name: e.supplier.name, share: e.share })
    acc.exposureShare += e.share
  }

  const sevW = SEVERITY_WEIGHT[shock.severity] ?? 0.5
  const exposurePayloads = []
  for (const acc of map.values()) {
    const exposureShare = Math.min(1, acc.exposureShare)
    const tts = Math.max(2, Math.round(18 - 16 * exposureShare))
    const risk = Math.round(exposureShare * 70 + sevW * 30)
    const confidence = Math.max(0.3, Math.min(0.95, 0.3 + acc.consumer.monitoringDensity * 0.6))
    const supList = acc.suppliers.map((s) => `${s.name} (${Math.round(s.share * 100)}%)`).join(', ')
    const path = `${shock.title} → ${supList} export halt → ${acc.consumer.name} (${Math.round(exposureShare * 100)}% of ${acc.commodity.name} imports)`
    exposurePayloads.push({
      shockId,
      countryCode: acc.consumer.code,
      countryName: acc.consumer.name,
      region: acc.consumer.region,
      lat: acc.consumer.lat,
      lng: acc.consumer.lng,
      commodityCode: acc.commodity.code,
      commodityName: acc.commodity.name,
      exposurePath: path,
      depth: 1,
      timeToShortageDays: tts,
      riskScore: risk,
      confidence,
      monitoringDensity: acc.consumer.monitoringDensity,
      _exposureShare: exposureShare,
    })
  }
  exposurePayloads.sort((a, b) => b.riskScore - a.riskScore)

  // Persist exposures.
  const savedExposures = []
  for (const p of exposurePayloads) {
    const { _exposureShare, ...rest } = p
    savedExposures.push({ ...rest, _exposureShare, row: await db.exposedRegion.create({ data: rest }) })
  }

  // Build deterministic reroute drafts for the top exposures.
  const top = savedExposures.slice(0, 7)
  const drafts: RerouteDraft[] = []
  const draftLinks: { draft: RerouteDraft; exposureId: string; commodityCode: string; commodityName: string; fromSuppliers: string; toSupplierName: string }[] = []

  for (const exp of top) {
    const consumer = await db.country.findUnique({ where: { code: exp.row.countryCode } })
    const commodity = await db.commodity.findUnique({ where: { code: exp.row.commodityCode } })
    if (!consumer || !commodity) continue
    const alts = await db.tradeEdge.findMany({
      where: { consumerId: consumer.id, commodityId: commodity.id, supplierId: { notIn: supplierIds } },
      include: { supplier: true },
    })
    alts.sort((a, b) => b.share - a.share)
    for (const alt of alts.slice(0, 2)) {
      const tta = Math.max(3, Math.round(8 + (1 - alt.share) * 14))
      const cost = Math.round((10 + (1 - alt.share) * 25) * 10) / 10
      const feasibility = Math.max(0.25, Math.min(0.9, alt.share * 0.6 + 0.3))
      const confidence = Math.max(0.3, Math.min(0.92, exp.row.confidence * 0.8 + alt.share * 0.2))
      const tempId = `r-${drafts.length + 1}`
      const draft: RerouteDraft = {
        tempId,
        region: exp.row.countryName,
        commodity: exp.row.commodityName,
        fromSuppliers: supplierNameList,
        toSupplier: alt.supplier.name,
        toSupplierShare: alt.share,
        exposurePct: Math.round(exp._exposureShare * 100),
        costIncrease: cost,
        timeToAdd: tta,
        feasibility,
        confidence,
        monitoringDensity: exp.row.monitoringDensity,
      }
      drafts.push(draft)
      draftLinks.push({
        draft,
        exposureId: exp.row.id,
        commodityCode: commodity.code,
        commodityName: commodity.name,
        fromSuppliers: supplierNameList,
        toSupplierName: alt.supplier.name,
      })
    }
  }

  // LLM enrichment (graceful fallback to deterministic text if it fails).
  const enriched = await enrichReroutes(drafts)

  for (const link of draftLinks) {
    const mc = monteCarlo(
      // recompute tts for this exposure
      top.find((t) => t.row.id === link.exposureId)!.row.timeToShortageDays,
      link.draft.timeToAdd,
    )
    const ll = enriched.get(link.draft.tempId)
    const title =
      ll?.title ||
      `Reroute ${link.draft.region} ${link.commodityName}: ${link.fromSuppliers} → ${link.toSupplierName}`
    const rationale =
      ll?.rationale ||
      `Substitute ${link.draft.exposurePct}% of ${link.draft.region}'s ${link.commodityName} deficit with ${link.toSupplierName}, which already supplies ${Math.round(link.draft.toSupplierShare * 100)}%.${
        link.draft.monitoringDensity < 0.55
          ? ' Equity caveat: monitoring density is low — manual verification recommended.'
          : ''
      }`
    await db.rerouteSuggestion.create({
      data: {
        shockId,
        exposedRegionId: link.exposureId,
        title,
        rationale,
        fromSupplier: link.fromSuppliers,
        toSupplier: link.toSupplierName,
        commodityCode: link.commodityCode,
        commodityName: link.commodityName,
        affectedRegion: link.draft.region,
        estimatedCostIncrease: link.draft.costIncrease,
        estimatedTimeToAddDays: link.draft.timeToAdd,
        feasibilityScore: link.draft.feasibility,
        confidence: link.draft.confidence,
        monteCarloOutcome: JSON.stringify(mc),
        status: 'pending',
      },
    })
  }

  await db.shockEvent.update({ where: { id: shockId }, data: { status: 'evaluated' } })
  await db.adminDecision.create({
    data: {
      action: 'evaluate',
      summary: `Evaluated ripple for "${shock.title}" — ${savedExposures.length} exposed regions, ${drafts.length} reroutes proposed.`,
      actor: 'ripple-agent',
      metadata: JSON.stringify({ shockId, exposures: savedExposures.length, reroutes: drafts.length }),
    },
  })

  return {
    shockId,
    exposuresCreated: savedExposures.length,
    reroutesCreated: drafts.length,
  }
}
