import { POPULAR_ISTANBUL_TOP10 } from '../../ux/premiumHelpers'
import type { ExplorerPOI, ExplorerTag } from './types'

type Extra = {
  tags: ExplorerTag[]
  popularity: number
  crowdScore: number
  bestWindow: string
  weatherFit: ExplorerPOI['weatherFit']
  alternatives: string[]
  accentKey: ExplorerPOI['accentKey']
  routeWeight: number
  sunsetPick?: boolean
  hiddenGem?: boolean
  microWeather: string
}

const EXTRA: Record<string, Extra> = {
  hagia: {
    tags: ['historical', 'family', 'rain'],
    popularity: 98,
    crowdScore: 82,
    bestWindow: '08:00–10:30 · quieter openings',
    weatherFit: 'ok',
    alternatives: ['Chora Museum', 'Archaeology Museum'],
    accentKey: 'sand',
    routeWeight: 96,
    microWeather: 'Light breeze · UV moderate'
  },
  blue: {
    tags: ['historical', 'family'],
    popularity: 94,
    crowdScore: 78,
    bestWindow: 'Prayer gaps · mid-morning',
    weatherFit: 'ideal',
    alternatives: ['Süleymaniye Mosque'],
    accentKey: 'olive',
    routeWeight: 92,
    microWeather: 'Clear · comfortable'
  },
  topkapi: {
    tags: ['historical', 'shopping', 'family'],
    popularity: 91,
    crowdScore: 71,
    bestWindow: 'Opens · weekday mornings',
    weatherFit: 'ideal',
    alternatives: ['Archaeology Museum'],
    accentKey: 'sand',
    routeWeight: 88,
    microWeather: 'Pleasant · carry water'
  },
  bazaar: {
    tags: ['shopping', 'food', 'rain'],
    popularity: 89,
    crowdScore: 88,
    bestWindow: 'Weekday lunch · earlier slots',
    weatherFit: 'carry-umbrella',
    alternatives: ['Spice Bazaar'],
    accentKey: 'sunset',
    routeWeight: 72,
    microWeather: 'Humid indoors · AC pockets'
  },
  galata: {
    tags: ['nightlife', 'nature'],
    popularity: 87,
    crowdScore: 76,
    bestWindow: 'Golden hour ascent',
    weatherFit: 'ideal',
    alternatives: ['Karaköy waterfront'],
    accentKey: 'blue',
    routeWeight: 94,
    sunsetPick: true,
    microWeather: 'Wind picks up · layer up'
  },
  dolma: {
    tags: ['historical', 'nature'],
    popularity: 84,
    crowdScore: 54,
    bestWindow: 'Late afternoon facade light',
    weatherFit: 'ideal',
    alternatives: ['Ortaköy pier'],
    accentKey: 'blue',
    routeWeight: 99,
    sunsetPick: true,
    microWeather: 'Bosphorus mist possible'
  },
  bridge: {
    tags: ['nature', 'historical', 'family'],
    popularity: 88,
    crowdScore: 62,
    bestWindow: 'Golden hour · less haze after rain',
    weatherFit: 'ideal',
    alternatives: ['Fatih Sultan Mehmet Bridge', 'Ortaköy pier'],
    accentKey: 'blue',
    routeWeight: 82,
    sunsetPick: true,
    microWeather: 'Strait breeze · dress for wind'
  },
  spice: {
    tags: ['food', 'shopping', 'rain'],
    popularity: 83,
    crowdScore: 81,
    bestWindow: 'Late morning aromas',
    weatherFit: 'ok',
    alternatives: ['Kadıköy market hop'],
    accentKey: 'sunset',
    routeWeight: 68,
    microWeather: 'Spice heat indoors'
  },
  maiden: {
    tags: ['nature', 'nightlife'],
    popularity: 78,
    crowdScore: 48,
    bestWindow: 'Sunset ferry glow',
    weatherFit: 'ideal',
    alternatives: ['Üsküdar shore'],
    accentKey: 'blue',
    routeWeight: 97,
    sunsetPick: true,
    hiddenGem: true,
    microWeather: 'Sea chop · jacket'
  },
  taksim: {
    tags: ['nightlife', 'shopping', 'family'],
    popularity: 92,
    crowdScore: 90,
    bestWindow: 'Late evening energy',
    weatherFit: 'ok',
    alternatives: ['Karaköy bridges'],
    accentKey: 'sunset',
    routeWeight: 62,
    microWeather: 'Urban heat island'
  }
}

function build(): ExplorerPOI[] {
  return POPULAR_ISTANBUL_TOP10.map((p) => {
    const x = EXTRA[p.id]
    if (!x) throw new Error(`Missing explorer meta for ${p.id}`)
    return { ...p, ...x } satisfies ExplorerPOI
  })
}

export const EXPLORER_POIS: ExplorerPOI[] = build()

export const SIDEBAR_ROUTES = [
  { title: 'Top routes today', items: ['Sultanahmet core → Galata ridge', 'Bosphorus palaces · Ortaköy loop'] },
  {
    title: 'Least crowded alternatives',
    items: ['Maiden’s Tower · off-peak ferry', 'Dolmabahçe · weekday gardens']
  },
  { title: 'Best sunset spots', items: ['Galata Tower', 'Maiden’s Tower', 'Dolmabahçe façade'] },
  { title: 'Hidden gems', items: ['Bosphorus bridge viewpoints', 'Spice Bazaar upper lanes'] },
  {
    title: 'AI recommended path',
    items: ['Crowd-aware · scenic · 6 km gentle arc'],
    accent: true as const
  }
]
