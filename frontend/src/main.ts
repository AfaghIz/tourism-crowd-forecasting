import './app.css'
import 'leaflet/dist/leaflet.css'

import { createMap } from './map/mapController'
import {
  searchHotels,
  searchEverything,
  fetchRecommendations,
  type Hotel,
  type Poi,
  type RankedRecommendation,
  type SearchResult,
  forecast
} from './api/api'
import type { LatLng, MapSelection, SelectionKind } from './domain/types'

const DEFAULT_CENTER: LatLng = { lat: 41.0082, lng: 28.9784 }

const POI_CATEGORIES = [
  'all',
  'Landmark',
  'Museum',
  'Viewpoint',
  'Shopping',
  'Market',
  'Street'
] as const

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
  <div class="page">
    <div class="topbar">
      <div class="topbarInner">
        <div class="brand">
          <div class="brandMark" aria-hidden="true"></div>
          <div class="brandText">
            <h1>Istanbul Crowd Compass</h1>
            <p class="brandTagline">
              Pick a place on the map, see crowd context for your window, then open directions in Google Maps.
            </p>
          </div>
        </div>

        <div class="apiPill" title="Backend API (Flask)">
          <div class="apiDot" aria-hidden="true"></div>
          <span>${import.meta.env.VITE_API_BASE_URL || 'Render API'}</span>
        </div>
      </div>
    </div>

    <div class="heroStatsOuter" role="region" aria-label="Product highlights">
    <section class="heroStats">
      <article class="statCard">
        <div class="statLabel">Coverage</div>
        <div class="statValue">260 Weeks</div>
        <div class="statMeta">Historical demand-weather timeline</div>
      </article>
      <article class="statCard">
        <div class="statLabel">Baseline Model</div>
        <div class="statValue">R2 0.9813</div>
        <div class="statMeta">Random Forest benchmark</div>
      </article>
      <article class="statCard">
        <div class="statLabel">Experience</div>
        <div class="statValue">Live Map + Search</div>
        <div class="statMeta">Matches WEBSITE_UX_FLOW target journey</div>
      </article>
    </section>
    </div>

    <div class="layout">
      <div class="panel">
        <section class="card">
          <div class="flowBlock">
            <div class="fieldLabel">
              <span>Location on the Istanbul map</span>
              <span class="hint">step: GPS</span>
            </div>
            <div class="btnRow">
              <button id="useMyLocationBtn" class="btn btnPrimary btnInline" type="button">
                Use my location
              </button>
            </div>
            <div id="locationStatus" class="hint" style="margin-top: 8px"></div>

            <div class="filterGrid">
              <div>
                <div class="fieldLabel">
                  <span>Category</span>
                  <span class="hint">optional</span>
                </div>
                <select id="filterCategory" class="select" aria-label="Filter by place category">
                  ${POI_CATEGORIES.map(
  (c) =>
    `<option value="${c}">${c === 'all' ? 'All categories' : c}</option>`
).join('')}
                </select>
              </div>
              <div>
                <div class="fieldLabel">
                  <span>When</span>
                  <span class="hint">forecast window</span>
                </div>
                <select id="filterWhen" class="select" aria-label="Planning time horizon">
                  <option value="4">Next ~4 weeks (default)</option>
                  <option value="2">Closer window (~2 weeks)</option>
                  <option value="8">Longer view (~8 weeks)</option>
                </select>
              </div>
            </div>
          </div>

          <div class="cardTitleRow" style="margin-top: 14px">
            <h2>Hotel & Location</h2>
            <div class="hint">Map tap or search</div>
          </div>

          <div class="tabs" role="tablist" aria-label="Selection mode">
            <button id="tabHotels" class="tabBtn isActive" role="tab" aria-selected="true" type="button">
              Hotels
            </button>
            <button id="tabLocation" class="tabBtn" role="tab" aria-selected="false" type="button">
              Current location
            </button>
          </div>

          <div id="panelHotels" class="section">
            <div class="fieldLabel">
              <span>Pick a hotel</span>
              <span class="hint">prototype search</span>
            </div>
            <input
              id="hotelPickerInput"
              class="input"
              type="text"
              placeholder="Search hotels (e.g., Sultanahmet, Galata)"
              autocomplete="off"
              spellcheck="false"
            />
            <div id="hotelPickerResults" class="results" aria-live="polite" role="listbox"></div>
          </div>

          <div id="panelLocation" class="section" hidden>
            <div class="fieldLabel">
              <span>Use your current location</span>
              <span class="hint">browser geolocation</span>
            </div>
            <div class="hint" style="margin-top:10px">
              We request GPS on open. If you denied it, use the button above to retry.
            </div>
          </div>

          <div class="selectionBlock">
            <div class="fieldLabel" style="margin-top:14px">
              <span>Selection</span>
              <span class="hint">syncs with map marker</span>
            </div>
            <div class="selectionLine">
              <div class="chip" id="selectionChip">
                <i id="selectionChipDot" aria-hidden="true"></i>
                <span id="selectionKindText">—</span>
              </div>
              <div class="selectionLabel" id="selectionLabelText">Click map or choose a hotel</div>
            </div>
            <div class="coords">
              <span>Coordinates</span>
              <span id="selectionCoordsText">—</span>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="cardTitleRow">
            <h2>Search</h2>
            <div class="hint">Hotels + landmarks (prototype)</div>
          </div>

          <div class="fieldLabel">
            <span>Find a place</span>
            <span class="hint">POI or hotel</span>
          </div>
          <input
            id="globalSearchInput"
            class="input"
            type="text"
            placeholder="Search or tap the map (e.g. Hagia Sophia, Galata Tower)…"
            autocomplete="off"
            spellcheck="false"
          />
          <div id="globalSearchResults" class="results" aria-live="polite" role="listbox"></div>

          <div class="hint" style="margin-top:10px">
            API seam: replace mock functions like <code>searchEverything()</code> with real endpoints.
          </div>
        </section>
      </div>

      <section class="mapWrap mapStage">
        <div id="map" class="map" aria-label="Interactive map (tap or click to select)"></div>
        <div class="forecastSpotlight forecastSheet" id="forecastSheetRoot" aria-live="polite">
          <button
            type="button"
            class="sheetHandleBtn"
            id="forecastSheetToggle"
            aria-expanded="true"
            aria-controls="forecastSheetCollapsible"
            aria-label="Collapse place detail"
          >
            <span class="sheetHandle" aria-hidden="true"></span>
            <span class="sheetChevron" aria-hidden="true">▼</span>
          </button>
          <div class="sheetSwipeStrip" id="sheetSwipeStrip">
            <div class="forecastHeader">
              <p id="detailScreenLabel">POI / place detail</p>
              <span>forecast</span>
            </div>
            <div class="forecastTitle" id="forecastTitleText">Select a place on the map or via search</div>
            <div class="forecastLevelRow">
              <div>
                <div class="forecastLabel" id="forecastCrowdLabel">Crowd signal</div>
                <div class="forecastLevel" id="forecastLevelText">—</div>
              </div>
              <div>
                <div class="forecastLabel">Crowd index</div>
                <div class="forecastScore"><span id="forecastScoreText">—</span><small>/100</small></div>
              </div>
            </div>
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
        <div class="mapHUD">
          <div class="hudTitle">On-map selection</div>
          <div class="hudRow">
            <span>Type</span>
            <span id="hudKindText">—</span>
          </div>
          <div class="hudRow">
            <span>Coordinates</span>
            <span id="hudCoordText">—</span>
          </div>
        </div>
      </section>

      <div class="mobileNavBar" aria-label="Navigation">
        <button id="openMapsBtnMobile" class="btn btnPrimary" type="button" disabled>
          Open in Google Maps
        </button>
      </div>
    </div>

    <section class="insightGrid">
      <article class="insightCard">
        <h3>How it decides</h3>
        <p>
          Weekly Istanbul pressure from the notebook pipeline (trends, weather, seasonality, holidays). The same
          city-wide index is shown for every pin until per-venue data exists.
        </p>
      </article>
      <article class="insightCard">
        <h3>What this UI proves</h3>
        <p>Search, map interactions, and location-based selection are already production-style and ready for API wiring.</p>
      </article>
      <article class="insightCard">
        <h3>Navigation handoff</h3>
        <p>After you confirm a place, Google Maps opens for real-world directions—the last step in the target UX flow.</p>
      </article>
    </section>

    <div class="footerNote">
      Forecast uses the bundled weekly model CSV when the Flask API runs with data files; scope is city-wide, not
      measured footfall at each venue.
    </div>
  </div>
`

function el<T extends HTMLElement>(id: string): T {
  const node = document.getElementById(id)
  if (!node) throw new Error(`Missing element #${id}`)
  return node as T
}

function formatCoord(p: LatLng) {
  return `${p.lat.toFixed(5)}, ${p.lng.toFixed(5)}`
}

function dotColor(kind: SelectionKind): string {
  return kind === 'hotel'
    ? 'var(--accentA)'
    : kind === 'poi'
      ? 'var(--accentB)'
      : kind === 'location'
        ? 'var(--accentC)'
        : 'var(--accentD)'
}

function kindLabel(kind: SelectionKind): string {
  switch (kind) {
    case 'hotel':
      return 'Hotel'
    case 'location':
      return 'Current location'
    case 'poi':
      return 'Point of interest'
    case 'map':
      return 'Pinned location'
  }
}

function getHorizonWeeks(): number {
  const node = document.getElementById('filterWhen') as HTMLSelectElement | null
  const n = Number(node?.value)
  return n >= 1 && n <= 52 ? n : 4
}

function getCategoryFilter(): string {
  const node = document.getElementById('filterCategory') as HTMLSelectElement | null
  const v = node?.value ?? 'all'
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
    warnTitle.textContent = 'High city-wide pressure this week'
    warnBody.textContent =
      'The model estimates pressure for Istanbul as a whole—not a live queue at this pin. Nearby places are for exploration; they are not ranked as “quieter” from venue counts.'
    altTitle.textContent = 'Other places nearby'
  } else if (!showRecommendations) {
    warnTitle.textContent = 'High (demo scoring)'
    warnBody.textContent =
      'Demo mode uses a placeholder score. Bundle the weekly CSV in the API for a real city-wide index.'
    altTitle.textContent = 'Alternatives nearby'
  }

  const cat = getCategoryFilter()

  try {
    const data = await fetchRecommendations({
      origin: sel.latlng,
      timestamp: new Date().toISOString(),
      radiusKm: showRecommendations ? 10 : 25,
      topK: showRecommendations ? 6 : 4,
      includeItinerary: false,
      ...(cat ? { allowedCategories: [cat] } : {})
    })
    const recs = data.recommendations
    if (recs.length === 0) {
      list.innerHTML =
        '<p class="altEmpty">No ranked POIs for this pin—try another category or widen the map.</p>'
      return
    }
    for (const rec of recs) {
      const name = String(rec.name ?? 'Place')
      const dist = rec.distance_km
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
      const metaCat = String(rec.category ?? '')
      const b = document.createElement('button')
      b.type = 'button'
      b.className = 'altPoiBtn'
      b.setAttribute('role', 'listitem')
      b.innerHTML = `<span class="altPoiName">${name}</span><span class="altPoiMeta">${metaCat} · ${distLabel}</span>`
      const ll = pickLatLngFromRankedRec(rec)
      if (ll) {
        b.addEventListener('click', () => {
          const next: MapSelection = { latlng: ll, label: name, kind: 'location' }
          currentSelection = next
          setChip(next)
          map.setMarker(next, { flyTo: true })
        })
      }
      list.appendChild(b)
    }
  } catch {
    list.innerHTML =
      '<p class="altEmpty">Recommendations unavailable—start the Flask API on port 8080.</p>'
  }
}

function setChip(selection: MapSelection | null) {
  const dot = el<HTMLElement>('selectionChipDot')
  const kindText = el<HTMLSpanElement>('selectionKindText')
  const labelText = el<HTMLDivElement>('selectionLabelText')
  const coordsText = el<HTMLSpanElement>('selectionCoordsText')
  const hudKind = el<HTMLSpanElement>('hudKindText')
  const hudCoord = el<HTMLSpanElement>('hudCoordText')
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

  if (!selection) {
    dot.style.background = 'transparent'
    kindText.textContent = '—'
    labelText.textContent = 'Click map or choose a hotel'
    coordsText.textContent = '—'
    hudKind.textContent = '—'
    hudCoord.textContent = '—'
    forecastTitle.textContent = 'Select a place on the map or via search'
    forecastInterpretation.textContent = ''
    forecastCrowdLabel.textContent = 'Crowd signal'
    forecastLevel.textContent = '—'
    forecastScore.textContent = '—'
    forecastTrend.textContent = 'Awaiting selection…'
    areaTrafficText.textContent = '—'
    bestTimeText.textContent = '—'
    detailScreenLabel.textContent = 'POI / place detail'
    crowdedWarning.hidden = true
    alternativesBlock.hidden = true
    alternativesList.innerHTML = ''
    openMapsBtn.disabled = true
    if (openMapsBtnMobile) openMapsBtnMobile.disabled = true
    return
  }

  openMapsBtn.disabled = false
  if (openMapsBtnMobile) openMapsBtnMobile.disabled = false
  detailScreenLabel.textContent = selection.kind === 'poi' ? 'POI detail' : 'Place detail'
  dot.style.background = dotColor(selection.kind)
  kindText.textContent = kindLabel(selection.kind)
  labelText.textContent = selection.label
  coordsText.textContent = formatCoord(selection.latlng)
  hudKind.textContent = kindLabel(selection.kind)
  hudCoord.textContent = formatCoord(selection.latlng)
  forecastTitle.textContent = selection.label
  forecastLevel.textContent = '…'
  forecastScore.textContent = '…'
  forecastTrend.textContent = 'Fetching forecast from API…'
  areaTrafficText.textContent = '…'
  bestTimeText.textContent = '…'
  forecastInterpretation.textContent = ''
  crowdedWarning.hidden = true
  alternativesBlock.hidden = true
  alternativesList.innerHTML = ''

  const horizon = getHorizonWeeks()
  forecast({ kind: selection.kind, label: selection.label, latlng: selection.latlng }, horizon)
    .then((res) => {
      if (!currentSelection) return
      if (currentSelection.label !== selection.label || currentSelection.kind !== selection.kind) return
      forecastLevel.textContent = res.level
      forecastScore.textContent = String(res.score)
      forecastTrend.textContent = res.trend
      const scope = res.forecastScope ?? 'demo'
      let interp = res.interpretation?.trim() ?? ''
      if (res.basisWeekStart) {
        interp = interp ? `${interp} Data week: ${res.basisWeekStart}.` : `Data week: ${res.basisWeekStart}.`
      }
      forecastInterpretation.textContent = interp

      if (scope === 'city_wide') {
        forecastCrowdLabel.textContent = 'City this week'
        areaTrafficText.textContent = `${res.level} (city-wide, not road API)`
      } else {
        forecastCrowdLabel.textContent = 'Demo score'
        areaTrafficText.textContent = areaTrafficLevel(res.score)
      }
      bestTimeText.textContent = bestTimeHint(res.level)
      void fillAlternativesIfCrowded(selection, res.level, scope)
    })
    .catch(() => {
      forecastLevel.textContent = '—'
      forecastScore.textContent = '—'
      forecastTrend.textContent = 'Backend not reachable (start Flask API on :8080)'
      areaTrafficText.textContent = '—'
      bestTimeText.textContent = '—'
      forecastInterpretation.textContent = ''
      crowdedWarning.hidden = true
      alternativesBlock.hidden = true
      alternativesList.innerHTML = ''
    })
}

const tabHotels = el<HTMLButtonElement>('tabHotels')
const tabLocation = el<HTMLButtonElement>('tabLocation')
const panelHotels = el<HTMLDivElement>('panelHotels')
const panelLocation = el<HTMLDivElement>('panelLocation')

function setActiveTab(tab: 'hotels' | 'location') {
  const hotelsActive = tab === 'hotels'
  tabHotels.classList.toggle('isActive', hotelsActive)
  tabHotels.setAttribute('aria-selected', String(hotelsActive))
  tabHotels.style.opacity = hotelsActive ? '1' : '0.86'

  tabLocation.classList.toggle('isActive', !hotelsActive)
  tabLocation.setAttribute('aria-selected', String(!hotelsActive))
  tabLocation.style.opacity = !hotelsActive ? '1' : '0.86'

  panelHotels.hidden = !hotelsActive
  panelLocation.hidden = hotelsActive
}

tabHotels.addEventListener('click', () => setActiveTab('hotels'))
tabLocation.addEventListener('click', () => setActiveTab('location'))

const hotelPickerInput = el<HTMLInputElement>('hotelPickerInput')
const hotelPickerResults = el<HTMLDivElement>('hotelPickerResults')
const globalSearchInput = el<HTMLInputElement>('globalSearchInput')
const globalSearchResults = el<HTMLDivElement>('globalSearchResults')

function clearResults(container: HTMLDivElement) {
  container.innerHTML = ''
}

function showEmpty(container: HTMLDivElement, text: string) {
  clearResults(container)
  const row = document.createElement('div')
  row.className = 'resultItem'
  row.style.cursor = 'default'
  row.innerHTML = `
    <div class="resultBadge" style="opacity:0.7">Prototype</div>
    <div class="resultMain">
      <div class="resultName">No matches</div>
      <div class="resultMeta">${text}</div>
    </div>
  `
  container.appendChild(row)
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

function makeRankedRecommendationRow(rec: RankedRecommendation): HTMLElement {
  const row = document.createElement('div')
  row.className = 'resultItem'
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
  const score = rec.score

  const badge = document.createElement('div')
  badge.className = 'resultBadge'
  badge.textContent = 'Ranked'

  const main = document.createElement('div')
  main.className = 'resultMain'
  const title = document.createElement('div')
  title.className = 'resultName'
  title.textContent = name
  const meta = document.createElement('div')
  meta.className = 'resultMeta'
  const metaBits = [cat, distStr, crowd ? `crowd ${crowd}` : '', typeof score === 'number' ? `score ${score.toFixed(3)}` : '']
  meta.textContent = metaBits.filter(Boolean).join(' · ')
  main.appendChild(title)
  main.appendChild(meta)
  if (expl.trim()) {
    const detail = document.createElement('div')
    detail.className = 'resultMeta'
    detail.style.marginTop = '6px'
    detail.style.fontSize = '0.9em'
    detail.style.opacity = '0.95'
    detail.textContent = expl
    main.appendChild(detail)
  }

  row.appendChild(badge)
  row.appendChild(main)

  const ll = pickLatLngFromRankedRec(rec)
  if (ll) {
    row.addEventListener('click', () => {
      const sel: MapSelection = { latlng: ll, label: name, kind: 'location' }
      currentSelection = sel
      setChip(sel)
      map.setMarker(sel, { flyTo: true })
    })
    row.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') {
        const sel: MapSelection = { latlng: ll, label: name, kind: 'location' }
        currentSelection = sel
        setChip(sel)
        map.setMarker(sel, { flyTo: true })
      }
    })
  }

  return row
}

async function showNearbyMatches(origin: LatLng) {
  setLoading(globalSearchResults)
  const cat = getCategoryFilter()
  try {
    const data = await fetchRecommendations({
      origin,
      timestamp: new Date().toISOString(),
      radiusKm: 5,
      topK: 10,
      includeItinerary: false,
      ...(cat ? { allowedCategories: [cat] } : {})
    })
    clearResults(globalSearchResults)
    const recs = data.recommendations
    if (recs.length === 0) {
      showEmpty(
        globalSearchResults,
        'No ranked POIs for this area—try another category or use search.'
      )
      return
    }
    for (const rec of recs) {
      globalSearchResults.appendChild(makeRankedRecommendationRow(rec))
    }
  } catch {
    showEmpty(
      globalSearchResults,
      'Could not load ranked POIs. Start the Flask API on port 8080 (backend-python).'
    )
  }
}

function setLoading(container: HTMLDivElement) {
  clearResults(container)
  const row = document.createElement('div')
  row.className = 'resultItem'
  row.style.cursor = 'default'
  row.innerHTML = `
    <div class="resultBadge" style="opacity:0.8">Loading</div>
    <div class="resultMain">
      <div class="resultName">Searching Istanbul…</div>
      <div class="resultMeta">Calling /api/recommendations…</div>
    </div>
  `
  container.appendChild(row)
}

function makeHotelRow(hotel: Hotel): HTMLElement {
  const row = document.createElement('div')
  row.className = 'resultItem'
  row.setAttribute('role', 'option')
  row.tabIndex = 0
  row.dataset.id = hotel.id

  row.innerHTML = `
    <div class="resultBadge">Hotel</div>
    <div class="resultMain">
      <div class="resultName">${hotel.name}</div>
      <div class="resultMeta">${hotel.district} • ${hotel.rating.toFixed(1)}★ • from $${hotel.priceFrom}</div>
    </div>
  `

  row.addEventListener('click', () => selectHotel(hotel))
  row.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') selectHotel(hotel)
  })
  return row
}

function makePoiRow(poi: Poi): HTMLElement {
  const row = document.createElement('div')
  row.className = 'resultItem'
  row.setAttribute('role', 'option')
  row.tabIndex = 0
  row.dataset.id = poi.id

  row.innerHTML = `
    <div class="resultBadge">POI</div>
    <div class="resultMain">
      <div class="resultName">${poi.name}</div>
      <div class="resultMeta">${poi.category}</div>
    </div>
  `

  row.addEventListener('click', () => selectPoi(poi))
  row.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') selectPoi(poi)
  })
  return row
}

let currentSelection: MapSelection | null = null

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

function runHotelPicker(query: string) {
  setLoading(hotelPickerResults)
  searchHotels(query)
    .then((hotels) => {
      clearResults(hotelPickerResults)
      if (hotels.length === 0) {
        showEmpty(hotelPickerResults, 'Try a district like “Sultanahmet” or “Beyoğlu”.')
        return
      }
      for (const hotel of hotels) hotelPickerResults.appendChild(makeHotelRow(hotel))
    })
    .catch(() => {
      showEmpty(hotelPickerResults, 'Mock search failed. Reload the page.')
    })
}

function debounce<T extends unknown[]>(fn: (...args: T) => void, ms: number) {
  let timer: number | null = null
  return (...args: T) => {
    if (timer) window.clearTimeout(timer)
    timer = window.setTimeout(() => fn(...args), ms)
  }
}

const debouncedHotelPicker = debounce((value: string) => runHotelPicker(value), 220)

hotelPickerInput.addEventListener('input', () => {
  debouncedHotelPicker(hotelPickerInput.value)
})

hotelPickerInput.addEventListener('focus', () => {
  if (!hotelPickerInput.value.trim()) runHotelPicker('')
})

globalSearchInput.addEventListener('input', () => {
  debouncedGlobalSearch(globalSearchInput.value)
})

const debouncedGlobalSearch = debounce((query: string) => {
  setLoading(globalSearchResults)
  searchEverything(query)
    .then((items) => {
      clearResults(globalSearchResults)
      const filtered = applyCategoryToSearchResults(items)
      if (filtered.length === 0) {
        showEmpty(
          globalSearchResults,
          items.length === 0
            ? 'Try “Hagia Sophia”, “Grand Bazaar”, or a district name.'
            : 'No matches for this category—set category to “All categories”.'
        )
        return
      }
      for (const item of filtered) {
        if (item.kind === 'hotel') globalSearchResults.appendChild(makeHotelRow(item.hotel))
        else globalSearchResults.appendChild(makePoiRow(item.poi))
      }
    })
    .catch(() => showEmpty(globalSearchResults, 'Search failed. Reload the page.'))
}, 220)

globalSearchInput.addEventListener('focus', () => {
  if (!globalSearchInput.value.trim()) {
    setLoading(globalSearchResults)
    searchEverything('')
      .then((items) => {
        clearResults(globalSearchResults)
        const filtered = applyCategoryToSearchResults(items)
        if (filtered.length === 0) {
          showEmpty(globalSearchResults, 'No matches for this category—set category to “All categories”.')
          return
        }
        for (const item of filtered) {
          if (item.kind === 'hotel') globalSearchResults.appendChild(makeHotelRow(item.hotel))
          else globalSearchResults.appendChild(makePoiRow(item.poi))
        }
      })
      .catch(() => showEmpty(globalSearchResults, 'Suggestions failed.'))
  }
})

const locationStatus = el<HTMLDivElement>('locationStatus')
const useMyLocationBtn = el<HTMLButtonElement>('useMyLocationBtn')
const filterCategory = el<HTMLSelectElement>('filterCategory')
const filterWhen = el<HTMLSelectElement>('filterWhen')

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
      setChip(currentSelection)
      map.setMarker(currentSelection, { flyTo: true })
      void showNearbyMatches(selection.latlng)
      statusEl.textContent =
        'Location set on the Istanbul map. Tap the map to fine-tune or search for a POI.'
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
}

filterCategory.addEventListener('change', onFilterChange)
filterWhen.addEventListener('change', onFilterChange)

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
  const SWIPE_PX = 52
  let ignoreNextToggleClick = false

  const sync = () => {
    if (!mq.matches) {
      collapsed = false
      sheetRoot.classList.remove('isCollapsed')
      mapStage.classList.remove('hasCollapsedSheet')
      sheetToggle.setAttribute('aria-expanded', 'true')
      sheetToggle.setAttribute('aria-label', 'Collapse place detail')
      return
    }
    sheetRoot.classList.toggle('isCollapsed', collapsed)
    mapStage.classList.toggle('hasCollapsedSheet', collapsed)
    sheetToggle.setAttribute('aria-expanded', String(!collapsed))
    sheetToggle.setAttribute('aria-label', collapsed ? 'Expand place detail' : 'Collapse place detail')
  }

  const applyResize = () => window.dispatchEvent(new Event('resize'))

  sheetToggle.addEventListener('click', () => {
    if (!mq.matches) return
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

  mq.addEventListener('change', sync)
  sync()
}

initForecastSheetCollapse()

// Ask for location permission right away (for “open app → GPS → recommendations” flow).
// If denied, the user can still search or tap the map.
window.setTimeout(() => {
  setActiveTab('location')
  startGeolocation(locationStatus)
}, 160)
setChip(null)
runHotelPicker('')

