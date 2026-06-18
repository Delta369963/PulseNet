import { PrismaClient } from '@prisma/client'

const db = new PrismaClient()

// Country code -> { name, region, lat, lng, monitoringDensity }
const COUNTRIES = [
  // South Asia
  ['IND', 'India', 'South Asia', 21.0, 79.0, 0.72],
  ['PAK', 'Pakistan', 'South Asia', 30.4, 69.3, 0.45],
  ['BGD', 'Bangladesh', 'South Asia', 23.7, 90.4, 0.40],
  ['LKA', 'Sri Lanka', 'South Asia', 7.9, 80.8, 0.38],
  // Middle East
  ['SAU', 'Saudi Arabia', 'Middle East', 23.9, 45.1, 0.80],
  ['ARE', 'United Arab Emirates', 'Middle East', 23.4, 53.8, 0.85],
  ['QAT', 'Qatar', 'Middle East', 25.4, 51.2, 0.82],
  ['IRN', 'Iran', 'Middle East', 32.4, 53.7, 0.50],
  ['EGY', 'Egypt', 'North Africa', 26.8, 30.8, 0.62],
  // East Asia
  ['CHN', 'China', 'East Asia', 35.0, 104.0, 0.78],
  ['JPN', 'Japan', 'East Asia', 36.2, 138.3, 0.92],
  ['KOR', 'South Korea', 'East Asia', 35.9, 127.8, 0.90],
  // West
  ['USA', 'United States', 'North America', 39.8, -98.6, 0.95],
  ['DEU', 'Germany', 'Europe', 51.2, 10.4, 0.93],
  ['FRA', 'France', 'Europe', 46.2, 2.2, 0.91],
  // Eurasia
  ['RUS', 'Russia', 'Eurasia', 61.5, 105.3, 0.55],
  ['UKR', 'Ukraine', 'Eurasia', 48.4, 31.2, 0.42],
  // Africa
  ['KEN', 'Kenya', 'East Africa', -0.0, 37.9, 0.43],
  ['NGA', 'Nigeria', 'West Africa', 9.1, 8.7, 0.41],
  ['ETH', 'Ethiopia', 'East Africa', 9.1, 40.5, 0.30],
] as const

const COMMODITIES = [
  ['LPG', 'Liquefied Petroleum Gas', 'energy', 'kt'],
  ['DIESEL', 'Refined Diesel / Petroleum', 'energy', 'kt'],
  ['WHEAT', 'Wheat', 'food', 'kt'],
  ['PHARMA', 'Pharmaceuticals', 'medical', 'tonnes'],
] as const

// [supplier, consumer, commodity, volume, share]
const EDGES: [string, string, string, number, number][] = [
  // LPG
  ['SAU', 'IND', 'LPG', 4200, 0.40],
  ['ARE', 'IND', 'LPG', 2600, 0.25],
  ['USA', 'IND', 'LPG', 2100, 0.20],
  ['QAT', 'IND', 'LPG', 1000, 0.10],
  ['SAU', 'PAK', 'LPG', 980, 0.55],
  ['ARE', 'BGD', 'LPG', 620, 0.50],
  ['USA', 'JPN', 'LPG', 3400, 0.30],
  ['ARE', 'JPN', 'LPG', 2200, 0.20],
  ['SAU', 'KEN', 'LPG', 240, 0.45],
  ['ARE', 'EGY', 'LPG', 410, 0.30],
  // DIESEL
  ['RUS', 'IND', 'DIESEL', 5200, 0.25],
  ['SAU', 'IND', 'DIESEL', 6300, 0.30],
  ['USA', 'IND', 'DIESEL', 4200, 0.20],
  ['RUS', 'PAK', 'DIESEL', 1400, 0.40],
  ['SAU', 'BGD', 'DIESEL', 900, 0.45],
  ['SAU', 'KEN', 'DIESEL', 510, 0.50],
  ['RUS', 'EGY', 'DIESEL', 1200, 0.20],
  ['SAU', 'EGY', 'DIESEL', 2100, 0.35],
  ['USA', 'JPN', 'DIESEL', 3800, 0.25],
  ['SAU', 'KOR', 'DIESEL', 2900, 0.35],
  ['RUS', 'CHN', 'DIESEL', 6800, 0.30],
  // WHEAT
  ['RUS', 'EGY', 'WHEAT', 8800, 0.50],
  ['UKR', 'EGY', 'WHEAT', 4600, 0.26],
  ['RUS', 'BGD', 'WHEAT', 1900, 0.40],
  ['IND', 'BGD', 'WHEAT', 950, 0.20],
  ['USA', 'JPN', 'WHEAT', 3100, 0.45],
  ['RUS', 'NGA', 'WHEAT', 1400, 0.30],
  ['USA', 'NGA', 'WHEAT', 1100, 0.25],
  ['RUS', 'KEN', 'WHEAT', 780, 0.35],
  ['UKR', 'KEN', 'WHEAT', 440, 0.20],
  ['RUS', 'PAK', 'WHEAT', 1300, 0.30],
  ['USA', 'EGY', 'WHEAT', 1500, 0.15],
  ['FRA', 'EGY', 'WHEAT', 480, 0.05],
  ['USA', 'KEN', 'WHEAT', 320, 0.20],
  ['IND', 'PAK', 'WHEAT', 280, 0.15],
  ['USA', 'CHN', 'DIESEL', 2400, 0.10],
  ['SAU', 'PAK', 'DIESEL', 700, 0.30],
  // PHARMA
  ['IND', 'KEN', 'PHARMA', 4200, 0.35],
  ['IND', 'NGA', 'PHARMA', 3600, 0.30],
  ['IND', 'ETH', 'PHARMA', 2800, 0.40],
  ['CHN', 'IND', 'PHARMA', 5200, 0.20],
  ['DEU', 'IND', 'PHARMA', 6400, 0.25],
  ['IND', 'BGD', 'PHARMA', 5100, 0.45],
]

async function main() {
  console.log('Seeding PulseNet trade graph + replay events...')

  // Wipe (order matters for FKs)
  await db.adminDecision.deleteMany()
  await db.rerouteSuggestion.deleteMany()
  await db.exposedRegion.deleteMany()
  await db.shockEvent.deleteMany()
  await db.tradeEdge.deleteMany()
  await db.commodity.deleteMany()
  await db.country.deleteMany()

  // Countries
  for (const [code, name, region, lat, lng, md] of COUNTRIES) {
    await db.country.create({
      data: { code, name, region, lat, lng, monitoringDensity: md },
    })
  }
  console.log(`  ✓ ${COUNTRIES.length} countries`)

  // Commodities
  for (const [code, name, category, unit] of COMMODITIES) {
    await db.commodity.create({ data: { code, name, category, unit } })
  }
  console.log(`  ✓ ${COMMODITIES.length} commodities`)

  // Trade edges
  for (const [sup, con, com, vol, share] of EDGES) {
    const supplier = await db.country.findUnique({ where: { code: sup } })
    const consumer = await db.country.findUnique({ where: { code: con } })
    const commodity = await db.commodity.findUnique({ where: { code: com } })
    if (!supplier || !consumer || !commodity) continue
    await db.tradeEdge.create({
      data: {
        supplierId: supplier.id,
        consumerId: consumer.id,
        commodityId: commodity.id,
        volume: vol,
        share,
      },
    })
  }
  console.log(`  ✓ ${EDGES.length} trade edges`)

  // --- Replay event 1: Persian Gulf seismic event ---
  const e1 = await db.shockEvent.create({
    data: {
      externalId: 'replay-persian-gulf-2024',
      source: 'USGS',
      sourceUrl: 'https://earthquake.usgs.gov/',
      title: 'M 7.2 earthquake — Persian Gulf coastline (replay)',
      description:
        'Replay of a significant seismic event on the Iranian side of the Persian Gulf, near the Strait of Hormuz shipping lane. Disrupts LPG and refined-petroleum export terminals at Saudi, UAE, and Qatian ports; vessel traffic in the Strait temporarily halted.',
      type: 'earthquake',
      severity: 'severe',
      lat: 28.4,
      lng: 51.2,
      locationName: 'Persian Gulf / Strait of Hormuz',
      countryCodes: JSON.stringify(['IRN', 'SAU', 'ARE', 'QAT']),
      occurredAt: new Date(Date.now() - 1000 * 60 * 60 * 6),
      status: 'evaluated',
      confidence: 0.88,
    },
  })

  const exp1 = [
    { cc: 'IND', com: 'LPG', path: 'Strait of Hormuz halt → SAU/ARE/QAT export terminals → India (75% of LPG imports)', depth: 1, tts: 9, risk: 91, conf: 0.84, md: 0.72 },
    { cc: 'IND', com: 'DIESEL', path: 'Persian Gulf terminals → Saudi diesel exports → India (30% of diesel imports)', depth: 1, tts: 12, risk: 78, conf: 0.82, md: 0.72 },
    { cc: 'BGD', com: 'LPG', path: 'ARE export halt → Bangladesh (50% of LPG imports)', depth: 1, tts: 14, risk: 74, conf: 0.46, md: 0.40 },
    { cc: 'JPN', com: 'LPG', path: 'ARE/SAU halt → Japan (50% of LPG imports from Gulf)', depth: 1, tts: 16, risk: 68, conf: 0.88, md: 0.92 },
    { cc: 'KEN', com: 'DIESEL', path: 'SAU diesel halt → Kenya (50% of diesel imports)', depth: 1, tts: 10, risk: 81, conf: 0.40, md: 0.43 },
    { cc: 'KOR', com: 'DIESEL', path: 'SAU diesel halt → South Korea (35% of diesel imports)', depth: 1, tts: 15, risk: 66, conf: 0.85, md: 0.90 },
  ]
  for (const x of exp1) {
    const c = await db.country.findUnique({ where: { code: x.cc } })
    const com = await db.commodity.findUnique({ where: { code: x.com } })
    if (!c || !com) continue
    await db.exposedRegion.create({
      data: {
        shockId: e1.id,
        countryCode: c.code,
        countryName: c.name,
        region: c.region,
        lat: c.lat,
        lng: c.lng,
        commodityCode: com.code,
        commodityName: com.name,
        exposurePath: x.path,
        depth: x.depth,
        timeToShortageDays: x.tts,
        riskScore: x.risk,
        confidence: x.conf,
        monitoringDensity: x.md,
      },
    })
  }

  const ind = await db.country.findUnique({ where: { code: 'IND' } })
  const bgd = await db.country.findUnique({ where: { code: 'BGD' } })
  const ken = await db.country.findUnique({ where: { code: 'KEN' } })
  const kor = await db.country.findUnique({ where: { code: 'KOR' } })
  const indLpg = await db.exposedRegion.findFirst({ where: { shockId: e1.id, countryCode: 'IND', commodityCode: 'LPG' } })
  const indDie = await db.exposedRegion.findFirst({ where: { shockId: e1.id, countryCode: 'IND', commodityCode: 'DIESEL' } })
  const bgdLpg = await db.exposedRegion.findFirst({ where: { shockId: e1.id, countryCode: 'BGD', commodityCode: 'LPG' } })
  const kenDie = await db.exposedRegion.findFirst({ where: { shockId: e1.id, countryCode: 'KEN', commodityCode: 'DIESEL' } })
  const korDie = await db.exposedRegion.findFirst({ where: { shockId: e1.id, countryCode: 'KOR', commodityCode: 'DIESEL' } })

  await db.rerouteSuggestion.create({
    data: {
      shockId: e1.id,
      exposedRegionId: indLpg?.id,
      title: 'Reroute India LPG imports: Gulf → US Gulf Coast (direct)',
      rationale:
        'India already imports 20% of its LPG from the US. Scaling US cargoes to cover the 65% gap left by the Saudi/Emirati/Qatari halt avoids the Strait entirely. Marginally higher freight; resilient to a prolonged Gulf disruption.',
      fromSupplier: 'Saudi Arabia / UAE / Qatar',
      toSupplier: 'United States',
      commodityCode: 'LPG',
      commodityName: 'Liquefied Petroleum Gas',
      affectedRegion: 'India',
      estimatedCostIncrease: 14.5,
      estimatedTimeToAddDays: 18,
      feasibilityScore: 0.82,
      confidence: 0.86,
      monteCarloOutcome: JSON.stringify({ trials: 5000, medianShortageWindow: 0, p95ShortageWindow: 2, successProb: 0.78 }),
      status: 'approved',
      adminNote: 'Approved — instruct Indian Oil to scale US term contracts. ETA validation in 5 days.',
      decidedAt: new Date(Date.now() - 1000 * 60 * 60 * 2),
      decidedBy: 'administrator',
    },
  })
  await db.rerouteSuggestion.create({
    data: {
      shockId: e1.id,
      exposedRegionId: kenDie?.id,
      title: 'Reroute Kenya diesel: Saudi → UAE regional swap (low confidence)',
      rationale:
        'Partial Saudi-to-Kenya diesel flow could be re-routed via UAE storage at Fujairah. UAE terminals are themselves impaired; feasibility is uncertain. Flagged low-confidence because Kenyan downstream monitoring is sparse.',
      fromSupplier: 'Saudi Arabia',
      toSupplier: 'United Arab Emirates (regional)',
      commodityCode: 'DIESEL',
      commodityName: 'Refined Diesel / Petroleum',
      affectedRegion: 'Kenya',
      estimatedCostIncrease: 22.0,
      estimatedTimeToAddDays: 6,
      feasibilityScore: 0.41,
      confidence: 0.40,
      monteCarloOutcome: JSON.stringify({ trials: 5000, medianShortageWindow: 4, p95ShortageWindow: 9, successProb: 0.34 }),
      status: 'pending',
    },
  })
  await db.rerouteSuggestion.create({
    data: {
      shockId: e1.id,
      exposedRegionId: bgdLpg?.id,
      title: 'Reroute Bangladesh LPG: UAE → US spot cargoes',
      rationale:
        'Bangladesh sources 50% of LPG from the UAE; a spot-cargo program from the US Gulf covers the deficit but adds ~18 days transit. Equity note: Bangladesh monitoring density is low — manual verification recommended.',
      fromSupplier: 'United Arab Emirates',
      toSupplier: 'United States',
      commodityCode: 'LPG',
      commodityName: 'Liquefied Petroleum Gas',
      affectedRegion: 'Bangladesh',
      estimatedCostIncrease: 19.0,
      estimatedTimeToAddDays: 18,
      feasibilityScore: 0.58,
      confidence: 0.46,
      monteCarloOutcome: JSON.stringify({ trials: 5000, medianShortageWindow: 1, p95ShortageWindow: 8, successProb: 0.52 }),
      status: 'pending',
    },
  })
  await db.rerouteSuggestion.create({
    data: {
      shockId: e1.id,
      exposedRegionId: korDie?.id,
      title: 'Reroute South Korea diesel: Saudi → US + Kuwait blend',
      rationale:
        'South Korea has deep refining capacity; substituting Saudi diesel with US and Kuwaiti barrels preserves volume. Marginal cost increase; high feasibility.',
      fromSupplier: 'Saudi Arabia',
      toSupplier: 'United States + Kuwait',
      commodityCode: 'DIESEL',
      commodityName: 'Refined Diesel / Petroleum',
      affectedRegion: 'South Korea',
      estimatedCostIncrease: 8.5,
      estimatedTimeToAddDays: 12,
      feasibilityScore: 0.79,
      confidence: 0.84,
      monteCarloOutcome: JSON.stringify({ trials: 5000, medianShortageWindow: 0, p95ShortageWindow: 3, successProb: 0.74 }),
      status: 'rejected',
      adminNote: 'Rejected — domestic reserves sufficient for 21 days; defer to avoid spot-market price spike.',
      decidedAt: new Date(Date.now() - 1000 * 60 * 60 * 1),
      decidedBy: 'administrator',
    },
  })

  // --- Replay event 2: Black Sea port closure ---
  const e2 = await db.shockEvent.create({
    data: {
      externalId: 'replay-blacksea-2024',
      source: 'WebSearch',
      sourceUrl: 'https://www.reuters.com/',
      title: 'Black Sea grain port closures — conflict escalation (replay)',
      description:
        'Replay of a Black Sea port-disruption scenario: export terminals at Odesa and Russian Black Sea ports suspend wheat and diesel shipments following a security escalation. Directly severs Russia→Mediterranean/Africa wheat flows and Russia→South Asia diesel flows.',
      type: 'port_closure',
      severity: 'high',
      lat: 46.5,
      lng: 32.0,
      locationName: 'Black Sea / Odesa',
      countryCodes: JSON.stringify(['UKR', 'RUS']),
      occurredAt: new Date(Date.now() - 1000 * 60 * 60 * 30),
      status: 'new',
      confidence: 0.81,
    },
  })
  // Exposures for e2 will be computed live by the ripple evaluator when the admin clicks "Evaluate".
  // (Showcases the agent pipeline rather than pre-seeding everything.)

  // Audit-trail history
  await db.adminDecision.create({
    data: {
      action: 'ingest',
      summary: 'Ingested replay event: Persian Gulf seismic event (USGS)',
      actor: 'system',
      metadata: JSON.stringify({ shockId: e1.id }),
    },
  })
  await db.adminDecision.create({
    data: {
      action: 'ingest',
      summary: 'Ingested replay event: Black Sea port closure (WebSearch)',
      actor: 'system',
      metadata: JSON.stringify({ shockId: e2.id }),
    },
  })
  await db.adminDecision.create({
    data: {
      action: 'approve',
      summary: 'Approved reroute — India LPG via US Gulf Coast direct',
      actor: 'administrator',
      metadata: JSON.stringify({ shockId: e1.id, commodity: 'LPG', region: 'India' }),
    },
  })
  await db.adminDecision.create({
    data: {
      action: 'reject',
      summary: 'Rejected reroute — South Korea diesel (reserves sufficient)',
      actor: 'administrator',
      metadata: JSON.stringify({ shockId: e1.id, commodity: 'DIESEL', region: 'South Korea' }),
    },
  })

  console.log('  ✓ 2 replay shock events (1 evaluated with reroutes, 1 awaiting evaluation)')
  console.log('  ✓ audit-trail history seeded')
  console.log('Seed complete.')
}

main()
  .catch((e) => {
    console.error(e)
    process.exit(1)
  })
  .finally(async () => {
    await db.$disconnect()
  })
