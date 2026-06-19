// Shared types for the PulseNet dashboard (match backend API shapes).

export type Severity = 'low' | 'moderate' | 'high' | 'severe'
export type ShockType =
  | 'earthquake'
  | 'flood'
  | 'cyclone'
  | 'conflict'
  | 'port_closure'
  | 'grid_failure'
  | 'border_restriction'
  | 'strike'
export type ShockStatus = 'new' | 'evaluated' | 'dismissed'
export type RerouteStatus = 'pending' | 'approved' | 'rejected' | 'adjusted'
export type DecisionAction = 'approve' | 'reject' | 'adjust' | 'dismiss' | 'ingest' | 'evaluate' | 'reset'

export type MonteCarloOutcome = {
  trials: number
  medianShortageWindow: number
  p95ShortageWindow: number
  successProb: number
}

export type ShockListItem = {
  id: string
  source: string
  sourceUrl: string | null
  title: string
  description: string
  type: ShockType
  severity: Severity
  lat: number | null
  lng: number | null
  locationName: string
  countryCodes: string[]
  occurredAt: string
  ingestedAt: string
  status: ShockStatus
  confidence: number
  exposureCount: number
  rerouteCount: number
}

export type ExposedRegion = {
  id: string
  shockId: string
  countryCode: string
  countryName: string
  region: string
  lat: number
  lng: number
  commodityCode: string
  commodityName: string
  exposurePath: string
  depth: number
  timeToShortageDays: number
  riskScore: number
  confidence: number
  cascadeConfidence: number // exposureShare × (1−recuperationFactor(SRI)) — prompt §4
  monitoringDensity: number
}


export type RerouteSuggestion = {
  id: string
  shockId: string
  exposedRegionId: string | null
  title: string
  rationale: string
  fromSupplier: string
  toSupplier: string
  commodityCode: string
  commodityName: string
  affectedRegion: string
  estimatedCostIncrease: number
  estimatedTimeToAddDays: number
  feasibilityScore: number
  confidence: number
  monteCarloOutcome: MonteCarloOutcome | null
  status: RerouteStatus
  adminNote: string | null
  decidedAt: string | null
  decidedBy: string | null
  createdAt: string
}

export type ShockDetail = {
  shock: Omit<ShockListItem, 'exposureCount' | 'rerouteCount'> & {
    exposures: ExposedRegion[]
    reroutes: RerouteSuggestion[]
  }
}

export type Decision = {
  id: string
  action: DecisionAction
  summary: string
  actor: string
  metadata: Record<string, unknown> | null
  createdAt: string
}

export type Stats = {
  shocks: number
  exposures: number
  reroutes: number
  pendingReroutes: number
  decisions: number
  countries: number
  edges: number
  lowConfidence: number
}

export type LedgerRow = {
  crisisId: string
  timestamp: string
  shockId: string | null
  sourceFeedUrl: string
  detectedShockVector: {
    lat?: number | null
    lng?: number | null
    severity?: string
    severityScore?: number
    initialAsset?: string
  }
  byzantineAgreementDelta: number // 0=identical, 1=total disagreement
  humanInTheLoopOverride: boolean
  authorizedByAdmin: string | null
}

export type GraphData = {

  countries: { code: string; name: string; region: string; lat: number; lng: number; monitoringDensity: number }[]
  commodities: { code: string; name: string; category: string; unit: string }[]
  edges: { supplier: string; consumer: string; commodity: string; volume: number; share: number }[]
}
