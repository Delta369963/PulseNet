import { PrismaClient } from '@prisma/client'

const db = new PrismaClient()

// Country code -> [name, region, lat, lng, monitoringDensity, gdpPerCapita, gridDensity, historicalVolatility]
const COUNTRIES = [
  ['IND', 'India', 'South Asia', 21.0, 79.0, 0.72, 2480, 0.62, 0.45],
  ['PAK', 'Pakistan', 'South Asia', 30.4, 69.3, 0.45, 1590, 0.40, 0.70],
  ['BGD', 'Bangladesh', 'South Asia', 23.7, 90.4, 0.40, 2690, 0.45, 0.60],
  ['LKA', 'Sri Lanka', 'South Asia', 7.9, 80.8, 0.38, 3830, 0.50, 0.78],
  ['SAU', 'Saudi Arabia', 'Middle East', 23.9, 45.1, 0.80, 28700, 0.85, 0.40],
  ['ARE', 'United Arab Emirates', 'Middle East', 23.4, 53.8, 0.85, 47800, 0.92, 0.32],
  ['QAT', 'Qatar', 'Middle East', 25.4, 51.2, 0.82, 80200, 0.93, 0.30],
  ['IRN', 'Iran', 'Middle East', 32.4, 53.7, 0.50, 4660, 0.55, 0.72],
  ['EGY', 'Egypt', 'North Africa', 26.8, 30.8, 0.62, 3770, 0.58, 0.62],
  ['CHN', 'China', 'East Asia', 35.0, 104.0, 0.78, 12720, 0.80, 0.35],
  ['JPN', 'Japan', 'East Asia', 36.2, 138.3, 0.92, 33800, 0.95, 0.30],
  ['KOR', 'South Korea', 'East Asia', 35.9, 127.8, 0.90, 32400, 0.94, 0.28],
  ['USA', 'United States', 'North America', 39.8, -98.6, 0.95, 76300, 0.96, 0.22],
  ['DEU', 'Germany', 'Europe', 51.2, 10.4, 0.93, 48700, 0.95, 0.20],
  ['FRA', 'France', 'Europe', 46.2, 2.2, 0.91, 40900, 0.94, 0.22],
  ['RUS', 'Russia', 'Eurasia', 61.5, 105.3, 0.55, 12200, 0.70, 0.58],
  ['UKR', 'Ukraine', 'Eurasia', 48.4, 31.2, 0.42, 4530, 0.48, 0.88],
  ['KEN', 'Kenya', 'East Africa', 0.0, 37.9, 0.43, 2090, 0.38, 0.66],
  ['NGA', 'Nigeria', 'West Africa', 9.1, 8.7, 0.41, 2160, 0.32, 0.72],
  ['ETH', 'Ethiopia', 'East Africa', 9.1, 40.5, 0.30, 1020, 0.25, 0.80],
] as const

// SRI formula mirrors compute/sri.py — weights (W1=0.5, W2=0.3, W3=0.2)
const GDP_LOG_MIN = Math.log(1000), GDP_LOG_MAX = Math.log(80000)
function computeSri(gdp: number, grid: number, vol: number): number {
  const n = Math.min(1, Math.max(0, (Math.log(Math.max(gdp,1)) - GDP_LOG_MIN) / (GDP_LOG_MAX - GDP_LOG_MIN)))
  return Math.round(Math.min(1, Math.max(0.05, 0.5*n + 0.3*grid - 0.2*vol)) * 1000) / 1000
}

const COMMODITIES = [
  ['LPG', 'Liquefied Petroleum Gas', 'energy', 'kt'],
  ['DIESEL', 'Refined Diesel / Petroleum', 'energy', 'kt'],
  ['WHEAT', 'Wheat', 'food', 'kt'],
  ['PHARMA', 'Pharmaceuticals', 'medical', 'tonnes'],
] as const

const EDGES: [string, string, string, number, number][] = [
  ['SAU','IND','LPG',4200,0.40], ['ARE','IND','LPG',2600,0.25], ['USA','IND','LPG',2100,0.20], ['QAT','IND','LPG',1000,0.10],
  ['SAU','PAK','LPG',980,0.55], ['ARE','BGD','LPG',620,0.50], ['USA','JPN','LPG',3400,0.30], ['ARE','JPN','LPG',2200,0.20],
  ['SAU','KEN','LPG',240,0.45], ['ARE','EGY','LPG',410,0.30],
  ['RUS','IND','DIESEL',5200,0.25], ['SAU','IND','DIESEL',6300,0.30], ['USA','IND','DIESEL',4200,0.20],
  ['RUS','PAK','DIESEL',1400,0.40], ['SAU','BGD','DIESEL',900,0.45], ['SAU','KEN','DIESEL',510,0.50],
  ['RUS','EGY','DIESEL',1200,0.20], ['SAU','EGY','DIESEL',2100,0.35], ['USA','JPN','DIESEL',3800,0.25],
  ['SAU','KOR','DIESEL',2900,0.35], ['RUS','CHN','DIESEL',6800,0.30], ['USA','CHN','DIESEL',2400,0.10],
  ['SAU','PAK','DIESEL',700,0.30],
  ['RUS','EGY','WHEAT',8800,0.50], ['UKR','EGY','WHEAT',4600,0.26], ['RUS','BGD','WHEAT',1900,0.40],
  ['IND','BGD','WHEAT',950,0.20], ['USA','JPN','WHEAT',3100,0.45], ['RUS','NGA','WHEAT',1400,0.30],
  ['USA','NGA','WHEAT',1100,0.25], ['RUS','KEN','WHEAT',780,0.35], ['UKR','KEN','WHEAT',440,0.20],
  ['RUS','PAK','WHEAT',1300,0.30], ['USA','EGY','WHEAT',1500,0.15], ['FRA','EGY','WHEAT',480,0.05],
  ['USA','KEN','WHEAT',320,0.20], ['IND','PAK','WHEAT',280,0.15],
  ['IND','KEN','PHARMA',4200,0.35], ['IND','NGA','PHARMA',3600,0.30], ['IND','ETH','PHARMA',2800,0.40],
  ['CHN','IND','PHARMA',5200,0.20], ['DEU','IND','PHARMA',6400,0.25], ['IND','BGD','PHARMA',5100,0.45],
  ['DEU','UKR','PHARMA',3200,0.60], ['FRA','UKR','PHARMA',1500,0.20], ['IND','UKR','PHARMA',800,0.15],
]

async function main() {
  console.log('Seeding PulseNet trade graph (live mode — no demo shocks)...')

  await db.adminDecision.deleteMany()
  await db.rerouteSuggestion.deleteMany()
  await db.exposedRegion.deleteMany()
  await db.shockEvent.deleteMany()
  await db.tradeEdge.deleteMany()
  await db.commodity.deleteMany()
  await db.country.deleteMany()
  await db.systemicConsensusLedger.deleteMany()

  for (const [code, name, region, lat, lng, md, gdp, grid, vol] of COUNTRIES) {
    await db.country.create({ data: { code, name, region, lat, lng, monitoringDensity: md,
      gdpPerCapita: gdp, gridDensity: grid, historicalVolatility: vol, sri: computeSri(gdp, grid, vol) } })
  }
  console.log(`  ✓ ${COUNTRIES.length} countries (with SRI)`)

  for (const [code, name, category, unit] of COMMODITIES) {
    await db.commodity.create({ data: { code, name, category, unit } })
  }
  console.log(`  ✓ ${COMMODITIES.length} commodities`)

  for (const [sup, con, com, vol, share] of EDGES) {
    const supplier = await db.country.findUnique({ where: { code: sup } })
    const consumer = await db.country.findUnique({ where: { code: con } })
    const commodity = await db.commodity.findUnique({ where: { code: com } })
    if (!supplier || !consumer || !commodity) continue
    await db.tradeEdge.create({ data: {
      supplierId: supplier.id, consumerId: consumer.id,
      commodityId: commodity.id, volume: vol, share,
    }})
  }
  console.log(`  ✓ ${EDGES.length} trade edges`)
  console.log('Seed complete. App starts in LIVE mode — use the Demo toggle to load replay scenarios.')
}

main()
  .catch((e) => { console.error(e); process.exit(1) })
  .finally(async () => { await db.$disconnect() })
