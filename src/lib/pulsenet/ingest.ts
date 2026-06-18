import { db } from '@/lib/db'
import { llmComplete, parseJsonArray, webSearch } from './zai'
import { nearestCountries } from './geo'

// Live seismic feed (no key, public, GeoJSON). Updates continuously.
const USGS_URL = 'https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson'
const USGS_MIN_MAG = 4.5
const USGS_MAX_EVENTS = 6

const EVENT_TYPES = ['earthquake', 'flood', 'cyclone', 'conflict', 'port_closure', 'grid_failure', 'border_restriction', 'strike']
const SEVERITIES = ['low', 'moderate', 'high', 'severe']

function magSeverity(mag: number): string {
  if (mag >= 6.5) return 'severe'
  if (mag >= 5.5) return 'high'
  return 'moderate'
}

type UsgsFeature = {
  id: string
  properties: { mag: number; place: string; time: number; url: string; title: string }
  geometry: { coordinates: [number, number, number] } | null
}

async function fetchUsgs(): Promise<UsgsFeature[]> {
  try {
    const res = await fetch(USGS_URL, { cache: 'no-store' })
    if (!res.ok) return []
    const data = await res.json()
    const feats: UsgsFeature[] = (data.features || []).filter(
      (f: UsgsFeature) => (f.properties?.mag ?? 0) >= USGS_MIN_MAG && !!f.geometry?.coordinates,
    )
    feats.sort((a, b) => (b.properties?.mag ?? 0) - (a.properties?.mag ?? 0))
    return feats.slice(0, USGS_MAX_EVENTS)
  } catch (err) {
    console.error('[fetchUsgs] failed:', (err as Error).message)
    return []
  }
}

type ParsedNewsEvent = {
  title: string
  description: string
  type: string
  severity: string
  locationName: string
  lat: number | null
  lng: number | null
  countryCodes: string[]
  occurredAtHoursAgo: number
}

/** LLM ingestion filter: turns unstructured news snippets into structured shock events. */
async function parseNewsEvents(
  snippets: { name: string; snippet: string; url: string }[],
  countryCatalog: string,
): Promise<ParsedNewsEvent[]> {
  if (snippets.length === 0) return []
  const system = `You are PulseNet's Ingestion Filter agent. You read messy real-world news and extract only events that plausibly DISRUPT a supply chain for a critical commodity (LPG, diesel/petroleum, wheat/food, pharmaceuticals).

Return ONLY a JSON array — no markdown, no commentary, no prose. Each element must be exactly:
{"title": string, "description": string (1-2 sentences, supply-chain focused), "type": one of [${EVENT_TYPES.join(', ')}], "severity": one of [${SEVERITIES.join(', ')}], "locationName": string, "lat": number|null, "lng": number|null, "countryCodes": string[] (ONLY codes from the catalog below), "occurredAtHoursAgo": number}

Rules:
- Discard items that do not plausibly disrupt commodity supply.
- "countryCodes" must be a subset of the catalog codes. Use [] if none clearly match.
- "lat"/"lng" are the event's approximate coordinates (null if unknown).
- Keep descriptions concrete and actionable.`

  const user = `Country catalog (code: name):\n${countryCatalog}\n\nNews snippets:\n${snippets
    .map((s, i) => `${i + 1}. ${s.name}\n${s.snippet}\nURL: ${s.url}`)
    .join('\n\n')}\n\nExtract supply-chain disruption events as a JSON array.`

  const raw = await llmComplete(system, user)
  const parsed = parseJsonArray<ParsedNewsEvent>(raw)
  // sanity-filter
  return parsed.filter(
    (e) =>
      e &&
      typeof e.title === 'string' &&
      EVENT_TYPES.includes(e.type) &&
      SEVERITIES.includes(e.severity),
  )
}

export type IngestResult = {
  usgsFetched: number
  newsSearched: number
  inserted: number
  skipped: number
  insertedEvents: { id: string; title: string; source: string }[]
}

export async function runIngestion(): Promise<IngestResult> {
  const countries = await db.country.findMany()
  const countryCatalog = countries.map((c) => `${c.code}: ${c.name}`).join(', ')

  const result: IngestResult = {
    usgsFetched: 0,
    newsSearched: 0,
    inserted: 0,
    skipped: 0,
    insertedEvents: [],
  }

  const candidates: {
    externalId: string
    source: string
    sourceUrl: string | null
    title: string
    description: string
    type: string
    severity: string
    lat: number | null
    lng: number | null
    locationName: string
    countryCodes: string[]
    occurredAt: Date
    confidence: number
  }[] = []

  // --- 1. USGS seismic feed (structured — no LLM needed) ---
  const usgs = await fetchUsgs()
  result.usgsFetched = usgs.length
  for (const f of usgs) {
    const [lng, lat] = f.geometry!.coordinates
    const near = nearestCountries(lat, lng, countries)
    candidates.push({
      externalId: `usgs-${f.id}`,
      source: 'USGS',
      sourceUrl: f.properties.url || 'https://earthquake.usgs.gov/',
      title: `M ${f.properties.mag.toFixed(1)} earthquake — ${f.properties.place || 'unknown'}`,
      description: `Seismic event detected by USGS (magnitude ${f.properties.mag.toFixed(1)}). Potential disruption to nearby export terminals, refineries, or transport corridors if located near industrialized coastline.`,
      type: 'earthquake',
      severity: magSeverity(f.properties.mag),
      lat,
      lng,
      locationName: f.properties.place || 'Unknown location',
      countryCodes: near,
      occurredAt: new Date(f.properties.time),
      confidence: 0.9,
    })
  }

  // --- 2. Web-search news + LLM parse (the "unstructured chaos" agent) ---
  const newsQueries = [
    'port closure shipping disruption fuel supply news this week',
    'fuel shortage LPG diesel wheat supply chain disruption news',
  ]
  const seenUrls = new Set<string>()
  const snippets: { name: string; snippet: string; url: string }[] = []
  for (const q of newsQueries) {
    const results = await webSearch(q, 8)
    for (const r of results) {
      if (seenUrls.has(r.url)) continue
      seenUrls.add(r.url)
      snippets.push({ name: r.name, snippet: r.snippet, url: r.url })
      if (snippets.length >= 12) break
    }
    if (snippets.length >= 12) break
  }
  result.newsSearched = snippets.length

  const newsEvents = await parseNewsEvents(snippets, countryCatalog)
  for (const e of newsEvents) {
    const url = snippets.find((s) => s.name === e.title || e.title.includes(s.name.slice(0, 20)))?.url || null
    // deterministic external id from title + location
    const externalId = `web-${Buffer.from(`${e.title}|${e.locationName}`).toString('base64').slice(0, 18)}`
    candidates.push({
      externalId,
      source: 'WebSearch',
      sourceUrl: url,
      title: e.title,
      description: e.description,
      type: e.type,
      severity: e.severity,
      lat: typeof e.lat === 'number' ? e.lat : null,
      lng: typeof e.lng === 'number' ? e.lng : null,
      locationName: e.locationName,
      countryCodes: Array.isArray(e.countryCodes) ? e.countryCodes.filter((c) => countries.some((cc) => cc.code === c)) : [],
      occurredAt: new Date(Date.now() - (e.occurredAtHoursAgo || 12) * 3600 * 1000),
      confidence: 0.78,
    })
  }

  // --- 3. Dedupe + insert ---
  for (const c of candidates) {
    const existing = await db.shockEvent.findUnique({ where: { externalId: c.externalId } })
    if (existing) {
      result.skipped++
      continue
    }
    const created = await db.shockEvent.create({
      data: {
        externalId: c.externalId,
        source: c.source,
        sourceUrl: c.sourceUrl,
        title: c.title,
        description: c.description,
        type: c.type,
        severity: c.severity,
        lat: c.lat,
        lng: c.lng,
        locationName: c.locationName,
        countryCodes: JSON.stringify(c.countryCodes),
        occurredAt: c.occurredAt,
        confidence: c.confidence,
        status: 'new',
      },
    })
    result.inserted++
    result.insertedEvents.push({ id: created.id, title: created.title, source: created.source })
    await db.adminDecision.create({
      data: {
        action: 'ingest',
        summary: `Ingested ${c.source} event: ${c.title}`,
        actor: c.source === 'USGS' ? 'ingestion-agent' : 'ingestion-agent + LLM',
        metadata: JSON.stringify({ shockId: created.id, type: c.type, severity: c.severity }),
      },
    })
  }

  return result
}
