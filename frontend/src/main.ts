import './app.css'
import 'leaflet/dist/leaflet.css'

import { createMap } from './map/mapController'
import {
  searchHotels,
  searchEverything,
  type Hotel,
  type Poi,
  selectionKindLabel
} from './api/mockApi'
import type { LatLng, MapSelection, SelectionKind } from './domain/types'

const DEFAULT_CENTER: LatLng = { lat: 41.0082, lng: 28.9784 }

const root = document.querySelector<HTMLDivElement>('#app')
if (!root) throw new Error('Missing #app mount element')

root.innerHTML = `
  <div class="page">
    <div class="topbar">
      <div class="topbarInner">
        <div class="brand">
          <div class="brandMark" aria-hidden="true"></div>
          <div>
            <h1>Istanbul Crowd Compass</h1>
            <p>Prototype UI: select a hotel or point, then search (mock data for now).</p>
          </div>
        </div>

        <div class="apiPill" title="Mock data layer; replace with real API later">
          <div class="apiDot" aria-hidden="true"></div>
          <span>Mock API (wire real endpoints later)</span>
        </div>
      </div>
    </div>

    <div class="layout">
      <div class="panel">
        <section class="card">
          <div class="cardTitleRow">
            <h2>Hotel & Location</h2>
            <div class="hint">Also works with map click</div>
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
            <div class="btnRow">
              <button id="useMyLocationBtn" class="btn btnPrimary" type="button">
                Use my location
              </button>
            </div>
            <div id="locationStatus" class="hint" style="margin-top:10px"></div>
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
            <span class="hint">prototype</span>
          </div>
          <input
            id="globalSearchInput"
            class="input"
            type="text"
            placeholder="Try: Hagia Sophia, Grand Bazaar, Bosphorus view..."
            autocomplete="off"
            spellcheck="false"
          />
          <div id="globalSearchResults" class="results" aria-live="polite" role="listbox"></div>

          <div class="hint" style="margin-top:10px">
            API seam: replace mock functions like <code>searchEverything()</code> with real endpoints.
          </div>
        </section>
      </div>

      <section class="mapWrap">
        <div id="map" class="map" aria-label="Interactive map (click to select)"></div>
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
    </div>

    <div class="footerNote">
      Prototype only. Map clicks and selectors are functional; real data wiring is left for later branches.
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

function setChip(selection: MapSelection | null) {
  const dot = el<HTMLElement>('selectionChipDot')
  const kindText = el<HTMLSpanElement>('selectionKindText')
  const labelText = el<HTMLDivElement>('selectionLabelText')
  const coordsText = el<HTMLSpanElement>('selectionCoordsText')
  const hudKind = el<HTMLSpanElement>('hudKindText')
  const hudCoord = el<HTMLSpanElement>('hudCoordText')

  if (!selection) {
    dot.style.background = 'transparent'
    kindText.textContent = '—'
    labelText.textContent = 'Click map or choose a hotel'
    coordsText.textContent = '—'
    hudKind.textContent = '—'
    hudCoord.textContent = '—'
    return
  }

  dot.style.background = dotColor(selection.kind)
  kindText.textContent = selectionKindLabel(selection.kind)
  labelText.textContent = selection.label
  coordsText.textContent = formatCoord(selection.latlng)
  hudKind.textContent = selectionKindLabel(selection.kind)
  hudCoord.textContent = formatCoord(selection.latlng)
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

function setLoading(container: HTMLDivElement) {
  clearResults(container)
  const row = document.createElement('div')
  row.className = 'resultItem'
  row.style.cursor = 'default'
  row.innerHTML = `
    <div class="resultBadge" style="opacity:0.8">Loading</div>
    <div class="resultMain">
      <div class="resultName">Searching Istanbul…</div>
      <div class="resultMeta">Mock endpoint (replace later)</div>
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
      if (items.length === 0) {
        showEmpty(globalSearchResults, 'Try “Hagia Sophia”, “Grand Bazaar”, or a district name.')
        return
      }
      for (const item of items) {
        if (item.kind === 'hotel') globalSearchResults.appendChild(makeHotelRow(item.hotel))
        else globalSearchResults.appendChild(makePoiRow(item.poi))
      }
    })
    .catch(() => showEmpty(globalSearchResults, 'Mock search failed. Reload the page.'))
}, 220)

globalSearchInput.addEventListener('focus', () => {
  if (!globalSearchInput.value.trim()) {
    setLoading(globalSearchResults)
    searchEverything('')
      .then((items) => {
        clearResults(globalSearchResults)
        for (const item of items) {
          if (item.kind === 'hotel') globalSearchResults.appendChild(makeHotelRow(item.hotel))
          else globalSearchResults.appendChild(makePoiRow(item.poi))
        }
      })
      .catch(() => showEmpty(globalSearchResults, 'Mock suggestions failed.'))
  }
})

const useMyLocationBtn = el<HTMLButtonElement>('useMyLocationBtn')
const locationStatus = el<HTMLDivElement>('locationStatus')

useMyLocationBtn.addEventListener('click', () => {
  locationStatus.textContent = ''

  if (!navigator.geolocation) {
    locationStatus.textContent = 'Geolocation not available in this browser.'
    return
  }

  locationStatus.textContent = 'Requesting location…'

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
      locationStatus.textContent = 'Location selected. Click map to fine-tune.'
    },
    () => {
      locationStatus.textContent = 'Could not access location. Try again or use map click.'
    },
    { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
  )
})

setActiveTab('hotels')
setChip(null)
runHotelPicker('')

