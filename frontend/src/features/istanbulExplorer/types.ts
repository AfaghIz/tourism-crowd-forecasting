import type { PopularIstanbulPlace } from '../../ux/premiumHelpers'

export type ExplorerTag =
  | 'historical'
  | 'food'
  | 'shopping'
  | 'nature'
  | 'nightlife'
  | 'family'
  | 'rain'

export type RouteMode = 'avoid-crowds' | 'scenic' | 'fastest' | 'budget'

export type ThemeMode = 'day' | 'night'

export interface ExplorerPOI extends PopularIstanbulPlace {
  tags: ExplorerTag[]
  /** 0–100 — drives node scale & glow */
  popularity: number
  /** 1–100 perceived busyness */
  crowdScore: number
  bestWindow: string
  weatherFit: 'ideal' | 'ok' | 'carry-umbrella'
  alternatives: string[]
  accentKey: 'blue' | 'sand' | 'olive' | 'sunset'
  routeWeight: number
  sunsetPick?: boolean
  hiddenGem?: boolean
  microWeather: string
}

