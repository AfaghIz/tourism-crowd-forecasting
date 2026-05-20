import * as L from 'leaflet'
import type { LatLng, MapSelection, SelectionKind } from '../domain/types'

export type MapController = {
  setMarker: (selection: MapSelection, options?: { flyTo?: boolean }) => void
  clearSelection: () => void
  setPoiMarkers: (
    pois: Array<{
      id: string
      name: string
      category: string
      lat: number
      lng: number
      crowdLevel?: 'Low' | 'Medium' | 'High'
      isSelected?: boolean
      isRecommended?: boolean
      isFaded?: boolean
    }>,
    selectedPoiId: string | null,
    recommendationLines: Array<{ lat: number; lng: number }>,
    onSelectPoi: (poiId: string) => void
  ) => void
  getCenter: () => LatLng
  /** Invalidate Leaflet size (e.g. after fullscreen toggle). */
  relayout: () => void
  destroy: () => void
}

function toLeafletLatLng(p: LatLng): L.LatLngExpression {
  return [p.lat, p.lng]
}

/** Tarboosh / fez for map-tap pins and geolocation (“you are here”), distinct from POI teardrop pins. */
function fezMarkerIcon(): L.Icon {
  const svg = `
  <svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" viewBox="-2 -2 60 60">
    <defs>
      <linearGradient id="fezBody" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#8c1a2e"/>
        <stop offset="45%" stop-color="#e01e3c"/>
        <stop offset="100%" stop-color="#6f1224"/>
      </linearGradient>
      <filter id="fezSh" x="-40%" y="-40%" width="180%" height="180%">
        <feDropShadow dx="0" dy="5" stdDeviation="4" flood-color="#000" flood-opacity="0.32"/>
      </filter>
    </defs>
    <g filter="url(#fezSh)">
      <g transform="rotate(-11 28 45.5)">
        <path d="M14 47 L17 27 Q28 21 39 27 L42 47 Z" fill="url(#fezBody)" stroke="#2a060c" stroke-width="1.15" stroke-linejoin="round"/>
        <path d="M11.5 44.5 h33 v5.5 h-33 z" fill="#12080c"/>
        <ellipse cx="28" cy="45" rx="15" ry="3" fill="#000" opacity="0.22"/>
        <path d="M28 22.5 Q26.8 16.5 25.8 12.2" stroke="#141010" stroke-width="1.85" fill="none" stroke-linecap="round"/>
        <circle cx="25.4" cy="9.8" r="3.9" fill="#141010"/>
        <path d="M21.8 11.2 L19.2 16.2 M24 10.2 L22.6 16.8 M26.2 9.6 L26.4 16.5 M28.4 10.1 L30.2 16.6 M30.8 11.2 L33.4 15.8" stroke="#141010" stroke-width="1.15" stroke-linecap="round" fill="none"/>
      </g>
    </g>
  </svg>`
  const iconUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`
  return L.icon({
    iconUrl,
    iconSize: [50, 50],
    iconAnchor: [25, 46],
    popupAnchor: [0, -44],
    className: 'icc-map-pin icc-map-pin--fez'
  })
}

function markerIconFor(kind: SelectionKind): L.Icon {
  if (kind === 'map' || kind === 'location') {
    return fezMarkerIcon()
  }

  const color = kind === 'hotel' ? '#FFB020' : '#18D3C5'

  const svg = `
  <svg xmlns="http://www.w3.org/2000/svg" width="56" height="56" viewBox="0 0 56 56">
    <defs>
      <radialGradient id="g" cx="30%" cy="18%" r="80%">
        <stop offset="0%" stop-color="#ffffff" stop-opacity="0.9"/>
        <stop offset="35%" stop-color="${color}"/>
        <stop offset="100%" stop-color="#0b1020"/>
      </radialGradient>
      <filter id="s" x="-50%" y="-50%" width="200%" height="200%">
        <feDropShadow dx="0" dy="6" stdDeviation="5" flood-color="#000" flood-opacity="0.35"/>
      </filter>
    </defs>
    <path filter="url(#s)" d="M28 5C20.2 5 14 11.2 14 19c0 14 14 32 14 32s14-18 14-32c0-7.8-6.2-14-14-14z" fill="url(#g)" stroke="rgba(255,255,255,0.7)" stroke-width="2"/>
    <circle cx="28" cy="21" r="7.5" fill="rgba(255,255,255,0.2)"/>
    <circle cx="28" cy="21" r="4.3" fill="rgba(255,255,255,0.65)"/>
  </svg>`

  const iconUrl = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`

  return L.icon({
    iconUrl,
    iconSize: [48, 48],
    iconAnchor: [24, 48],
    popupAnchor: [0, -48],
    className: 'icc-map-pin'
  })
}

function poiCircleStyle(opts: {
  crowdLevel?: 'Low' | 'Medium' | 'High'
  isSelected?: boolean
  isRecommended?: boolean
  isFaded?: boolean
}) {
  const base =
    opts.crowdLevel === 'High'
      ? { stroke: '#7a1c1c', fill: '#d64a3a' }
      : opts.crowdLevel === 'Medium'
        ? { stroke: '#8b6a16', fill: '#e6bf49' }
        : { stroke: '#1d6a42', fill: '#52b87a' }

  if (opts.isSelected) {
    return {
      radius: 11.5,
      color: '#fff5cf',
      weight: 2.8,
      fillColor: base.fill,
      fillOpacity: 1,
      opacity: 1
    } satisfies L.CircleMarkerOptions
  }

  if (opts.isRecommended) {
    return {
      radius: 9.5,
      color: '#f5f0df',
      weight: 2.2,
      fillColor: '#3f89d3',
      fillOpacity: 0.98,
      opacity: 1
    } satisfies L.CircleMarkerOptions
  }

  if (opts.isFaded) {
    return {
      radius: 6.5,
      color: '#9b907f',
      weight: 1,
      fillColor: base.fill,
      fillOpacity: 0.22,
      opacity: 0.3
    } satisfies L.CircleMarkerOptions
  }

  return {
    radius: 6.8,
    color: base.stroke,
    weight: 1.4,
    fillColor: base.fill,
    fillOpacity: 0.9,
    opacity: 0.96
  } satisfies L.CircleMarkerOptions
}

export function createMap(
  container: HTMLElement,
  opts: {
    defaultCenter: LatLng
    onSelect: (selection: MapSelection) => void
  }
): MapController {
  const map = L.map(container, {
    attributionControl: false,
    zoomControl: false,
    scrollWheelZoom: true,
    preferCanvas: true
  })

  const tile = L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution:
      '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
  })

  tile.addTo(map)

  // Keep attribution away from center overlays on mobile.
  L.control.attribution({ position: 'bottomleft' }).addTo(map)

  map.setView(toLeafletLatLng(opts.defaultCenter), 12)

  map.whenReady(() => {
    container.classList.add('map--ready')
  })

  const invalidate = () => {
    map.invalidateSize({ animate: false })
  }
  const ro = new ResizeObserver(() => invalidate())
  ro.observe(container)
  const onOrient = () => window.setTimeout(invalidate, 350)
  window.addEventListener('orientationchange', onOrient)

  // Subtle zoom controls in the top-right.
  L.control
    .zoom({
      position: 'topright'
    })
    .addTo(map)

  let marker: L.Marker | null = null
  const poiLayer = L.layerGroup().addTo(map)
  const recommendationLayer = L.layerGroup().addTo(map)
  let pulseMarker: L.Marker | null = null
  let suppressNextBackgroundClick = false

  const clearPulse = () => {
    if (pulseMarker) {
      map.removeLayer(pulseMarker)
      pulseMarker = null
    }
  }

  const setMarkerInternal = (selection: MapSelection, options?: { flyTo?: boolean }) => {
    const icon = markerIconFor(selection.kind)
    clearPulse()

    if (!marker) {
      marker = L.marker(toLeafletLatLng(selection.latlng), { icon, riseOnHover: true }).addTo(map)
    } else {
      marker.setIcon(icon)
      marker.setLatLng(toLeafletLatLng(selection.latlng))
    }

    if (selection.kind === 'location') {
      const pulseIcon = L.divIcon({
        className: 'icc-pulse-wrap',
        html: '<div class="icc-pulse-ring" aria-hidden="true"></div><div class="icc-pulse-ring icc-pulse-ring--delay" aria-hidden="true"></div>',
        iconSize: [140, 140],
        iconAnchor: [70, 70]
      })
      pulseMarker = L.marker(toLeafletLatLng(selection.latlng), {
        icon: pulseIcon,
        interactive: false,
        keyboard: false,
        zIndexOffset: -200
      }).addTo(map)
    }

    const popup = `<div class="icc-map-popup">${selection.label}</div>`

    marker.bindPopup(popup, { closeButton: false })
    marker.openPopup()

    if (options?.flyTo) {
      let targetCenter = toLeafletLatLng(selection.latlng)
      if (selection.kind === 'poi') {
        const targetZoom = 14
        const offsetPx = Math.max(72, Math.min(180, Math.round(container.clientWidth * 0.18)))
        const projected = map.project(L.latLng(selection.latlng.lat, selection.latlng.lng), targetZoom)
        targetCenter = map.unproject(projected.add([offsetPx, 0]), targetZoom)
      }

      map.flyTo(targetCenter, 14, {
        duration: 1.12,
        easeLinearity: 0.28
      })
    }
  }

  map.on('click', (e: L.LeafletMouseEvent) => {
    if (suppressNextBackgroundClick) {
      suppressNextBackgroundClick = false
      return
    }
    const selection: MapSelection = {
      latlng: { lat: e.latlng.lat, lng: e.latlng.lng },
      label: 'Map background',
      kind: 'map'
    }
    opts.onSelect(selection)
  })

  return {
    setMarker: (selection, options) => setMarkerInternal(selection, options),
    clearSelection: () => {
      clearPulse()
      if (marker) {
        map.removeLayer(marker)
        marker = null
      }
    },
    setPoiMarkers: (pois, selectedPoiId, recommendationLines, onSelectPoi) => {
      poiLayer.clearLayers()
      recommendationLayer.clearLayers()

      const selectedPoi = selectedPoiId ? pois.find((poi) => poi.id === selectedPoiId) : null

      if (selectedPoi) {
        for (const rec of recommendationLines) {
          const line = L.polyline(
            [
              [selectedPoi.lat, selectedPoi.lng],
              [rec.lat, rec.lng]
            ],
            {
              color: '#3f89d3',
              weight: 2.4,
              opacity: 0.72,
              dashArray: '7 6',
              lineCap: 'round'
            }
          )
          recommendationLayer.addLayer(line)
        }
      }

      for (const poi of pois) {
        const circle = L.circleMarker(
          [poi.lat, poi.lng],
          poiCircleStyle({
            crowdLevel: poi.crowdLevel,
            isSelected: poi.isSelected,
            isRecommended: poi.isRecommended,
            isFaded: poi.isFaded
          })
        ).addTo(poiLayer)
        const popup = `
          <div style="font-weight:700; letter-spacing:-0.2px">${poi.name}</div>
          <div style="font-size:12px; opacity:0.78; margin-top:2px">${poi.category}${poi.crowdLevel ? ` · ${poi.crowdLevel}` : ''}</div>
        `
        circle.bindPopup(popup, { closeButton: false })
        circle.on('mouseover', () => circle.openPopup())
        circle.on('mouseout', () => circle.closePopup())
        circle.on('click', (e) => {
          suppressNextBackgroundClick = true
          L.DomEvent.stopPropagation(e)
          onSelectPoi(poi.id)
        })
      }
    },
    getCenter: () => {
      const c = map.getCenter()
      return { lat: c.lat, lng: c.lng }
    },
    relayout: () => invalidate(),
    destroy: () => {
      window.removeEventListener('orientationchange', onOrient)
      ro.disconnect()
      map.remove()
    }
  }
}
