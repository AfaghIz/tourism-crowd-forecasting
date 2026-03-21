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
}

export type Poi = {
  id: string
  name: string
  category: string
  lat: number
  lng: number
  blurb: string
}

export type SearchResult =
  | { kind: 'hotel'; hotel: Hotel }
  | { kind: 'poi'; poi: Poi }

const HOTELS: Hotel[] = [
  {
    id: 'sultanahmet-ottoman-suites',
    name: 'Ottoman Tiles Suites',
    district: 'Sultanahmet',
    lat: 41.0049,
    lng: 28.9769,
    rating: 4.7,
    priceFrom: 95,
    tags: ['heritage', 'sea view', 'tram nearby'],
    blurb: 'A calm, design-forward stay within walking distance of the historic core.'
  },
  {
    id: 'grand-bazaar-heritage',
    name: 'Grand Bazaar Heritage House',
    district: 'Fatih',
    lat: 41.0116,
    lng: 28.9683,
    rating: 4.6,
    priceFrom: 82,
    tags: ['shopping', 'cafes', 'family friendly'],
    blurb: 'Mosaic interiors, quick access to spice, souvenirs, and old Istanbul streets.'
  },
  {
    id: 'galata-aurora',
    name: 'Galata Aurora Hotel',
    district: 'Beyoğlu',
    lat: 41.0263,
    lng: 28.9734,
    rating: 4.8,
    priceFrom: 110,
    tags: ['nightlife', 'view', 'boutique'],
    blurb: 'Bright rooms and skyline vibes—perfect for exploring Galata after sunset.'
  },
  {
    id: 'karakoy-harbor',
    name: 'Karaköy Harbor Boutique',
    district: 'Karaköy',
    lat: 41.0259,
    lng: 28.9652,
    rating: 4.5,
    priceFrom: 89,
    tags: ['waterfront', 'cafes', 'romantic'],
    blurb: 'Modern comfort with a waterfront mood; ideal starting point for Bosphorus walks.'
  },
  {
    id: 'besiktas-bosphorus-view',
    name: 'Bosphorus View Residence',
    district: 'Beşiktaş',
    lat: 41.0462,
    lng: 29.0139,
    rating: 4.6,
    priceFrom: 103,
    tags: ['bosphorus', 'parking', 'quiet rooms'],
    blurb: 'A sleek base with easy transit access and gentle evening light.'
  },
  {
    id: 'uskudar-riverside',
    name: 'Üsküdar Riverside Lodge',
    district: 'Üsküdar',
    lat: 41.0291,
    lng: 29.0556,
    rating: 4.4,
    priceFrom: 76,
    tags: ['riverside', 'ferries', 'local'],
    blurb: 'Wander along the coast, grab breakfast by the water, and enjoy slower Istanbul.'
  },
  {
    id: 'kadikoy-moda-sea-breeze',
    name: 'Moda Sea Breeze Hotel',
    district: 'Kadıköy',
    lat: 40.9843,
    lng: 29.0428,
    rating: 4.7,
    priceFrom: 92,
    tags: ['lifestyle', 'food', 'fashion'],
    blurb: 'Style meets comfort in the heart of Kadıköy’s creative energy.'
  },
  {
    id: 'nisantasi-muse',
    name: 'Nişantaşı Muse Suites',
    district: 'Nişantaşı',
    lat: 41.0573,
    lng: 28.9935,
    rating: 4.6,
    priceFrom: 118,
    tags: ['luxury', 'shopping', 'design'],
    blurb: 'Upscale details, refined interiors, and a short walk to boutiques.'
  },
  {
    id: 'ortakoy-sunset-house',
    name: 'Ortaköy Sunset House',
    district: 'Ortaköy',
    lat: 41.0415,
    lng: 29.0348,
    rating: 4.5,
    priceFrom: 88,
    tags: ['bosphorus', 'views', 'art'],
    blurb: 'Sunset-facing charm near the water and culture spots.'
  }
]

const POIS: Poi[] = [
  {
    id: 'blue-mosque',
    name: 'Blue Mosque',
    category: 'Landmark',
    lat: 41.0055,
    lng: 28.9768,
    blurb: 'Iconic architecture and timeless silhouettes.'
  },
  {
    id: 'hagia-sophia',
    name: 'Hagia Sophia',
    category: 'Museum',
    lat: 41.0086,
    lng: 28.9802,
    blurb: 'A masterpiece of history, light, and scale.'
  },
  {
    id: 'galata-tower',
    name: 'Galata Tower',
    category: 'Viewpoint',
    lat: 41.025, // prototype accuracy is sufficient
    lng: 28.9744,
    blurb: 'Climb for skyline views across Istanbul.'
  },
  {
    id: 'grand-bazaar',
    name: 'Grand Bazaar',
    category: 'Shopping',
    lat: 41.0117,
    lng: 28.9682,
    blurb: 'A maze of craft, textiles, and souvenirs.'
  },
  {
    id: 'spice-bazaar',
    name: 'Spice Bazaar',
    category: 'Market',
    lat: 41.0179,
    lng: 28.965,
    blurb: 'Smells, spices, and vibrant vendor stalls.'
  },
  {
    id: 'istiklal',
    name: 'İstiklal Street',
    category: 'Street',
    lat: 41.0364,
    lng: 28.9822,
    blurb: 'Tram rides, boutiques, and late-night energy.'
  },
  {
    id: 'maiden-tower',
    name: "Maiden’s Tower",
    category: 'Landmark',
    lat: 41.0445,
    lng: 29.0516,
    blurb: 'A romantic island icon on the Bosphorus.'
  }
]

function sleep(ms: number) {
  return new Promise<void>((resolve) => setTimeout(resolve, ms))
}

function normalize(input: string) {
  return input.trim().toLowerCase()
}

function includesAll(haystack: string, query: string) {
  const h = haystack.toLowerCase()
  const q = query.toLowerCase()
  return h.includes(q)
}

export async function listHotels(): Promise<Hotel[]> {
  // TODO(api): replace mock list with a real endpoint (ex: GET /hotels?city=istanbul)
  await sleep(250)
  return HOTELS
}

export async function searchHotels(query: string, limit = 7): Promise<Hotel[]> {
  // TODO(api): replace with real search endpoint (ex: GET /hotels/search?q=...)
  await sleep(220)

  const q = normalize(query)
  const results = (q
    ? HOTELS.filter((h) => {
        const hay = `${h.name} ${h.district} ${h.tags.join(' ')}`
        return includesAll(hay, q)
      })
    : HOTELS.slice(0, limit)
  ).slice(0, limit)

  return results
}

export async function searchPois(query: string, limit = 7): Promise<Poi[]> {
  // TODO(api): replace with real POI endpoint (ex: GET /pois/search?q=...)
  await sleep(210)

  const q = normalize(query)
  const results = (q
    ? POIS.filter((p) => includesAll(`${p.name} ${p.category}`, q))
    : POIS.slice(0, limit)
  ).slice(0, limit)

  return results
}

export async function searchEverything(query: string, limit = 10): Promise<SearchResult[]> {
  // TODO(api): replace with a single endpoint that can return mixed results
  await sleep(240)

  const q = normalize(query)
  const hotelResults: SearchResult[] = (q
    ? (await searchHotels(q, limit)).map((h) => ({ kind: 'hotel', hotel: h }))
    : HOTELS.slice(0, 4).map((h) => ({ kind: 'hotel', hotel: h }))
  )
  const poiResults: SearchResult[] = (q
    ? (await searchPois(q, limit)).map((p) => ({ kind: 'poi', poi: p }))
    : POIS.slice(0, 6).map((p) => ({ kind: 'poi', poi: p }))
  )

  return [...hotelResults, ...poiResults].slice(0, limit)
}

export function toMapLatLng(lat: number, lng: number): LatLng {
  return { lat, lng }
}

export function selectionKindLabel(kind: SelectionKind): string {
  switch (kind) {
    case 'hotel':
      return 'Hotel'
    case 'location':
      return 'Current location'
    case 'poi':
      return 'Point of interest'
    case 'map':
      return 'Map point'
  }
}

