import type { LatLng, SelectionKind } from '../domain/types'

export type Hotel = {
  id: string
  name: string
  district: string
  lat: number
  lng: number
  rating: number
  priceFrom: number
  tags: string[]
  blurb: string
  /** Optional photo URL for list thumbnails (e.g. Wikimedia Commons). */
  photoUrl?: string
}

export type Poi = {
  id: string
  name: string
  category: string
  lat: number
  lng: number
  blurb: string
  /** Optional photo URL for list thumbnails (e.g. Wikimedia Commons). */
  photoUrl?: string
}

export type SearchResult =
  | { kind: 'hotel'; hotel: Hotel }
  | { kind: 'poi'; poi: Poi }

export type ForecastResponse = {
  label: string
  kind: SelectionKind
  latlng: LatLng
  score: number
  level: 'Low' | 'Medium' | 'High'
  trend: string
  /** city_wide = notebook weekly index for whole Istanbul; demo = CSV missing */
  forecastScope?: string
  basisWeekStart?: string
  interpretation?: string
}

const API_BASE =
  (import.meta as any).env?.VITE_API_BASE_URL?.toString?.().trim?.() ||
  'http://localhost:8080'

function isWikimediaHttps(url: string): boolean {
  try {
    const u = new URL(url)
    if (u.protocol !== 'https:') return false
    const h = u.hostname
    return h === 'upload.wikimedia.org' || h.endsWith('.wikimedia.org')
  } catch {
    return false
  }
}

/**
 * Proxied Google Places photo (see ``GET /api/place-photo``). Safe Wikimedia ``fallbackUrl``
 * enables server redirect when the API key is unset or lookup fails.
 */
export function placePhotoProxyUrl(opts: {
  name: string
  lat?: number
  lng?: number
  fallbackUrl?: string
}): string {
  const url = new URL('/api/place-photo', API_BASE)
  url.searchParams.set('name', opts.name)
  if (
    opts.lat != null &&
    opts.lng != null &&
    Number.isFinite(opts.lat) &&
    Number.isFinite(opts.lng)
  ) {
    url.searchParams.set('lat', String(opts.lat))
    url.searchParams.set('lng', String(opts.lng))
  }
  if (opts.fallbackUrl && isWikimediaHttps(opts.fallbackUrl)) {
    url.searchParams.set('fallback', opts.fallbackUrl)
  }
  return url.toString()
}

async function getJson<T>(path: string, params?: Record<string, string | number | undefined>) {
  const url = new URL(path, API_BASE)
  if (params) {
    for (const [k, v] of Object.entries(params)) {
      if (v === undefined || v === null) continue
      url.searchParams.set(k, String(v))
    }
  }

  const res = await fetch(url.toString(), { headers: { Accept: 'application/json' } })
  if (!res.ok) throw new Error(`API request failed: ${res.status} ${res.statusText}`)
  return (await res.json()) as T
}

async function postJson<T>(path: string, body: unknown) {
  const url = new URL(path, API_BASE)
  const res = await fetch(url.toString(), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify(body)
  })
  if (!res.ok) throw new Error(`API request failed: ${res.status} ${res.statusText}`)
  return (await res.json()) as T
}

export async function listHotels(): Promise<Hotel[]> {
  return await getJson<Hotel[]>('/api/hotels')
}

export async function searchHotels(query: string, limit = 7): Promise<Hotel[]> {
  return await getJson<Hotel[]>('/api/hotels/search', { q: query, limit })
}

export async function searchPois(query: string, limit = 7): Promise<Poi[]> {
  return await getJson<Poi[]>('/api/pois/search', { q: query, limit })
}

export async function searchEverything(query: string, limit = 10): Promise<SearchResult[]> {
  const raw = await getJson<any[]>('/api/search', { q: query, limit })
  // Backend returns {kind, hotel? poi?}; map to the frontend union exactly.
  return raw.map((item) =>
    item.kind === 'hotel' ? ({ kind: 'hotel', hotel: item.hotel } as const) : ({ kind: 'poi', poi: item.poi } as const)
  )
}

export async function forecast(selection: { kind: SelectionKind; label: string; latlng: LatLng }, horizonWeeks = 4) {
  return await postJson<ForecastResponse>('/api/forecast', { ...selection, horizonWeeks })
}

/** One ranked POI row from the pandas pipeline (explanation engine output). */
export type RankedRecommendation = Record<string, unknown> & {
  name?: string
  score?: number
  distance_km?: number
  explanation?: string
  poi_id?: string
}

export type RecommendationApiResponse = {
  recommendations: RankedRecommendation[]
  itinerary: Array<Record<string, unknown>> | null
}

/**
 * Full recommendation pipeline: features, personalization, time-aware crowd, MMR, optional itinerary.
 * ``POST /api/recommendations`` — same contract as ``recommendation.pipeline.recommend``.
 */
export async function fetchRecommendations(body: {
  origin: LatLng
  /** ISO-8601, e.g. `2026-05-02T14:30:00` */
  timestamp?: string
  userProfile?: Record<string, unknown>
  radiusKm?: number
  topK?: number
  includeItinerary?: boolean
  /** Maps to backend ``allowed_categories`` (``category_clean`` filter). */
  allowedCategories?: string[]
}): Promise<RecommendationApiResponse> {
  return await postJson<RecommendationApiResponse>('/api/recommendations', body)
}
