/**
 * Demo seed helper — creates or removes the 2 validated replay scenarios.
 * Does NOT touch the trade graph (countries, commodities, edges).
 * Safe to call at runtime from the demo API route.
 */

import { db } from '@/lib/db'

function rfactor(sri: number): number {
  const scaled = Math.max(1, 1 + sri * 4)
  return Math.min(1, Math.max(0, 1 - 1 / scaled))
}
function cascadeConf(share: number, sri: number): number {
  return Math.round(share * (1 - rfactor(sri)) * 1000) / 1000
}

export async function seedDemo(): Promise<{ created: number }> {
  // Idempotent — skip if already seeded.
  const existing = await db.shockEvent.findUnique({ where: { externalId: 'replay-persian-gulf-2024' } })
  if (existing) return { created: 0 }

  // --- Replay 1: Persian Gulf ---
  const e1 = await db.shockEvent.create({
    data: {
      externalId: 'replay-persian-gulf-2024',
      source: 'USGS',
      sourceUrl: 'https://earthquake.usgs.gov/',
      title: 'M 7.2 earthquake — Persian Gulf coastline (replay)',
      description: 'Replay: significant seismic event on the Iranian side of the Persian Gulf near Strait of Hormuz. Disrupts LPG/petroleum terminals at Saudi, UAE and Qatari ports.',
      type: 'earthquake', severity: 'severe', lat: 28.4, lng: 51.2,
      locationName: 'Persian Gulf / Strait of Hormuz',
      countryCodes: JSON.stringify(['IRN', 'SAU', 'ARE', 'QAT']),
      occurredAt: new Date(Date.now() - 6 * 3600000),
      status: 'evaluated', confidence: 0.88,
    },
  })

  const exp1Data = [
    { cc: 'IND', com: 'LPG',   path: 'Strait of Hormuz halt → SAU/ARE/QAT terminals → India (75% of LPG imports)',   tts: 9,  risk: 91, conf: 0.84, md: 0.72, share: 0.75 },
    { cc: 'IND', com: 'DIESEL',path: 'Persian Gulf terminals → Saudi diesel exports → India (30% of diesel imports)', tts: 12, risk: 78, conf: 0.82, md: 0.72, share: 0.30 },
    { cc: 'BGD', com: 'LPG',   path: 'ARE export halt → Bangladesh (50% of LPG imports)',                             tts: 14, risk: 74, conf: 0.46, md: 0.40, share: 0.50 },
    { cc: 'JPN', com: 'LPG',   path: 'ARE/SAU halt → Japan (50% of LPG imports from Gulf)',                          tts: 16, risk: 68, conf: 0.88, md: 0.92, share: 0.50 },
    { cc: 'KEN', com: 'DIESEL',path: 'SAU diesel halt → Kenya (50% of diesel imports)',                               tts: 10, risk: 81, conf: 0.40, md: 0.43, share: 0.50 },
    { cc: 'KOR', com: 'DIESEL',path: 'SAU diesel halt → South Korea (35% of diesel imports)',                         tts: 15, risk: 66, conf: 0.85, md: 0.90, share: 0.35 },
  ]

  for (const x of exp1Data) {
    const c = await db.country.findUnique({ where: { code: x.cc } })
    const cm = await db.commodity.findUnique({ where: { code: x.com } })
    if (!c || !cm) continue
    await db.exposedRegion.create({ data: {
      shockId: e1.id, countryCode: c.code, countryName: c.name, region: c.region,
      lat: c.lat, lng: c.lng, commodityCode: cm.code, commodityName: cm.name,
      exposurePath: x.path, depth: 1, timeToShortageDays: x.tts, riskScore: x.risk,
      confidence: x.conf, cascadeConfidence: cascadeConf(x.share, c.sri), monitoringDensity: x.md,
    } })
  }

  const indLpg = await db.exposedRegion.findFirst({ where: { shockId: e1.id, countryCode: 'IND', commodityCode: 'LPG' } })
  const kenDie = await db.exposedRegion.findFirst({ where: { shockId: e1.id, countryCode: 'KEN', commodityCode: 'DIESEL' } })
  const bgdLpg = await db.exposedRegion.findFirst({ where: { shockId: e1.id, countryCode: 'BGD', commodityCode: 'LPG' } })
  const korDie = await db.exposedRegion.findFirst({ where: { shockId: e1.id, countryCode: 'KOR', commodityCode: 'DIESEL' } })

  await db.rerouteSuggestion.createMany({ data: [
    {
      shockId: e1.id, exposedRegionId: indLpg?.id,
      title: 'Reroute India LPG: Gulf → US Gulf Coast (direct)',
      rationale: 'India imports 20% from US. Scaling US cargoes covers the 65% gap and avoids the Strait entirely.',
      fromSupplier: 'Saudi Arabia / UAE / Qatar', toSupplier: 'United States',
      commodityCode: 'LPG', commodityName: 'Liquefied Petroleum Gas', affectedRegion: 'India',
      estimatedCostIncrease: 14.5, estimatedTimeToAddDays: 18, feasibilityScore: 0.82, confidence: 0.86,
      monteCarloOutcome: JSON.stringify({ trials: 5000, medianShortageWindow: 0, p95ShortageWindow: 2, successProb: 0.78 }),
      status: 'approved', adminNote: 'Approved — scale US term contracts. ETA 5 days.',
      decidedAt: new Date(Date.now() - 2 * 3600000), decidedBy: 'administrator',
    },
    {
      shockId: e1.id, exposedRegionId: kenDie?.id,
      title: 'Reroute Kenya diesel: Saudi → UAE regional swap (low confidence)',
      rationale: 'Partial Saudi-to-Kenya diesel via UAE Fujairah storage. UAE is itself impaired. Low confidence — sparse monitoring.',
      fromSupplier: 'Saudi Arabia', toSupplier: 'United Arab Emirates (regional)',
      commodityCode: 'DIESEL', commodityName: 'Refined Diesel / Petroleum', affectedRegion: 'Kenya',
      estimatedCostIncrease: 22.0, estimatedTimeToAddDays: 6, feasibilityScore: 0.41, confidence: 0.40,
      monteCarloOutcome: JSON.stringify({ trials: 5000, medianShortageWindow: 4, p95ShortageWindow: 9, successProb: 0.34 }),
      status: 'pending',
    },
    {
      shockId: e1.id, exposedRegionId: bgdLpg?.id,
      title: 'Reroute Bangladesh LPG: UAE → US spot cargoes',
      rationale: 'Bangladesh sources 50% LPG from UAE; US spot-cargo program covers deficit (+18d transit). Equity note: low monitoring density.',
      fromSupplier: 'United Arab Emirates', toSupplier: 'United States',
      commodityCode: 'LPG', commodityName: 'Liquefied Petroleum Gas', affectedRegion: 'Bangladesh',
      estimatedCostIncrease: 19.0, estimatedTimeToAddDays: 18, feasibilityScore: 0.58, confidence: 0.46,
      monteCarloOutcome: JSON.stringify({ trials: 5000, medianShortageWindow: 1, p95ShortageWindow: 8, successProb: 0.52 }),
      status: 'pending',
    },
    {
      shockId: e1.id, exposedRegionId: korDie?.id,
      title: 'Reroute South Korea diesel: Saudi → US + Kuwait blend',
      rationale: 'South Korea deep refining; US + Kuwaiti barrels preserve volume. Marginal cost; high feasibility.',
      fromSupplier: 'Saudi Arabia', toSupplier: 'United States + Kuwait',
      commodityCode: 'DIESEL', commodityName: 'Refined Diesel / Petroleum', affectedRegion: 'South Korea',
      estimatedCostIncrease: 8.5, estimatedTimeToAddDays: 12, feasibilityScore: 0.79, confidence: 0.84,
      monteCarloOutcome: JSON.stringify({ trials: 5000, medianShortageWindow: 0, p95ShortageWindow: 3, successProb: 0.74 }),
      status: 'rejected', adminNote: 'Rejected — domestic reserves sufficient 21 days.',
      decidedAt: new Date(Date.now() - 1 * 3600000), decidedBy: 'administrator',
    },
  ] })

  // --- Replay 2: Black Sea (unevaluated — run Evaluate Ripple yourself) ---
  await db.shockEvent.create({
    data: {
      externalId: 'replay-blacksea-2024',
      source: 'WebSearch', sourceUrl: 'https://www.reuters.com/',
      title: 'Black Sea grain port closures — conflict escalation (replay)',
      description: 'Replay: Black Sea port-disruption scenario. Odesa + Russian terminals suspend wheat/diesel following security escalation. Severs Russia→Mediterranean/Africa wheat flows.',
      type: 'port_closure', severity: 'high', lat: 46.5, lng: 32.0,
      locationName: 'Black Sea / Odesa',
      countryCodes: JSON.stringify(['UKR', 'RUS']),
      occurredAt: new Date(Date.now() - 30 * 3600000),
      status: 'new', confidence: 0.81,
    },
  })

  await db.adminDecision.createMany({ data: [
    { action: 'ingest', summary: 'Demo seeded: Persian Gulf seismic event (USGS)', actor: 'system', metadata: JSON.stringify({ mode: 'demo' }) },
    { action: 'ingest', summary: 'Demo seeded: Black Sea port closure (WebSearch)', actor: 'system', metadata: JSON.stringify({ mode: 'demo' }) },
    { action: 'approve', summary: 'Approved reroute — India LPG via US Gulf Coast direct', actor: 'administrator', metadata: JSON.stringify({ mode: 'demo' }) },
    { action: 'reject', summary: 'Rejected reroute — South Korea diesel (reserves sufficient)', actor: 'administrator', metadata: JSON.stringify({ mode: 'demo' }) },
  ] })

  return { created: 2 }
}

export async function clearDemo(): Promise<{ removed: number }> {
  const demos = await db.shockEvent.findMany({ where: { externalId: { startsWith: 'replay-' } } })
  if (demos.length === 0) return { removed: 0 }
  await db.shockEvent.deleteMany({ where: { externalId: { startsWith: 'replay-' } } })
  return { removed: demos.length }
}
