import './app.css'
import 'leaflet/dist/leaflet.css'

import { createMap } from './map/mapController'
import {
  searchEverything,
  fetchRecommendations,
  placePhotoProxyUrl,
  type Hotel,
  type Poi,
  type RankedRecommendation,
  type SearchResult,
  forecast
} from './api/api'
import type { LatLng, MapSelection, SelectionKind } from './domain/types'
import { createDirectionsOpener } from './nav/googleDirections'
import { rankLocalPoisNear } from './nearby/localRecommendations'
import { thumbUrlForPoiId } from './api/mockApi'
import {
  TRENDING_ISTANBUL,
  HIDDEN_GEMS,
  escapeHtml,
  recentSearchesAdd,
  recentSearchesGet,
  favoriteToggle,
  favoriteHas,
  categoryIcon,
  gradientThumbStyle,
  recommendationMicroBadges,
  bestTimeShort,
  crowdDotClass,
  hotelCardBadges,
  poiCardBadges,
  type DiscoveryItem,
} from './ux/premiumHelpers'

const DEFAULT_CENTER: LatLng = { lat: 41.0082, lng: 28.9784 }

/** Forecast API horizon when no UI control (matches former default “Next ~4 weeks”). */
const FORECAST_HORIZON_WEEKS = 4

/** YouTube clip ids for the small search-column preview stack (muted autoplay). */
const VR_CLIPS: readonly { id: string; iframeTitle: string }[] = [
  {
    id: 'Ko_pCVbUDJM',
    iframeTitle: 'Istanbul Bosphorous 360 VR Tour'
  },
  {
    id: 'x7kuv3rd5BY',
    iframeTitle: 'Istanbul travel video'
  },
  {
    id: 'cvmw60WqJ0k',
    iframeTitle: 'Istanbul travel video'
  },
  {
    id: '4ZXUSgLRNEU',
    iframeTitle: 'Istanbul travel video'
  },
  {
    id: 'JzTBLwZq_W0',
    iframeTitle: 'Istanbul travel video'
  },
  {
    id: 'ElRgievF8_0',
    iframeTitle: 'Istanbul travel video'
  }
]

/** Muted autoplay embeds (YouTube requires mute for autoplay). */
function sideVideoTilesHtml(clips: readonly { id: string; iframeTitle: string }[]): string {
  return clips
    .map((clip) => {
      const src = `https://www.youtube.com/embed/${encodeURIComponent(clip.id)}?autoplay=1&mute=1&loop=1&playlist=${encodeURIComponent(clip.id)}&playsinline=1&controls=0&modestbranding=1&rel=0`
      return `<div class="sideVideoTile"><iframe class="sideVideoIframe" src="${src}" title="${escapeHtml(clip.iframeTitle)}" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen" referrerpolicy="strict-origin-when-cross-origin"></iframe></div>`
    })
    .join('')
}

const SIDE_VIDEO_STACK_HTML = sideVideoTilesHtml(VR_CLIPS.slice(0, 4))
const SIDE_VIDEO_TRIP_STACK_HTML = sideVideoTilesHtml(VR_CLIPS.slice(4, 6))

const POI_CATEGORIES = [
  'all',
  'Landmark',
  'Museum',
  'Viewpoint',
  'Shopping',
  'Market',
  'Street'
] as const

type PoiCategoryBubble = (typeof POI_CATEGORIES)[number]

/** Distinctive line icons for trip-panel category chips (not generic emoji font). */
const CATEGORY_BUBBLE_SVG: Record<PoiCategoryBubble, string> = {
  all: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" aria-hidden="true"><path d="M12 2.5v3.5M12 18v3.5M2.5 12h3.5M18 12h3.5"/><path d="M5.2 5.2l2.5 2.5M16.3 16.3l2.5 2.5M5.2 18.8l2.5-2.5M16.3 7.7l2.5-2.5"/><circle cx="12" cy="12" r="1.75" fill="currentColor" stroke="none"/></svg>`,
  Landmark: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linejoin="round" aria-hidden="true"><path d="M4 20h16M5 20V11l7-6 7 6v9M8.5 20v-8M12 20V8.5M15.5 20v-8"/><path d="M12 6.5 9.5 11h5L12 6.5z"/></svg>`,
  Museum: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><rect x="5" y="6" width="14" height="12" rx="1.2"/><path d="M8 15.5 11 11l2.5 3 2.5-5 3 6.5"/></svg>`,
  Viewpoint: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linejoin="round" aria-hidden="true"><path d="M3 20h18L12 5.5 3 20z"/><circle cx="17.5" cy="7" r="2.3" fill="currentColor" stroke="none"/></svg>`,
  Shopping: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="M8.5 9V7.5a3.5 3.5 0 0 1 7 0V9"/><path d="M5.5 9h13l-1.2 10.5H6.7L5.5 9z"/><path d="M9 14h6" stroke-linecap="round"/></svg>`,
  Market: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linejoin="round" aria-hidden="true"><path d="M6 10h12l-1.1 9H7.1L6 10z"/><path d="M9 10V8a3 3 0 0 1 6 0v2"/><ellipse cx="12" cy="7.5" rx="5" ry="2.5"/><path d="M8 14h8" stroke-linecap="round"/></svg>`,
  Street: `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 19h16L14.2 4H9.8L4 19z"/><path d="M12 7.5v11" stroke-dasharray="2.2 3"/></svg>`
}

const CATEGORY_BUBBLES_HTML = POI_CATEGORIES.map((c) => {
  const icon = CATEGORY_BUBBLE_SVG[c]
  const label = c === 'all' ? 'All' : c
  const isAll = c === 'all'
  return `<button type="button" class="categoryBubble${isAll ? ' isActive' : ''}" data-category="${c}" aria-pressed="${String(isAll)}" aria-label="Category: ${label}"><span class="categoryBubble__ring" aria-hidden="true"><span class="categoryBubble__ic">${icon}</span></span><span class="categoryBubble__lbl">${label}</span></button>`
}).join('')

function areaTrafficLevel(crowdScore: number): 'Low' | 'Medium' | 'High' {
  const adj = Math.min(99, Math.max(1, crowdScore + Math.round(crowdScore * 0.08) - 6))
  return adj >= 72 ? 'High' : adj >= 45 ? 'Medium' : 'Low'
}

function bestTimeHint(crowdLevel: string): string {
  if (crowdLevel === 'High') return 'Early morning (before 9:00) or late weekday afternoons tend to be calmer.'
  if (crowdLevel === 'Medium') return 'Midday is usually busier; late morning or early evening are softer windows.'
  return 'Most times look comfortable; still avoid major holidays if you prefer quiet.'
}

const root = document.querySelector<HTMLDivElement>('#app')
if (!root) throw new Error('Missing #app mount element')

root.innerHTML = `
  <div class="page page--premium page--retro">
    <header class="topbar topbar--slim" role="banner">
      <h1 class="topbar__title">İstanbul Crowd Compass</h1>
    </header>

    <div class="layout">
      <div class="panel panel--search" id="explorePanel">
        <section class="card card--search card--lead">
          <div class="cardTitleRow">
            <h2>Search</h2>
          </div>

          <div class="searchShell">
            <label class="srOnly" for="globalSearchInput">Find a place</label>
            <div class="searchInputRow">
              <span class="searchGlyph" aria-hidden="true">⌕</span>
              <input
                id="globalSearchInput"
                class="input input--search"
                type="text"
                placeholder="Places, districts, landmarks…"
                autocomplete="off"
                spellcheck="false"
              />
            </div>
            <div id="globalSearchResults" class="results results--rich" aria-live="polite" role="listbox"></div>
          </div>
        </section>
        <div class="sideVideoStack" aria-label="Istanbul video clips">${SIDE_VIDEO_STACK_HTML}</div>
      </div>

      <div class="mapColumn">
        <section class="mapWrap mapStage" id="mapStage">
        <div id="map" class="map" aria-label="Interactive map (tap or click to select)"></div>
        <button type="button" id="mapFullscreenBtn" class="fab fab--expand" aria-pressed="false" aria-label="Immersive map">
          <span class="fab__glyph" aria-hidden="true">⛶</span>
        </button>
        <div
          class="forecastSpotlight forecastSheet forecastSheet--peek"
          id="forecastSheetRoot"
          aria-live="polite"
        >
          <button
            type="button"
            class="sheetHandleBtn"
            id="forecastSheetToggle"
            aria-expanded="false"
            aria-controls="forecastSheetCollapsible"
            aria-label="Pin place detail open (or hover the panel to preview)"
          >
            <span class="sheetHandle" aria-hidden="true"></span>
            <span class="sheetChevron" aria-hidden="true">▼</span>
          </button>
          <div class="sheetSwipeStrip" id="sheetSwipeStrip">
            <div class="forecastHeader">
              <p id="detailScreenLabel">Place</p>
              <span>Outlook</span>
            </div>
            <div class="forecastTitle" id="forecastTitleText">Select a place on the map or via search</div>
            <div class="forecastLevelRow">
              <div>
                <div class="forecastLabel" id="forecastCrowdLabel">Crowd outlook</div>
                <div class="forecastLevel" id="forecastLevelText">—</div>
              </div>
              <div>
                <div class="forecastLabel">Crowd index</div>
                <div class="forecastScore"><span id="forecastScoreText">—</span><small>/100</small></div>
              </div>
            </div>
            <div id="forecastBadges" class="forecastBadges" aria-label="Highlights"></div>
          </div>
          <div id="forecastSheetCollapsible" class="sheetCollapsible">
            <p class="forecastInterpret" id="forecastInterpretation"></p>
            <div class="detailExtra">
              <div class="miniRow">
                <span class="miniLabel">Area traffic</span>
                <span class="miniValue" id="areaTrafficText">—</span>
              </div>
              <div class="miniRow">
                <span class="miniLabel">Best time</span>
                <span class="miniHint" id="bestTimeText">—</span>
              </div>
            </div>
            <div class="trendLine">
              <span>Trend</span>
              <div id="forecastTrendText">Awaiting selection…</div>
            </div>
            <div id="crowdedWarning" class="crowdedWarn" hidden>
              <strong id="crowdedWarnTitle">Busy right now</strong>
              <p id="crowdedWarnBody">
                This selection looks crowded for your chosen window. Consider an alternative below.
              </p>
            </div>
            <div id="alternativesBlock" class="altBlock" hidden>
              <div class="altTitle" id="alternativesTitle">Alternatives nearby</div>
              <div id="alternativesList" class="altList" role="list"></div>
            </div>
          </div>
          <div class="navRow">
            <button id="openMapsBtn" class="btn btnPrimary" type="button" disabled>
              Open in Google Maps
            </button>
          </div>
        </div>
      </section>

        <section class="spotGuide popularPathBelow" aria-label="Landmarks">
          <div class="popularPathMount spotGuide__mount" id="popularPathMount"></div>
        </section>
      </div>

      <div class="panel panel--trip" id="tripPanel">
        <section class="card card--explore">
          <div class="flowBlock">
            <div class="btnRow">
              <button id="useMyLocationBtn" class="btn btnPrimary btnInline btn--sm" type="button">
                Use my location
              </button>
            </div>
            <div id="locationStatus" class="hint" style="margin-top: 8px"></div>

            <div class="categoryBubblesWrap">
              <div class="fieldLabel">
                <span>Category</span>
              </div>
              <div class="categoryBubbles" role="group" aria-label="Filter by place category">
                ${CATEGORY_BUBBLES_HTML}
              </div>
            </div>
            <div class="visitDateRow">
              <div class="fieldLabel">
                <span>Visit date</span>
              </div>
              <input type="hidden" id="visitDatePicker" value="" autocomplete="off" />
              <div class="miniCalendar" id="visitCalendarShell" aria-label="Choose visit date">
                <div class="miniCalendar__nav">
                  <button type="button" class="miniCalendar__navBtn" id="visitCalPrev" aria-label="Previous month">
                    ‹
                  </button>
                  <div class="miniCalendar__month" id="visitCalMonthYear"></div>
                  <button type="button" class="miniCalendar__navBtn" id="visitCalNext" aria-label="Next month">
                    ›
                  </button>
                </div>
                <div class="miniCalendar__weekdays" aria-hidden="true">
                  <span>Mo</span><span>Tu</span><span>We</span><span>Th</span><span>Fr</span><span>Sa</span><span>Su</span>
                </div>
                <div class="miniCalendar__cells" id="visitCalGrid" role="group"></div>
                <button type="button" class="miniCalendar__clear" id="visitCalClear">
                  Clear · use right now
                </button>
              </div>
            </div>
            <div class="sideVideoStack sideVideoStack--trip" aria-label="More Istanbul video clips">${SIDE_VIDEO_TRIP_STACK_HTML}</div>
          </div>
        </section>
      </div>

      <nav class="mobileDock" aria-label="Quick actions">
        <button type="button" class="dockBtn" id="dockExplore" aria-label="Scroll to explore">
          <span class="dockBtn__ic" aria-hidden="true">◇</span>
          <span class="dockBtn__tx">Explore</span>
        </button>
        <button type="button" class="dockBtn" id="dockMap" aria-label="Scroll to map">
          <span class="dockBtn__ic" aria-hidden="true">◎</span>
          <span class="dockBtn__tx">Map</span>
        </button>
        <button id="openMapsBtnMobile" class="dockBtn dockBtn--accent" type="button" disabled aria-label="Open in Google Maps">
          <span class="dockBtn__ic" aria-hidden="true">→</span>
          <span class="dockBtn__tx">Go</span>
        </button>
      </nav>
    </div>
  </div>
`

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id)
  if (!node) throw new Error(`Missing element #${id}`)
  return node as T
}

function localDateInputValue(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

function startOfMonth(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), 1)
}

/** Visible month in the always-open visit calendar (local, 1st of month). */
let visitCalView = startOfMonth(new Date())
const _visitCalInitDay = new Date()
_visitCalInitDay.setHours(0, 0, 0, 0)
let visitCalMinD = new Date(_visitCalInitDay)
let visitCalMaxD = new Date(_visitCalInitDay)
visitCalMaxD.setFullYear(visitCalMaxD.getFullYear() + 1)

function clampVisitCalViewToRange(): void {
  const minYm = visitCalMinD.getFullYear() * 12 + visitCalMinD.getMonth()
  const maxYm = visitCalMaxD.getFullYear() * 12 + visitCalMaxD.getMonth()
  let vm = visitCalView.getFullYear() * 12 + visitCalView.getMonth()
  vm = Math.max(minYm, Math.min(maxYm, vm))
  visitCalView = new Date(Math.floor(vm / 12), vm % 12, 1)
}

function renderVisitCalendar(): void {
  const grid = document.getElementById('visitCalGrid')
  const monthYearEl = document.getElementById('visitCalMonthYear')
  const prevBtn = document.getElementById('visitCalPrev') as HTMLButtonElement | null
  const nextBtn = document.getElementById('visitCalNext') as HTMLButtonElement | null
  const hidden = document.getElementById('visitDatePicker') as HTMLInputElement | null
  if (!grid || !monthYearEl || !prevBtn || !nextBtn || !hidden) return

  const selected = hidden.value.trim()
  const y = visitCalView.getFullYear()
  const m = visitCalView.getMonth()

  monthYearEl.textContent = new Date(y, m, 1).toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric'
  })

  const minYm = visitCalMinD.getFullYear() * 12 + visitCalMinD.getMonth()
  const maxYm = visitCalMaxD.getFullYear() * 12 + visitCalMaxD.getMonth()
  const viewYm = y * 12 + m
  prevBtn.disabled = viewYm <= minYm
  nextBtn.disabled = viewYm >= maxYm

  grid.replaceChildren()
  const first = new Date(y, m, 1)
  const lastDay = new Date(y, m + 1, 0).getDate()
  const lead = (first.getDay() + 6) % 7

  const today = new Date()
  today.setHours(0, 0, 0, 0)

  for (let i = 0; i < lead; i++) {
    const pad = document.createElement('span')
    pad.className = 'miniCalendar__pad'
    pad.setAttribute('aria-hidden', 'true')
    grid.appendChild(pad)
  }

  for (let d = 1; d <= lastDay; d++) {
    const cellDate = new Date(y, m, d)
    cellDate.setHours(0, 0, 0, 0)
    const ymd = localDateInputValue(cellDate)
    const btn = document.createElement('button')
    btn.type = 'button'
    btn.className = 'miniCalendar__day'
    btn.textContent = String(d)
    btn.setAttribute(
      'aria-label',
      cellDate.toLocaleDateString(undefined, {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric'
      })
    )
    btn.style.setProperty('--day-delay', `${((d + lead) % 7) * 0.04}s`)

    if (cellDate < visitCalMinD || cellDate > visitCalMaxD) {
      btn.disabled = true
      btn.classList.add('miniCalendar__day--muted')
    } else {
      btn.addEventListener('click', () => {
        hidden.value = ymd
        renderVisitCalendar()
        onFilterChange()
      })
    }

    if (ymd === selected) btn.classList.add('isSelected')
    if (cellDate.getTime() === today.getTime()) btn.classList.add('miniCalendar__day--today')

    grid.appendChild(btn)
  }
}

function syncVisitDatePickerBounds(): void {
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  visitCalMinD = new Date(today)
  visitCalMaxD = new Date(today)
  visitCalMaxD.setFullYear(visitCalMaxD.getFullYear() + 1)
  clampVisitCalViewToRange()
  renderVisitCalendar()
}

/** ISO timestamp for ``POST /api/recommendations``: chosen day + current clock, or now when the date is cleared. */
function getRecommendationTimestampISO(): string {
  const input = document.getElementById('visitDatePicker') as HTMLInputElement | null
  const raw = input?.value?.trim()
  if (!raw) return new Date().toISOString()
  const parts = raw.split('-').map(Number)
  const y = parts[0]
  const mo = parts[1]
  const d = parts[2]
  if (!y || !mo || !d) return new Date().toISOString()
  const now = new Date()
  const visit = new Date(y, mo - 1, d, now.getHours(), now.getMinutes(), now.getSeconds(), now.getMilliseconds())
  return visit.toISOString()
}

function getCategoryFilter(): string {
  const active = document.querySelector<HTMLButtonElement>('.categoryBubble.isActive')
  const v = active?.dataset.category ?? 'all'
  return v === 'all' ? '' : v
}

function applyCategoryToSearchResults(items: SearchResult[]): SearchResult[] {
  const cat = getCategoryFilter()
  if (!cat) return items
  return items.filter((i) => {
    if (i.kind !== 'poi') return true
    return i.poi.category === cat
  })
}

function googleMapsDirectionsUrl(sel: MapSelection): string {
  const { lat, lng } = sel.latlng
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${lat},${lng}`)}`
}

function crowdLevelNorm(label: string): 'Low' | 'Medium' | 'High' {
  const s = label.toLowerCase()
  if (s.includes('high') || s.includes('busy')) return 'High'
  if (s.includes('low') || s.includes('quiet')) return 'Low'
  return 'Medium'
}

async function execGlobalSearch(query: string, container: HTMLDivElement) {
  setSkeletonResults(container)
  try {
    const items = await searchEverything(query)
    clearResults(container)
    const filtered = applyCategoryToSearchResults(items)
    if (filtered.length === 0) {
      showWarmEmpty(
        container,
        items.length === 0
          ? 'Try a landmark, neighborhood, or hotel name—we’ll surface matches as you type.'
          : 'Nothing in this category—switch to “All categories” for more.'
      )
      return
    }
    filtered.forEach((item, i) => {
      if (item.kind === 'hotel') container.appendChild(makeHotelRow(item.hotel, i))
      else container.appendChild(makePoiRow(item.poi, i))
    })
  } catch {
    showWarmEmpty(
      container,
      'Check your connection or try again. Search works even when extra services are offline.',
      'Search unavailable'
    )
  }
}

function buildForecastBadgesHtml(level: string, kind: SelectionKind, label: string): string {
  const h = new Date().getHours()
  const parts: { text: string; mod: string }[] = []
  if (h >= 17 && h < 21) parts.push({ text: 'Perfect for sunset', mod: 'forecastBadge--sun' })
  if (level === 'Low') parts.push({ text: 'Quiet stretch ahead', mod: 'forecastBadge--quiet' })
  if (level === 'High') parts.push({ text: 'Best avoided at peak hours', mod: 'forecastBadge--peak' })
  if (/galata|ayasofya|hagia|grand bazaar|tower|mosque|bazaar/i.test(label))
    parts.push({ text: 'Popular with tourists', mod: 'forecastBadge--tour' })
  if (parts.length < 4 && kind === 'poi') parts.push({ text: 'Great hidden gem nearby', mod: 'forecastBadge--gem' })
  return parts
    .slice(0, 5)
    .map((p) => `<span class="forecastBadge ${p.mod}">${escapeHtml(p.text)}</span>`)
    .join('')
}

function renderDiscoveryPanel(container: HTMLDivElement) {
  const recent = recentSearchesGet().slice(0, 6)
  const recentBlock =
    recent.length === 0
      ? ''
      : `<div class="discSection"><div class="discSection__title">Recent</div>${recent
          .map(
            (q) =>
              `<button type="button" class="discRow" data-q="${escapeHtml(q)}"><span class="discRow__hint">Again</span><span class="discRow__name">${escapeHtml(q)}</span></button>`
          )
          .join('')}</div>`

  const trendBlock = `<div class="discSection"><div class="discSection__title">Popular in Istanbul</div>${TRENDING_ISTANBUL.map(
    (t: DiscoveryItem) =>
      `<button type="button" class="discRow discRow--rich" data-q="${escapeHtml(t.query)}"><span class="discRow__ic" aria-hidden="true">${t.icon}</span><span class="discRow__stack"><span class="discRow__name">${escapeHtml(t.query)}</span><span class="discRow__sub">${escapeHtml(t.subtitle ?? '')}</span></span></button>`
  ).join('')}</div>`

  const gemsBlock = `<div class="discSection"><div class="discSection__title">Hidden gems near you</div>${HIDDEN_GEMS.map(
    (t: DiscoveryItem) =>
      `<button type="button" class="discRow discRow--rich" data-q="${escapeHtml(t.query)}"><span class="discRow__ic" aria-hidden="true">${t.icon}</span><span class="discRow__stack"><span class="discRow__name">${escapeHtml(t.query)}</span><span class="discRow__sub">${escapeHtml(t.subtitle ?? '')}</span></span></button>`
  ).join('')}</div>`

  const guessBlock = `<div class="discSection"><div class="discSection__title">You might also like</div>
    <div class="guessGrid">
      <span class="guessPill">Perfect evening spots</span>
      <span class="guessPill">Quiet alternatives nearby</span>
      <span class="guessPill">Less crowded than Galata Tower</span>
    </div></div>`

  container.innerHTML = `<div class="discoveryPanel animStagger">${recentBlock}${trendBlock}${gemsBlock}${guessBlock}</div>`
  container.querySelectorAll<HTMLButtonElement>('button[data-q]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const q = btn.getAttribute('data-q') ?? ''
      const input = document.getElementById('globalSearchInput') as HTMLInputElement | null
      if (input) input.value = q
      recentSearchesAdd(q)
      void execGlobalSearch(q, container)
    })
  })
}

async function fillAlternativesIfCrowded(sel: MapSelection, crowdLevel: string, forecastScope: string) {
  const warn = el<HTMLDivElement>('crowdedWarning')
  const block = el<HTMLDivElement>('alternativesBlock')
  const list = el<HTMLDivElement>('alternativesList')
  const warnTitle = el<HTMLElement>('crowdedWarnTitle')
  const warnBody = el<HTMLParagraphElement>('crowdedWarnBody')
  const altTitle = el<HTMLDivElement>('alternativesTitle')

  const showRecommendations = sel.kind === 'location'

  warn.hidden = crowdLevel !== 'High'
  block.hidden = !(crowdLevel === 'High' || showRecommendations)
  list.innerHTML = ''
  if (showRecommendations) {
    altTitle.textContent = 'Recommended nearby'
    warnTitle.textContent = 'Busy right now'
    warnBody.textContent =
      'This selection looks crowded for your chosen window. Consider an alternative below.'
    warn.hidden = crowdLevel !== 'High'
  } else if (!showRecommendations && crowdLevel !== 'High') {
    warnTitle.textContent = 'Busy right now'
    warnBody.textContent =
      'This selection looks crowded for your chosen window. Consider an alternative below.'
    altTitle.textContent = 'Alternatives nearby'
    return
  }

  if (!showRecommendations && forecastScope === 'city_wide') {
    warnTitle.textContent = 'Busy week city-wide'
    warnBody.textContent =
      'Pressure is high across Istanbul this week—the outlook isn’t a live queue at this pin. Nearby suggestions are for inspiration.'
    altTitle.textContent = 'Other places nearby'
  } else if (!showRecommendations) {
    warnTitle.textContent = 'Crowd outlook unavailable'
    warnBody.textContent =
      'We couldn’t load a full weekly score—nearby places are shown for exploration only.'
    altTitle.textContent = 'Alternatives nearby'
  }

  const cat = getCategoryFilter()

  try {
    const data = await fetchRecommendations({
      origin: sel.latlng,
      timestamp: getRecommendationTimestampISO(),
      radiusKm: showRecommendations ? 10 : 25,
      topK: showRecommendations ? 6 : 4,
      includeItinerary: false,
      ...(cat ? { allowedCategories: [cat] } : {})
    })
    const recs = data.recommendations
    if (recs.length === 0) {
      list.innerHTML =
        '<p class="altEmpty">No suggestions for this spot yet—try another category or move the map.</p>'
      return
    }
    for (const rec of recs) {
      const ranked = rec as RankedRecommendation
      const name = String(ranked.name ?? 'Place')
      const dist = ranked.distance_km
      const km =
        typeof dist === 'number'
          ? dist
          : typeof dist === 'string'
            ? parseFloat(dist)
            : NaN
      const distLabel =
        Number.isFinite(km) && km < 1
          ? `${Math.round(km * 1000)} m`
          : Number.isFinite(km)
            ? `${km.toFixed(1)} km`
            : '—'
      const metaCat = String(ranked.category ?? '')
      const crowdRaw = String(ranked.crowd_level_label ?? '')
      const thumb = gradientThumbStyle(name)
      const photoUrl = rankedRowPhotoUrl(ranked)
      const llAlt = pickLatLngFromRankedRec(ranked)
      const badges = recommendationMicroBadges(ranked)
        .map((t) => `<span class="microBadge">${escapeHtml(t)}</span>`)
        .join('')
      const dot = crowdDotClass(crowdRaw || 'Medium')
      const cl = crowdRaw ? crowdLevelNorm(crowdRaw) : 'Medium'
      const bt = bestTimeShort(cl)
      const favId = `rec:${String(ranked.poi_id ?? name)}`
      const favOn = favoriteHas(favId)

      const b = document.createElement('div')
      b.className = 'altCard'
      b.setAttribute('role', 'listitem')
      b.tabIndex = 0
      const altThumb = altCardThumbBlock({
        photoUrl,
        placeName: name,
        lat: llAlt?.lat,
        lng: llAlt?.lng,
        gradientCss: thumb,
        iconHtml: categoryIcon(metaCat, 'poi')
      })
      b.innerHTML = `
        ${altThumb}
        <div class="altCard__body">
          <div class="altCard__head">
            <span class="crowdDot ${dot}" aria-hidden="true"></span>
            <span class="microAi">Pick</span>
            <button type="button" class="favBtn favBtn--sm ${favOn ? 'isOn' : ''}" data-favid="${escapeHtml(favId)}" aria-label="Save">${favOn ? '♥' : '♡'}</button>
          </div>
          <span class="altCard__name">${escapeHtml(name)}</span>
          <span class="altCard__meta">${escapeHtml(metaCat)} · ${escapeHtml(distLabel)}</span>
          <div class="microBadgeRow">${badges}</div>
          <div class="bestTimeMini"><span>Best time</span> ${escapeHtml(bt)}</div>
        </div>`
      const fav = b.querySelector('.favBtn')
      fav?.addEventListener('click', (ev) => {
        ev.stopPropagation()
        const on = favoriteToggle(favId)
        fav.classList.toggle('isOn', on)
        fav.textContent = on ? '♥' : '♡'
      })
      const go = () => {
        if (!llAlt) return
        const next: MapSelection = { latlng: llAlt, label: name, kind: 'location' }
        currentSelection = next
        setChip(next)
        map.setMarker(next, { flyTo: true })
      }
      b.addEventListener('click', (ev) => {
        if ((ev.target as HTMLElement).closest('.favBtn')) return
        go()
      })
      b.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          go()
        }
      })
      list.appendChild(b)
    }
  } catch {
    list.innerHTML = '<p class="altEmpty">Suggestions unavailable right now. Try again in a moment.</p>'
  }
}

let lastSetChipPeekKey = '__init__'

function setChip(selection: MapSelection | null) {
  const peekKey = selection
    ? `${selection.kind}|${selection.label}|${selection.latlng.lat.toFixed(4)}|${selection.latlng.lng.toFixed(4)}`
    : 'null'
  if (peekKey !== lastSetChipPeekKey) {
    lastSetChipPeekKey = peekKey
    document.getElementById('forecastSheetRoot')?.dispatchEvent(new Event('icc-forecast-peek-reset', { bubbles: false }))
  }

  const forecastTitle = el<HTMLDivElement>('forecastTitleText')
  const forecastLevel = el<HTMLDivElement>('forecastLevelText')
  const forecastScore = el<HTMLSpanElement>('forecastScoreText')
  const forecastTrend = el<HTMLDivElement>('forecastTrendText')
  const areaTrafficText = el<HTMLSpanElement>('areaTrafficText')
  const bestTimeText = el<HTMLSpanElement>('bestTimeText')
  const detailScreenLabel = el<HTMLParagraphElement>('detailScreenLabel')
  const crowdedWarning = el<HTMLDivElement>('crowdedWarning')
  const alternativesBlock = el<HTMLDivElement>('alternativesBlock')
  const alternativesList = el<HTMLDivElement>('alternativesList')
  const openMapsBtn = el<HTMLButtonElement>('openMapsBtn')
  const openMapsBtnMobile = document.getElementById('openMapsBtnMobile') as HTMLButtonElement | null
  const forecastInterpretation = el<HTMLParagraphElement>('forecastInterpretation')
  const forecastCrowdLabel = el<HTMLDivElement>('forecastCrowdLabel')
  const forecastBadgesEl = document.getElementById('forecastBadges')

  if (!selection) {
    forecastTitle.textContent = 'Tap the map or pick from search'
    forecastInterpretation.textContent = ''
    forecastCrowdLabel.textContent = 'Crowd outlook'
    forecastLevel.textContent = '—'
    forecastScore.textContent = '—'
    forecastTrend.textContent = 'Awaiting selection…'
    areaTrafficText.textContent = '—'
    bestTimeText.textContent = '—'
    detailScreenLabel.textContent = 'Place'
    crowdedWarning.hidden = true
    alternativesBlock.hidden = true
    alternativesList.innerHTML = ''
    if (forecastBadgesEl) forecastBadgesEl.innerHTML = ''
    openMapsBtn.disabled = true
    if (openMapsBtnMobile) openMapsBtnMobile.disabled = true
    return
  }

  openMapsBtn.disabled = false
  if (openMapsBtnMobile) openMapsBtnMobile.disabled = false
  detailScreenLabel.textContent = selection.kind === 'poi' ? 'Landmark or place' : 'Place'
  forecastTitle.textContent = selection.label
  forecastLevel.textContent = '…'
  forecastScore.textContent = '…'
  forecastTrend.textContent = 'Loading outlook…'
  areaTrafficText.textContent = '…'
  bestTimeText.textContent = '…'
  forecastInterpretation.textContent = ''
  crowdedWarning.hidden = true
  alternativesBlock.hidden = true
  alternativesList.innerHTML = ''
  if (forecastBadgesEl) forecastBadgesEl.innerHTML = ''

  forecast({ kind: selection.kind, label: selection.label, latlng: selection.latlng }, FORECAST_HORIZON_WEEKS)
    .then((res) => {
      if (!currentSelection) return
      if (currentSelection.label !== selection.label || currentSelection.kind !== selection.kind) return
      forecastLevel.textContent = res.level
      forecastScore.textContent = String(res.score)
      forecastTrend.textContent = res.trend
      const scope = res.forecastScope ?? 'demo'
      let interp = res.interpretation?.trim() ?? ''
      if (res.basisWeekStart) {
        const wk = `Outlook for the week starting ${res.basisWeekStart}.`
        interp = interp ? `${interp} ${wk}` : wk
      }
      forecastInterpretation.textContent = interp

      if (scope === 'city_wide') {
        forecastCrowdLabel.textContent = 'This week in Istanbul'
        areaTrafficText.textContent = `${res.level} (city-wide)`
      } else {
        forecastCrowdLabel.textContent = 'Estimated crowd'
        areaTrafficText.textContent = areaTrafficLevel(res.score)
      }
      bestTimeText.textContent = bestTimeHint(res.level)
      if (forecastBadgesEl)
        forecastBadgesEl.innerHTML = buildForecastBadgesHtml(res.level, selection.kind, selection.label)
      void fillAlternativesIfCrowded(selection, res.level, scope)
    })
    .catch(() => {
      forecastLevel.textContent = '—'
      forecastScore.textContent = '—'
      forecastTrend.textContent = 'Outlook unavailable—check your connection and try again.'
      areaTrafficText.textContent = '—'
      bestTimeText.textContent = '—'
      forecastInterpretation.textContent = ''
      if (forecastBadgesEl) forecastBadgesEl.innerHTML = ''
      crowdedWarning.hidden = true
      alternativesBlock.hidden = true
      alternativesList.innerHTML = ''
    })
}

const globalSearchInput = el<HTMLInputElement>('globalSearchInput')
const globalSearchResults = el<HTMLDivElement>('globalSearchResults')

function clearResults(container: HTMLDivElement) {
  container.innerHTML = ''
}

function showEmpty(container: HTMLDivElement, text: string, title?: string) {
  showWarmEmpty(container, text, title)
}

function showWarmEmpty(container: HTMLDivElement, text: string, title = 'No matches yet') {
  clearResults(container)
  const row = document.createElement('div')
  row.className = 'emptyState'
  row.style.cursor = 'default'
  row.innerHTML = `
    <div class="emptyState__art" aria-hidden="true">✦</div>
    <div class="emptyState__title">${escapeHtml(title)}</div>
    <div class="emptyState__body">${escapeHtml(text)}</div>
  `
  container.appendChild(row)
}

function rankedRowPhotoUrl(rec: RankedRecommendation): string | undefined {
  const r = rec as Record<string, unknown>
  const direct =
    (typeof r.photo_url === 'string' && r.photo_url.trim()) ||
    (typeof r.photoUrl === 'string' && r.photoUrl.trim())
  if (direct) return direct
  const pid = r.poi_id != null ? String(r.poi_id) : ''
  return pid ? thumbUrlForPoiId(pid) : undefined
}

/** Alternative row thumbnail (Google proxy when coords exist, else photo or gradient + glyph). */
function altCardThumbBlock(opts: {
  photoUrl?: string
  placeName: string
  lat?: number
  lng?: number
  gradientCss: string
  iconHtml: string
}): string {
  const lat = opts.lat
  const lng = opts.lng
  const hasCoords =
    typeof lat === 'number' &&
    typeof lng === 'number' &&
    Number.isFinite(lat) &&
    Number.isFinite(lng)
  const nm = opts.placeName.trim()
  const useProxy = Boolean(nm && hasCoords)
  const photoUrl = opts.photoUrl?.trim()
  const fbHttps = photoUrl?.startsWith('https://') ? photoUrl : undefined

  if (useProxy) {
    const proxyEsc = escapeHtml(
      placePhotoProxyUrl({
        name: nm,
        lat,
        lng,
        fallbackUrl: fbHttps
      })
    )
    const bgEsc = escapeHtml(opts.gradientCss)
    const dataFb = fbHttps ? ` data-fallback="${escapeHtml(fbHttps)}"` : ''
    const onerr = fbHttps
      ? ` onerror="this.onerror=null;if(this.dataset.fallback){this.src=this.dataset.fallback;this.removeAttribute('data-fallback');return;}this.remove()"`
      : ` onerror="this.remove()"`
    return `<div class="altCard__thumb altCard__thumb--photo" style="background:${bgEsc}"><span class="altCard__ic" aria-hidden="true">${opts.iconHtml}</span><img class="altCard__img" src="${proxyEsc}" alt="" loading="lazy" decoding="async"${dataFb}${onerr} /></div>`
  }
  if (photoUrl) {
    return `<div class="altCard__thumb altCard__thumb--photo"><img class="altCard__img" src="${escapeHtml(photoUrl)}" alt="" loading="lazy" decoding="async" /></div>`
  }
  return `<div class="altCard__thumb" style="background:${escapeHtml(opts.gradientCss)}"><span class="altCard__ic" aria-hidden="true">${opts.iconHtml}</span></div>`
}

function pickLatLngFromRankedRec(rec: RankedRecommendation): LatLng | null {
  const lat = typeof rec.lat === 'number' ? rec.lat : rec.lat != null ? Number(rec.lat) : NaN
  const lng =
    typeof rec.lng === 'number'
      ? rec.lng
      : rec.lng != null
        ? Number(rec.lng)
        : typeof (rec as { lon?: unknown }).lon === 'number'
          ? (rec as { lon: number }).lon
          : (rec as { lon?: unknown }).lon != null
            ? Number((rec as { lon: unknown }).lon)
            : NaN
  if (!Number.isFinite(lat) || !Number.isFinite(lng)) return null
  return { lat, lng }
}

function makeRankedRecommendationRow(rec: RankedRecommendation, index = 0): HTMLElement {
  const row = document.createElement('div')
  row.className = 'richResult richResult--rise richResult--rank'
  row.style.setProperty('--i', String(index))
  row.setAttribute('role', 'option')
  row.tabIndex = 0

  const name = String(rec.name ?? 'Place')
  const dist = rec.distance_km
  const distStr =
    typeof dist === 'number'
      ? dist < 1
        ? `${Math.round(dist * 1000)} m`
        : `${dist.toFixed(1)} km`
      : '—'
  const cat = String(rec.category ?? '')
  const crowd = String(rec.crowd_level_label ?? '')
  const expl = String(rec.explanation ?? rec.explanation_text ?? '')
  const llRec = pickLatLngFromRankedRec(rec)
  const badges = recommendationMicroBadges(rec)
    .map((t) => `<span class="microBadge">${escapeHtml(t)}</span>`)
    .join('')
  const dot = crowdDotClass(crowd || 'Medium')
  const bt = bestTimeShort(crowd ? crowdLevelNorm(crowd) : 'Medium')
  const favId = `rec:${String(rec.poi_id ?? name)}`
  const favOn = favoriteHas(favId)

  row.innerHTML = `
    <div class="richBody">
      <div class="richTop">
        <span class="crowdDot ${dot}" aria-hidden="true"></span>
        <span class="richKind">Nearby</span>
        <span class="microAi">For you</span>
        <button type="button" class="favBtn ${favOn ? 'isOn' : ''}" aria-label="Save place">${favOn ? '♥' : '♡'}</button>
      </div>
      <div class="richName">${escapeHtml(name)}</div>
      <div class="richMeta">${escapeHtml(cat)} · ${escapeHtml(distStr)}${crowd ? ` · ${escapeHtml(crowd)}` : ''}</div>
      <div class="microBadgeRow">${badges}</div>
      <div class="bestTimeMini"><span>Best time</span> ${escapeHtml(bt)}</div>
      ${expl.trim() ? `<div class="richExpl">${escapeHtml(expl)}</div>` : ''}
    </div>`

  const fav = row.querySelector('.favBtn')
  fav?.addEventListener('click', (e) => {
    e.stopPropagation()
    const on = favoriteToggle(favId)
    fav.classList.toggle('isOn', on)
    fav.textContent = on ? '♥' : '♡'
  })

  const go = () => {
    if (!llRec) return
    const sel: MapSelection = { latlng: llRec, label: name, kind: 'location' }
    currentSelection = sel
    setChip(sel)
    map.setMarker(sel, { flyTo: true })
  }
  row.addEventListener('click', (ev) => {
    if ((ev.target as HTMLElement).closest('.favBtn')) return
    go()
  })
  row.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      go()
    }
  })

  return row
}

function fillNearbyRecommendationsPanel(origin: LatLng, cat: string) {
  clearResults(globalSearchResults)
  const recs = rankLocalPoisNear(origin, cat, 10)
  if (recs.length === 0) {
    showEmpty(
      globalSearchResults,
      'Nothing matched that category—set Category to “All categories” or search above.',
      'Nothing nearby'
    )
    return
  }
  recs.forEach((rec, i) => {
    globalSearchResults.appendChild(makeRankedRecommendationRow(rec as RankedRecommendation, i))
  })
}

function scrollNearbyResultsIntoView() {
  document.querySelector('.card--search')?.scrollIntoView({ behavior: 'smooth', block: 'nearest' })
}

async function showNearbyMatches(origin: LatLng) {
  setSkeletonResults(globalSearchResults)
  const cat = getCategoryFilter()
  try {
    const data = await fetchRecommendations({
      origin,
      timestamp: getRecommendationTimestampISO(),
      radiusKm: 12,
      topK: 10,
      includeItinerary: false,
      ...(cat ? { allowedCategories: [cat] } : {})
    })
    clearResults(globalSearchResults)
    const recs = data.recommendations
    if (recs.length === 0) {
      fillNearbyRecommendationsPanel(origin, cat)
    } else {
      recs.forEach((rec, i) => {
        globalSearchResults.appendChild(makeRankedRecommendationRow(rec as RankedRecommendation, i))
      })
    }
  } catch {
    fillNearbyRecommendationsPanel(origin, cat)
  }
  scrollNearbyResultsIntoView()
}

function setSkeletonResults(container: HTMLDivElement, rows = 5) {
  clearResults(container)
  const frag = document.createDocumentFragment()
  for (let i = 0; i < rows; i++) {
    const d = document.createElement('div')
    d.className = 'skelRow'
    d.style.setProperty('--i', String(i))
    d.innerHTML = `
      <div class="skelBody">
        <div class="skelLine skelLine--lg skelShimmer"></div>
        <div class="skelLine skelLine--sm skelShimmer"></div>
        <div class="skelLine skelLine--sm skelShimmer" style="width:55%"></div>
      </div>`
    frag.appendChild(d)
  }
  container.appendChild(frag)
}

function makeHotelRow(hotel: Hotel, index = 0): HTMLElement {
  const row = document.createElement('div')
  row.className = 'richResult richResult--rise'
  row.style.setProperty('--i', String(index))
  row.setAttribute('role', 'option')
  row.tabIndex = 0
  row.dataset.id = hotel.id

  const favOn = favoriteHas(`hotel:${hotel.id}`)
  const micro = hotelCardBadges(hotel).map((t) => `<span class="microBadge">${escapeHtml(t)}</span>`).join('')

  row.innerHTML = `
    <div class="richBody">
      <div class="richTop">
        <span class="richKind">Hotel</span>
        <button type="button" class="favBtn ${favOn ? 'isOn' : ''}" aria-label="Save hotel">${favOn ? '♥' : '♡'}</button>
      </div>
      <div class="richName">${escapeHtml(hotel.name)}</div>
      <div class="richMeta">${escapeHtml(hotel.district)} · ${hotel.rating.toFixed(1)}★ · from $${hotel.priceFrom}</div>
      <div class="microBadgeRow">${micro}</div>
    </div>`

  const fav = row.querySelector('.favBtn')
  fav?.addEventListener('click', (e) => {
    e.stopPropagation()
    const on = favoriteToggle(`hotel:${hotel.id}`)
    fav.classList.toggle('isOn', on)
    fav.textContent = on ? '♥' : '♡'
  })

  const pick = () => {
    recentSearchesAdd(hotel.name)
    selectHotel(hotel)
  }
  row.addEventListener('click', (ev) => {
    if ((ev.target as HTMLElement).closest('.favBtn')) return
    pick()
  })
  row.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      pick()
    }
  })
  return row
}

function makePoiRow(poi: Poi, index = 0): HTMLElement {
  const row = document.createElement('div')
  row.className = 'richResult richResult--rise'
  row.style.setProperty('--i', String(index))
  row.setAttribute('role', 'option')
  row.tabIndex = 0
  row.dataset.id = poi.id

  const favOn = favoriteHas(`poi:${poi.id}`)
  const micro = poiCardBadges(poi).map((t) => `<span class="microBadge">${escapeHtml(t)}</span>`).join('')

  row.innerHTML = `
    <div class="richBody">
      <div class="richTop">
        <span class="richKind">Sight</span>
        <button type="button" class="favBtn ${favOn ? 'isOn' : ''}" aria-label="Save place">${favOn ? '♥' : '♡'}</button>
      </div>
      <div class="richName">${escapeHtml(poi.name)}</div>
      <div class="richMeta">${escapeHtml(poi.category)}</div>
      <div class="microBadgeRow">${micro}</div>
    </div>`

  const fav = row.querySelector('.favBtn')
  fav?.addEventListener('click', (e) => {
    e.stopPropagation()
    const on = favoriteToggle(`poi:${poi.id}`)
    fav.classList.toggle('isOn', on)
    fav.textContent = on ? '♥' : '♡'
  })

  const pick = () => {
    recentSearchesAdd(poi.name)
    selectPoi(poi)
  }
  row.addEventListener('click', (ev) => {
    if ((ev.target as HTMLElement).closest('.favBtn')) return
    pick()
  })
  row.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      pick()
    }
  })
  return row
}

let currentSelection: MapSelection | null = null

/** Updated when “Use my location” succeeds or when opening directions acquires a GPS fix. */
let lastKnownUserLatLng: LatLng | null = null

const openGoogleMapsDirectionsFromUser = createDirectionsOpener(
  () => lastKnownUserLatLng ?? (currentSelection?.kind === 'location' ? currentSelection.latlng : null),
  (ll) => {
    lastKnownUserLatLng = ll
  },
  { travelMode: 'walking' }
)

const map = createMap(el<HTMLDivElement>('map'), {
  defaultCenter: DEFAULT_CENTER,
  onSelect: (selection) => {
    currentSelection = selection
    setChip(currentSelection)
  }
})

function selectHotel(hotel: Hotel) {
  currentSelection = {
    latlng: { lat: hotel.lat, lng: hotel.lng },
    label: hotel.name,
    kind: 'hotel'
  }
  setChip(currentSelection)
  map.setMarker(currentSelection, { flyTo: true })
}

function selectPoi(poi: Poi) {
  currentSelection = {
    latlng: { lat: poi.lat, lng: poi.lng },
    label: poi.name,
    kind: 'poi'
  }
  setChip(currentSelection)
  map.setMarker(currentSelection, { flyTo: true })
}

function debounce<T extends unknown[]>(fn: (...args: T) => void, ms: number) {
  let timer: number | null = null
  return (...args: T) => {
    if (timer) window.clearTimeout(timer)
    timer = window.setTimeout(() => fn(...args), ms)
  }
}

globalSearchInput.addEventListener('input', () => {
  debouncedGlobalSearch(globalSearchInput.value)
})

const debouncedGlobalSearch = debounce((query: string) => {
  void execGlobalSearch(query, globalSearchResults)
}, 140)

globalSearchInput.addEventListener('focus', () => {
  if (!globalSearchInput.value.trim()) {
    renderDiscoveryPanel(globalSearchResults)
  }
})

const locationStatus = el<HTMLDivElement>('locationStatus')
const useMyLocationBtn = el<HTMLButtonElement>('useMyLocationBtn')

function startGeolocation(statusEl: HTMLElement) {
  statusEl.textContent = ''

  if (!navigator.geolocation) {
    statusEl.textContent = 'Geolocation not available in this browser.'
    return
  }

  statusEl.textContent = 'Requesting location…'

  navigator.geolocation.getCurrentPosition(
    (pos) => {
      const selection: MapSelection = {
        latlng: { lat: pos.coords.latitude, lng: pos.coords.longitude },
        label: 'Current location',
        kind: 'location'
      }
      currentSelection = selection
      lastKnownUserLatLng = selection.latlng
      setChip(currentSelection)
      map.setMarker(currentSelection, { flyTo: true })
      void showNearbyMatches(selection.latlng)
      statusEl.textContent = ''
    },
    () => {
      statusEl.textContent =
        'Location unavailable or denied—you can still use search or tap the map.'
    },
    { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
  )
}

useMyLocationBtn.addEventListener('click', () => startGeolocation(locationStatus))

function onFilterChange() {
  debouncedGlobalSearch(globalSearchInput.value)
  if (currentSelection) setChip(currentSelection)
  if (currentSelection?.kind === 'location') {
    void showNearbyMatches(currentSelection.latlng)
  }
}

function wireCategoryBubbles() {
  const buttons = document.querySelectorAll<HTMLButtonElement>('.categoryBubble')
  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      if (btn.classList.contains('isActive')) return
      buttons.forEach((b) => {
        const on = b === btn
        b.classList.toggle('isActive', on)
        b.setAttribute('aria-pressed', String(on))
      })
      onFilterChange()
    })
  })
}

wireCategoryBubbles()

function wireVisitCalendar(): void {
  const prev = document.getElementById('visitCalPrev')
  const next = document.getElementById('visitCalNext')
  const clear = document.getElementById('visitCalClear')
  const hidden = document.getElementById('visitDatePicker') as HTMLInputElement | null

  prev?.addEventListener('click', () => {
    visitCalView = new Date(visitCalView.getFullYear(), visitCalView.getMonth() - 1, 1)
    clampVisitCalViewToRange()
    renderVisitCalendar()
  })
  next?.addEventListener('click', () => {
    visitCalView = new Date(visitCalView.getFullYear(), visitCalView.getMonth() + 1, 1)
    clampVisitCalViewToRange()
    renderVisitCalendar()
  })
  clear?.addEventListener('click', () => {
    if (hidden) hidden.value = ''
    renderVisitCalendar()
    onFilterChange()
  })
}

wireVisitCalendar()

function wireOpenMapsButton(btn: HTMLButtonElement) {
  btn.addEventListener('click', () => {
    if (!currentSelection) return
    window.open(googleMapsDirectionsUrl(currentSelection), '_blank', 'noopener,noreferrer')
  })
}

wireOpenMapsButton(el<HTMLButtonElement>('openMapsBtn'))
const openMapsBtnMobile = document.getElementById('openMapsBtnMobile') as HTMLButtonElement | null
if (openMapsBtnMobile) wireOpenMapsButton(openMapsBtnMobile)

function initForecastSheetCollapse() {
  const sheetRoot = document.getElementById('forecastSheetRoot')
  const sheetToggle = document.getElementById('forecastSheetToggle') as HTMLButtonElement | null
  const swipeStrip = document.getElementById('sheetSwipeStrip')
  const mapStage = document.querySelector<HTMLElement>('.mapStage')
  if (!sheetRoot || !sheetToggle || !mapStage) return

  const mq = window.matchMedia('(max-width: 768px)')
  let collapsed = mq.matches
  let peekLocked = false
  const SWIPE_PX = 52
  let ignoreNextToggleClick = false

  const syncDesktopPeek = () => {
    sheetRoot.classList.toggle('isPeekLocked', peekLocked)
    sheetToggle.setAttribute('aria-expanded', String(peekLocked))
    sheetToggle.setAttribute(
      'aria-label',
      peekLocked ? 'Tuck place detail into the corner' : 'Pin place detail open (or hover the panel to preview)'
    )
  }

  const sync = () => {
    if (!mq.matches) {
      collapsed = false
      sheetRoot.classList.remove('isCollapsed')
      mapStage.classList.remove('hasCollapsedSheet')
      sheetRoot.classList.add('forecastSheet--peek')
      syncDesktopPeek()
      return
    }
    peekLocked = false
    sheetRoot.classList.remove('isPeekLocked')
    sheetRoot.classList.toggle('isCollapsed', collapsed)
    mapStage.classList.toggle('hasCollapsedSheet', collapsed)
    sheetToggle.setAttribute('aria-expanded', String(!collapsed))
    sheetToggle.setAttribute('aria-label', collapsed ? 'Expand place detail' : 'Collapse place detail')
  }

  const applyResize = () => window.dispatchEvent(new Event('resize'))

  sheetRoot.addEventListener('icc-forecast-peek-reset', () => {
    peekLocked = false
    sync()
  })

  sheetToggle.addEventListener('click', () => {
    if (!mq.matches) {
      peekLocked = !peekLocked
      syncDesktopPeek()
      applyResize()
      return
    }
    if (ignoreNextToggleClick) {
      ignoreNextToggleClick = false
      return
    }
    collapsed = !collapsed
    sync()
    applyResize()
  })

  type SwipeTarget = HTMLElement
  const swipeTargets: SwipeTarget[] = swipeStrip ? [swipeStrip, sheetToggle] : [sheetToggle]

  type SwipeSession = {
    pointerId: number
    startX: number
    startY: number
    target: SwipeTarget
  }
  let swipe: SwipeSession | null = null

  const onPointerDown = (e: PointerEvent, target: SwipeTarget) => {
    if (!mq.matches || e.button !== 0) return
    swipe = { pointerId: e.pointerId, startX: e.clientX, startY: e.clientY, target }
    try {
      target.setPointerCapture(e.pointerId)
    } catch {
      swipe = null
    }
  }

  const endSwipe = (e: PointerEvent) => {
    if (!swipe || e.pointerId !== swipe.pointerId) return
    const { startX, startY, target } = swipe
    swipe = null
    try {
      if (target.hasPointerCapture(e.pointerId)) target.releasePointerCapture(e.pointerId)
    } catch {
      /* ignore */
    }
    if (!mq.matches) return

    const dy = e.clientY - startY
    const dx = e.clientX - startX
    if (Math.abs(dx) > Math.max(28, Math.abs(dy) * 1.15)) return

    if (!collapsed && dy > SWIPE_PX) {
      collapsed = true
      if (target === sheetToggle) ignoreNextToggleClick = true
      sync()
      applyResize()
      return
    }
    if (collapsed && dy < -SWIPE_PX) {
      collapsed = false
      if (target === sheetToggle) ignoreNextToggleClick = true
      sync()
      applyResize()
    }
  }

  for (const t of swipeTargets) {
    t.addEventListener('pointerdown', (e) => onPointerDown(e, t))
    t.addEventListener('pointerup', endSwipe)
    t.addEventListener('pointercancel', endSwipe)
  }

  mq.addEventListener('change', () => {
    collapsed = mq.matches
    peekLocked = false
    sync()
  })
  sync()
}

initForecastSheetCollapse()

function initPageEnter() {
  requestAnimationFrame(() => {
    const page = document.querySelector('.page--premium')
    page?.classList.add('page--mounted', 'page--unveil')
  })
}

initPageEnter()
void import('./features/istanbulExplorer/mount').then(({ mountIstanbulExplorer }) => {
  mountIstanbulExplorer(openGoogleMapsDirectionsFromUser)
})

// Ask for location permission right away (for “open app → GPS → recommendations” flow).
// If denied, the user can still search or tap the map.
window.setTimeout(() => {
  startGeolocation(locationStatus)
}, 160)
syncVisitDatePickerBounds()
setChip(null)

function initMapFullscreen() {
  const btn = document.getElementById('mapFullscreenBtn')
  const stage = document.getElementById('mapStage')
  if (!btn || !stage) return
  btn.addEventListener('click', () => {
    const on = stage.classList.toggle('mapStage--fullscreen')
    document.body.classList.toggle('body--map-fs', on)
    btn.setAttribute('aria-pressed', String(on))
    map.relayout()
    window.setTimeout(() => map.relayout(), 320)
  })
}

function initMobileDock() {
  document.getElementById('dockExplore')?.addEventListener('click', () => {
    document.getElementById('explorePanel')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  })
  document.getElementById('dockMap')?.addEventListener('click', () => {
    document.getElementById('mapStage')?.scrollIntoView({ behavior: 'smooth', block: 'center' })
  })
}

initMapFullscreen()
initMobileDock()
