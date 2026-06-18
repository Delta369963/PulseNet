// Pure geo helpers — no DB access, so callers can batch-load countries once.

export function haversineKm(lat1: number, lng1: number, lat2: number, lng2: number): number {
  const R = 6371
  const dLat = ((lat2 - lat1) * Math.PI) / 180
  const dLng = ((lng2 - lng1) * Math.PI) / 180
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos((lat1 * Math.PI) / 180) *
      Math.cos((lat2 * Math.PI) / 180) *
      Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.sqrt(a))
}

export function nearestCountries(
  lat: number,
  lng: number,
  countries: { code: string; lat: number; lng: number }[],
  maxKm = 1500,
  limit = 2,
): string[] {
  return countries
    .map((c) => ({ code: c.code, d: haversineKm(lat, lng, c.lat, c.lng) }))
    .filter((x) => x.d <= maxKm)
    .sort((a, b) => a.d - b.d)
    .slice(0, limit)
    .map((x) => x.code)
}

/** Equirectangular projection of lat/lng onto a 0..1 x 0..1 plane (for SVG plotting). */
export function project(lat: number, lng: number): { x: number; y: number } {
  return { x: (lng + 180) / 360, y: (90 - lat) / 180 }
}
