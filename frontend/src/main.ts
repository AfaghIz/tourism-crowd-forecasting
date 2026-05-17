import './app.css'
import 'leaflet/dist/leaflet.css'

import { createMap } from './map/mapController'
import {
  listPois,
  listForecastPeriods,
  searchEverything,
  fetchRecommendations,
  type Poi,
  type ForecastPeriodOption,
  type RankedRecommendation,
  type SearchResult,
  forecast
} from './api/api'
import type { LatLng, MapSelection, SelectionKind } from './domain/types'

type AppSelection = MapSelection & {
  entityId?: string
}

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
  if (crowdLevel === 'High') return 'Try an earlier or later visit if you want a calmer stop.'
  if (crowdLevel === 'Medium') return 'A little planning helps here; quieter hours are usually easier.'
  return 'This stop looks manageable for most visits.'
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
              Pick a landmark, get a quick crowd read, and decide whether to stay with it or switch to a nearby alternative.
            </p>
          </div>
        </div>

        <div class="apiPill" title="Backend API (Flask)">
          <div class="apiDot" aria-hidden="true"></div>
          <span>Flask API (localhost:8080)</span>
        </div>
      </div>
    </div>

    <div class="layout">
      <div class="panel">
        <section class="card">
          <div class="flowBlock">
            <div class="fieldLabel">
              <span>Starting point</span>
              <span class="hint">optional</span>
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
                  <span>Modeled period</span>
                  <span class="hint">demo control</span>
                </div>
                <select id="forecastPeriod" class="select" aria-label="Choose modeled forecast period">
                  <option value="">Latest modeled week</option>
                </select>
              </div>
            </div>
          </div>

          <div class="cardTitleRow" style="margin-top: 14px">
            <h2>Map Selection</h2>
            <div class="hint">Current location or map tap</div>
          </div>

          <div class="hint" style="margin-top:10px">
            Use your current location, tap the map, or search for a landmark below.
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
              <div class="selectionLabel" id="selectionLabelText">Search for a landmark or tap the map</div>
            </div>
            <div class="coords">
              <span>Coordinates</span>
              <span id="selectionCoordsText">—</span>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="cardTitleRow">
            <h2>Landmark Search</h2>
            <div class="hint">POIs only</div>
          </div>

          <div class="fieldLabel">
            <span>Find a landmark</span>
            <span class="hint">anchor for alternatives</span>
          </div>
          <input
            id="globalSearchInput"
            class="input"
            type="text"
            placeholder="Search landmarks like Hagia Sophia or Galata Tower…"
            autocomplete="off"
            spellcheck="false"
          />
          <div id="globalSearchResults" class="results" aria-live="polite" role="listbox"></div>

          <div class="hint" style="margin-top:10px">
            Pick a landmark to trigger crowd-aware alternative suggestions nearby.
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
            </div>
            <div class="forecastTitle" id="forecastTitleText">Select a place on the map or via search</div>
            <div class="forecastLevelRow">
              <div>
                <div class="forecastLabel" id="forecastCrowdLabel">Expected crowd</div>
                <div class="forecastLevel" id="forecastLevelText">—</div>
              </div>
              <div>
                <div class="forecastLabel">Crowd level</div>
                <div class="forecastScore"><span id="forecastScoreText">—</span><small>/100</small></div>
              </div>
            </div>
          </div>
          <div id="forecastSheetCollapsible" class="sheetCollapsible">
            <p class="forecastInterpret" id="forecastInterpretation"></p>
            <div class="detailExtra">
              <div class="miniRow">
                <span class="miniLabel">City activity</span>
                <span class="miniValue" id="areaTrafficText">—</span>
              </div>
              <div class="miniRow">
                <span class="miniLabel">Visit note</span>
                <span class="miniHint" id="bestTimeText">—</span>
              </div>
            </div>
            <div id="crowdedWarning" class="crowdedWarn" hidden>
              <strong id="crowdedWarnTitle">Crowd update</strong>
              <p id="crowdedWarnBody">
                We’ll tell you whether this place looks manageable or whether it’s worth switching nearby.
              </p>
            </div>
            <div id="alternativesBlock" class="altBlock" hidden>
              <div class="altTitle" id="alternativesTitle">Nearby alternatives</div>
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

      <div class="mobileNavBar" aria-label="Navigation">
        <button id="openMapsBtnMobile" class="btn btnPrimary" type="button" disabled>
          Open in Google Maps
        </button>
      </div>
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
  return 4
}

function getSelectedForecastPeriod(): string | undefined {
  const node = document.getElementById('forecastPeriod') as HTMLSelectElement | null
  const value = node?.value?.trim() ?? ''
  return value || undefined
}

function getEffectiveForecastPeriodStart(): string | undefined {
  return getSelectedForecastPeriod() || forecastPeriods[0]?.id
}

function getModeledTimestampIso(): string {
  const basis = getEffectiveForecastPeriodStart()
  return basis ? `${basis}T12:00:00` : new Date().toISOString()
}

function getCategoryFilter(): string {
  const node = document.getElementById('filterCategory') as HTMLSelectElement | null
  const v = node?.value ?? 'all'
  return v === 'all' ? '' : v
}

function applyCategoryToSearchResults(items: SearchResult[]): SearchResult[] {
  const cat = getCategoryFilter()
  return items.filter((i) => i.kind === 'poi' && (!cat || i.poi.category === cat))
}

function googleMapsDirectionsUrl(sel: MapSelection): string {
  const { lat, lng } = sel.latlng
  return `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(`${lat},${lng}`)}`
}

function pickPoiIdFromRankedRec(rec: RankedRecommendation): string | null {
  const raw = rec.poi_id ?? rec.id
  if (typeof raw !== 'string') return null
  const trimmed = raw.trim()
  return trimmed ? trimmed : null
}

async function fillAlternativesIfCrowded(sel: AppSelection, crowdLevel: string, forecastScope: string) {
  const warn = el<HTMLDivElement>('crowdedWarning')
  const block = el<HTMLDivElement>('alternativesBlock')
  const list = el<HTMLDivElement>('alternativesList')
  const warnTitle = el<HTMLElement>('crowdedWarnTitle')
  const warnBody = el<HTMLParagraphElement>('crowdedWarnBody')
  const altTitle = el<HTMLDivElement>('alternativesTitle')

  const showRecommendations = sel.kind === 'location'
  const showAnchorAlternatives = sel.kind === 'poi' && typeof sel.entityId === 'string'
  const isHighCrowd = crowdLevel === 'High'
  const isMediumCrowd = crowdLevel === 'Medium'
  const shouldOfferAlternatives = isHighCrowd || isMediumCrowd

  warn.classList.remove('isCalm')
  list.innerHTML = ''
  if (showRecommendations && shouldOfferAlternatives) {
    warn.hidden = false
    block.hidden = false
    altTitle.textContent = 'Places nearby'
    warnTitle.textContent = isHighCrowd ? 'Busy right now' : 'Calmer options nearby'
    warnBody.textContent = isHighCrowd
      ? 'This area looks busy enough that a nearby switch may help.'
      : 'This area looks manageable, but these nearby options may feel a bit calmer.'
  } else if (showRecommendations) {
    warn.hidden = true
    block.hidden = true
    return
  } else if (showAnchorAlternatives && shouldOfferAlternatives) {
    warn.hidden = false
    block.hidden = false
    altTitle.textContent = `Nearby alternatives to ${sel.label}`
    warnTitle.textContent = isHighCrowd ? 'Try a nearby alternative' : 'Calmer alternatives if you want them'
    warnBody.textContent = isHighCrowd
      ? 'This landmark looks busy. The list below favors nearby options that keep a similar feel with less pressure.'
      : 'This landmark looks manageable, but the list below highlights nearby options with a similar feel and lower pressure.'
  } else if (showAnchorAlternatives) {
    warn.hidden = false
    block.hidden = true
    warn.classList.add('isCalm')
    warnTitle.textContent = 'You are good to go'
    warnBody.textContent =
      'This landmark looks relatively calm right now, so there is no strong reason to switch away from it.'
    return
  } else {
    warn.hidden = true
    block.hidden = true
    return
  }

  if (!showRecommendations && forecastScope === 'city_wide') {
    warnTitle.textContent = isHighCrowd ? 'Try a nearby alternative' : 'Calmer alternatives if you want them'
    warnBody.textContent = isHighCrowd
      ? 'This landmark looks busy enough that a nearby switch may give you a more comfortable visit.'
      : 'This landmark does not look overloaded, but these nearby alternatives may offer a calmer visit.'
  }

  const cat = getCategoryFilter()

  try {
    const data = await fetchRecommendations({
      origin: sel.latlng,
      timestamp: getModeledTimestampIso(),
      radiusKm: showRecommendations ? 10 : showAnchorAlternatives ? 6 : 25,
      topK: showRecommendations ? 4 : showAnchorAlternatives ? 3 : 4,
      includeItinerary: false,
      ...(showAnchorAlternatives
        ? { anchorPoiId: sel.entityId, anchorRadiusKm: 3 }
        : cat
          ? { allowedCategories: [cat] }
          : {})
    })
    const recs = data.recommendations
    if (recs.length === 0) {
      list.innerHTML = showAnchorAlternatives
        ? '<p class="altEmpty">No strong nearby alternative stood out for this landmark.</p>'
        : '<p class="altEmpty">No strong nearby places stood out for this area.</p>'
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
      const crowd = String(rec.crowd_level_label ?? '')
      const explanation = String(rec.explanation ?? rec.explanation_text ?? '')
      const b = document.createElement('button')
      b.type = 'button'
      b.className = 'altPoiBtn'
      b.setAttribute('role', 'listitem')
      const metaBits = [metaCat, distLabel, crowd ? `crowd ${crowd}` : ''].filter(Boolean)
      const nameEl = document.createElement('span')
      nameEl.className = 'altPoiName'
      nameEl.textContent = name

      const metaEl = document.createElement('span')
      metaEl.className = 'altPoiMeta'
      metaEl.textContent = metaBits.join(' · ')

      b.appendChild(nameEl)
      b.appendChild(metaEl)

      if (explanation.trim()) {
        const explanationEl = document.createElement('span')
        explanationEl.className = 'altPoiMeta altPoiExplanation'
        explanationEl.textContent = explanation
        b.appendChild(explanationEl)
      }
      const ll = pickLatLngFromRankedRec(rec)
      const poiId = pickPoiIdFromRankedRec(rec)
      if (ll) {
        b.addEventListener('click', () => {
          const next: AppSelection = { latlng: ll, label: name, kind: poiId ? 'poi' : 'location', ...(poiId ? { entityId: poiId } : {}) }
          currentSelection = next
          setChip(next)
          map.setMarker(next, { flyTo: true })
        })
      }
      list.appendChild(b)
    }
  } catch {
    list.innerHTML = '<p class="altEmpty">Nearby alternatives are unavailable right now.</p>'
  }
}

function setChip(selection: AppSelection | null) {
  const dot = el<HTMLElement>('selectionChipDot')
  const kindText = el<HTMLSpanElement>('selectionKindText')
  const labelText = el<HTMLDivElement>('selectionLabelText')
  const coordsText = el<HTMLSpanElement>('selectionCoordsText')
  const forecastTitle = el<HTMLDivElement>('forecastTitleText')
  const forecastLevel = el<HTMLDivElement>('forecastLevelText')
  const forecastScore = el<HTMLSpanElement>('forecastScoreText')
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
  const locationStatus = el<HTMLDivElement>('locationStatus')

  if (!selection) {
    dot.style.background = 'transparent'
    kindText.textContent = '—'
    labelText.textContent = 'Search for a landmark or tap the map'
    coordsText.textContent = '—'
    forecastTitle.textContent = 'Select a place on the map or via search'
    forecastInterpretation.textContent = ''
    forecastCrowdLabel.textContent = 'Expected crowd'
    forecastLevel.textContent = '—'
    forecastScore.textContent = '—'
    areaTrafficText.textContent = '—'
    bestTimeText.textContent = '—'
    detailScreenLabel.textContent = 'POI / place detail'
    crowdedWarning.classList.remove('isCalm')
    crowdedWarning.hidden = true
    alternativesBlock.hidden = true
    alternativesList.innerHTML = ''
    openMapsBtn.disabled = true
    if (openMapsBtnMobile) openMapsBtnMobile.disabled = true
    locationStatus.textContent = ''
    return
  }

  openMapsBtn.disabled = false
  if (openMapsBtnMobile) openMapsBtnMobile.disabled = false
  detailScreenLabel.textContent = selection.kind === 'poi' ? 'POI detail' : 'Place detail'
  dot.style.background = dotColor(selection.kind)
  kindText.textContent = kindLabel(selection.kind)
  labelText.textContent = selection.label
  coordsText.textContent = formatCoord(selection.latlng)
  forecastTitle.textContent = selection.label
  forecastLevel.textContent = '…'
  forecastScore.textContent = '…'
  areaTrafficText.textContent = '…'
  bestTimeText.textContent = '…'
  forecastInterpretation.textContent = ''
  crowdedWarning.classList.remove('isCalm')
  crowdedWarning.hidden = true
  alternativesBlock.hidden = true
  alternativesList.innerHTML = ''

  const horizon = getHorizonWeeks()
  const basisWeekStart = getSelectedForecastPeriod()
  forecast(
    {
      kind: selection.kind,
      label: selection.label,
      latlng: selection.latlng,
      entityId: selection.entityId
    },
    horizon,
    basisWeekStart
  )
    .then((res) => {
      if (!currentSelection) return
      if (currentSelection.label !== selection.label || currentSelection.kind !== selection.kind) return
      forecastLevel.textContent = res.level
      forecastScore.textContent = String(res.score)
      const scope = res.forecastScope ?? 'demo'
      const cityLevel = res.cityLevel ?? res.level
      const cityScore = res.cityScore ?? res.score
      const basisLabel = res.basisLabel?.trim()
      const interpretation = res.interpretation?.trim() ?? ''
      forecastInterpretation.textContent =
        basisLabel && interpretation ? `${basisLabel}. ${interpretation}` : basisLabel || interpretation
      forecastCrowdLabel.textContent = res.scoreLabel?.trim() || 'Expected crowd'
      areaTrafficText.textContent =
        scope === 'city_wide' ? `${cityLevel} across the city · ${cityScore}/100` : areaTrafficLevel(cityScore)
      bestTimeText.textContent = bestTimeHint(res.level)
      locationStatus.textContent = basisLabel
        ? `Using ${basisLabel.toLowerCase()} for the crowd view.`
        : ''
      void fillAlternativesIfCrowded(selection, res.level, scope)
    })
    .catch(() => {
      forecastLevel.textContent = '—'
      forecastScore.textContent = '—'
      areaTrafficText.textContent = '—'
      bestTimeText.textContent = '—'
      forecastInterpretation.textContent = 'We could not load the current crowd read right now.'
      crowdedWarning.hidden = true
      alternativesBlock.hidden = true
      alternativesList.innerHTML = ''
      locationStatus.textContent = ''
    })
}

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
      timestamp: getModeledTimestampIso(),
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

let currentSelection: AppSelection | null = null
let defaultMapPois: Poi[] = []
let forecastPeriods: ForecastPeriodOption[] = []

const map = createMap(el<HTMLDivElement>('map'), {
  defaultCenter: DEFAULT_CENTER,
  onSelect: (selection) => {
    currentSelection = selection
    setChip(currentSelection)
  }
})

function filteredMapPois(): Poi[] {
  const cat = getCategoryFilter()
  const visible = cat ? defaultMapPois.filter((poi) => poi.category === cat) : defaultMapPois
  return visible.slice(0, 80)
}

function renderDefaultPoiMarkers() {
  const pois = filteredMapPois()
  map.setPoiMarkers(
    pois.map((poi) => ({
      id: poi.id,
      name: poi.name,
      category: poi.category,
      lat: poi.lat,
      lng: poi.lng
    })),
    (poiId) => {
      const poi = defaultMapPois.find((item) => item.id === poiId)
      if (poi) selectPoi(poi)
    }
  )
}

async function loadDefaultPoiMarkers() {
  try {
    defaultMapPois = await listPois(80)
    renderDefaultPoiMarkers()
  } catch {
    defaultMapPois = []
    renderDefaultPoiMarkers()
  }
}

function selectPoi(poi: Poi) {
  currentSelection = {
    latlng: { lat: poi.lat, lng: poi.lng },
    label: poi.name,
    kind: 'poi',
    entityId: poi.id
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
        if (item.kind === 'poi') globalSearchResults.appendChild(makePoiRow(item.poi))
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
          if (item.kind === 'poi') globalSearchResults.appendChild(makePoiRow(item.poi))
        }
      })
      .catch(() => showEmpty(globalSearchResults, 'Suggestions failed.'))
  }
})

const locationStatus = el<HTMLDivElement>('locationStatus')
const useMyLocationBtn = el<HTMLButtonElement>('useMyLocationBtn')
const filterCategory = el<HTMLSelectElement>('filterCategory')
const forecastPeriod = el<HTMLSelectElement>('forecastPeriod')

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
  renderDefaultPoiMarkers()
  if (currentSelection) setChip(currentSelection)
}

filterCategory.addEventListener('change', onFilterChange)
forecastPeriod.addEventListener('change', () => {
  if (currentSelection) setChip(currentSelection)
})

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

function renderForecastPeriods() {
  forecastPeriod.innerHTML = ''

  const latestOption = document.createElement('option')
  latestOption.value = ''
  latestOption.textContent = 'Latest modeled week'
  forecastPeriod.appendChild(latestOption)

  for (const option of forecastPeriods) {
    const node = document.createElement('option')
    node.value = option.id
    node.textContent = `${option.label} · ${option.level}`
    forecastPeriod.appendChild(node)
  }
}

async function loadForecastPeriods() {
  try {
    forecastPeriods = await listForecastPeriods()
  } catch {
    forecastPeriods = []
  }
  renderForecastPeriods()
}

initForecastSheetCollapse()
void loadForecastPeriods()
void loadDefaultPoiMarkers()

// Ask for location permission right away (for “open app → GPS → recommendations” flow).
// If denied, the user can still search or tap the map.
window.setTimeout(() => {
  startGeolocation(locationStatus)
}, 160)
setChip(null)
