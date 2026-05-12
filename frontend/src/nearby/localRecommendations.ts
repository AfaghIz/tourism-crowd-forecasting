import type { LatLng } from '../domain/types'
import type { RankedRecommendation } from '../api/api'
import { LOCAL_POIS_FOR_NEARBY } from '../api/mockApi'

function haversineKm(a: LatLng, b: { lat: number; lng: number }): number {
  const R = 6371
  const toRad = (d: number) => (d * Math.PI) / 180
  const dLat = toRad(b.lat - a.lat)
  const dLng = toRad(b.lng - a.lng)
  const lat1 = toRad(a.lat)
  const lat2 = toRad(b.lat)
  const h =
    Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLng / 2) ** 2
  return 2 * R * Math.asin(Math.min(1, Math.sqrt(h)))
}

/**
 * Rank bundled Istanbul POIs by straight-line distance from the user.
 * Used when POST /api/recommendations is unavailable or returns no rows.
 */
export function rankLocalPoisNear(origin: LatLng, categoryFilter: string, topK = 10): RankedRecommendation[] {
  let list = [...LOCAL_POIS_FOR_NEARBY]
  if (categoryFilter) {
    const filtered = list.filter((p) => p.category === categoryFilter)
    if (filtered.length > 0) list = filtered
  }

  return list
    .map((p) => ({ p, km: haversineKm(origin, p) }))
    .sort((a, b) => a.km - b.km)
    .slice(0, topK)
    .map(({ p, km }) => ({
      name: p.name,
      poi_id: p.id,
      lat: p.lat,
      lng: p.lng,
      category: p.category,
      distance_km: Math.round(km * 100) / 100,
      crowd_level_label: km < 1.5 ? 'Medium' : 'Low',
      explanation: p.blurb,
      score: Math.max(0, 1 - km / 25),
      photo_url: p.photoUrl
    }))
}
