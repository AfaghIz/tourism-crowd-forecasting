import type { Hotel, Poi, RankedRecommendation } from '../api/api'

const RECENT_KEY = 'icc_recent_searches_v1'
const FAV_KEY = 'icc_favorites_v1'
const MAX_RECENT = 8

export type DiscoveryItem = { query: string; icon: string; subtitle?: string }

/** Curated landmarks for the “top 10” path UI — coordinates are approximate public POI locations. */
export type PopularIstanbulPlace = {
  id: string
  name: string
  subtitle: string
  lat: number
  lng: number
  /** Visual variant for ceramic-style icon (0–9). */
  sculpt: number
  /** Shown on the threaded map (emoji). */
  icon: string
  /** Placement on the abstract thread canvas (0–100 → % left / % top). */
  thread: [number, number]
}

export const POPULAR_ISTANBUL_TOP10: PopularIstanbulPlace[] = [
  {
    id: 'hagia',
    name: 'Hagia Sophia',
    subtitle: 'Byzantine icon',
    lat: 41.00858,
    lng: 28.98018,
    sculpt: 0,
    icon: '🏛️',
    thread: [18, 26]
  },
  {
    id: 'blue',
    name: 'Blue Mosque',
    subtitle: 'Sultanahmet',
    lat: 41.00541,
    lng: 28.97681,
    sculpt: 1,
    icon: '🕌',
    thread: [82, 16]
  },
  {
    id: 'topkapi',
    name: 'Topkapı Palace',
    subtitle: 'Ottoman court',
    lat: 41.01152,
    lng: 28.98325,
    sculpt: 2,
    icon: '🏰',
    thread: [46, 44]
  },
  {
    id: 'bazaar',
    name: 'Grand Bazaar',
    subtitle: 'Covered lanes',
    lat: 41.01069,
    lng: 28.96827,
    sculpt: 3,
    icon: '🛍️',
    thread: [22, 68]
  },
  {
    id: 'galata',
    name: 'Galata Tower',
    subtitle: 'Genoese landmark',
    lat: 41.02563,
    lng: 28.9741,
    sculpt: 4,
    icon: '🗼',
    thread: [74, 52]
  },
  {
    id: 'dolma',
    name: 'Dolmabahçe',
    subtitle: 'Bosphorus palace',
    lat: 41.03917,
    lng: 29.00056,
    sculpt: 5,
    icon: '🌊',
    thread: [58, 10]
  },
  {
    id: 'bridge',
    name: 'Bosphorus Bridge',
    subtitle: '15 July Martyrs Bridge',
    lat: 41.0444,
    lng: 29.0342,
    sculpt: 6,
    icon: '🌉',
    thread: [38, 86]
  },
  {
    id: 'spice',
    name: 'Spice Bazaar',
    subtitle: 'Mısır Çarşısı',
    lat: 41.01669,
    lng: 28.97053,
    sculpt: 7,
    icon: '🌶️',
    thread: [8, 42]
  },
  {
    id: 'maiden',
    name: 'Maiden’s Tower',
    subtitle: 'On the water',
    lat: 41.02129,
    lng: 29.00411,
    sculpt: 8,
    icon: '⚓',
    thread: [90, 36]
  },
  {
    id: 'taksim',
    name: 'Taksim Square',
    subtitle: 'İstiklal hub',
    lat: 41.03685,
    lng: 28.98503,
    sculpt: 9,
    icon: '🏙️',
    thread: [64, 74]
  }
]

/** Discovery dropdown — first six curated picks (names match search). */
export const TRENDING_ISTANBUL: DiscoveryItem[] = POPULAR_ISTANBUL_TOP10.slice(0, 6).map((p, i) => ({
  query: p.name,
  icon: ['🏛️', '🕌', '🏰', '🛍️', '🗼', '🏛️'][i] ?? '📍',
  subtitle: p.subtitle
}))

export const HIDDEN_GEMS: DiscoveryItem[] = [
  { query: 'Çamlıca Hill', icon: '🌿', subtitle: 'Wide city views' },
  { query: 'Kuzguncuk', icon: '🏘️', subtitle: 'Quiet neighborhood' },
  { query: 'Yıldız Park', icon: '🌳', subtitle: 'Green escape' },
  { query: 'Moda seaside', icon: '🌊', subtitle: 'Easy stroll' }
]

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export function recentSearchesGet(): string[] {
  try {
    const raw = localStorage.getItem(RECENT_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw) as unknown
    return Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : []
  } catch {
    return []
  }
}

export function recentSearchesAdd(query: string): void {
  const q = query.trim()
  if (q.length < 2) return
  const prev = recentSearchesGet().filter((x) => x.toLowerCase() !== q.toLowerCase())
  prev.unshift(q)
  try {
    localStorage.setItem(RECENT_KEY, JSON.stringify(prev.slice(0, MAX_RECENT)))
  } catch {
    /* ignore */
  }
}

export function favoritesGet(): Set<string> {
  try {
    const raw = localStorage.getItem(FAV_KEY)
    if (!raw) return new Set()
    const parsed = JSON.parse(raw) as unknown
    return new Set(Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === 'string') : [])
  } catch {
    return new Set()
  }
}

export function favoriteToggle(id: string): boolean {
  const set = favoritesGet()
  if (set.has(id)) {
    set.delete(id)
  } else {
    set.add(id)
  }
  try {
    localStorage.setItem(FAV_KEY, JSON.stringify([...set]))
  } catch {
    /* ignore */
  }
  return set.has(id)
}

export function favoriteHas(id: string): boolean {
  return favoritesGet().has(id)
}

const CAT_ICONS: Record<string, string> = {
  Landmark: '🏛️',
  Museum: '🏺',
  Viewpoint: '🌄',
  Shopping: '🛍️',
  Market: '🧺',
  Street: '🛤️',
  Hotel: '🏨'
}

export function categoryIcon(category: string, kind: 'hotel' | 'poi'): string {
  if (kind === 'hotel') return '🏨'
  return CAT_ICONS[category] ?? '📍'
}

/** Deterministic soft gradient from name (no external images). */
export function gradientThumbStyle(name: string): string {
  let h = 0
  for (let i = 0; i < name.length; i++) h = (h * 31 + name.charCodeAt(i)) >>> 0
  const hue = h % 360
  const hue2 = (hue + 38) % 360
  return `linear-gradient(135deg, hsla(${hue},70%,42%,0.95) 0%, hsla(${hue2},65%,28%,0.98) 100%)`
}

export function recommendationMicroBadges(rec: RankedRecommendation): string[] {
  const rawCrowd = String(rec.crowd_level_label ?? '').toLowerCase()
  const cat = String(rec.category ?? '')
  const dist = typeof rec.distance_km === 'number' ? rec.distance_km : parseFloat(String(rec.distance_km ?? ''))
  const name = String(rec.name ?? '').toLowerCase()
  const out: string[] = []
  const hour = new Date().getHours()

  if (hour >= 17 && hour < 21) out.push('Perfect for sunset')
  if (rawCrowd.includes('low') || rawCrowd === 'l') out.push('Quiet right now')
  if (rawCrowd.includes('high') || rawCrowd === 'h') out.push('Busy — avoid peak hours')
  if (/viewpoint|park|hill|bosphorus|shore/i.test(name) || cat === 'Viewpoint') out.push('Great hidden gem nearby')
  if (/museum|mosque|palace|tower|ayasofya|galata/i.test(name)) out.push('Popular with tourists')
  if (Number.isFinite(dist) && dist > 1.2 && dist < 4) out.push('Easy detour from center')
  if (out.length < 3 && cat === 'Market') out.push('Lively local energy')
  return [...new Set(out)].slice(0, 4)
}

export function bestTimeShort(crowdLevel: string): string {
  if (crowdLevel === 'High') return 'Early morning or late afternoon'
  if (crowdLevel === 'Medium') return 'Late morning or early evening'
  return 'Most windows feel relaxed'
}

export function crowdDotClass(crowdLabel: string): 'crowdDot--low' | 'crowdDot--mid' | 'crowdDot--high' {
  const s = crowdLabel.toLowerCase()
  if (s.includes('high') || s.includes('busy')) return 'crowdDot--high'
  if (s.includes('low') || s.includes('quiet')) return 'crowdDot--low'
  return 'crowdDot--mid'
}

export function hotelCardBadges(hotel: Hotel): string[] {
  const tags = hotel.tags?.slice(0, 2) ?? []
  const out = [...tags]
  if (hotel.rating >= 4.6) out.unshift('Loved by guests')
  return [...new Set(out)].slice(0, 3)
}

export function poiCardBadges(poi: Poi): string[] {
  const out: string[] = []
  if (/viewpoint|park/i.test(poi.category)) out.push('Scenic')
  if (/museum|landmark/i.test(poi.category)) out.push('Don’t rush')
  out.push(poi.category)
  return [...new Set(out)].slice(0, 3)
}
