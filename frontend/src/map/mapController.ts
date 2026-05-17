import * as L from 'leaflet'
import type { LatLng, MapSelection, SelectionKind } from '../domain/types'

export type MapController = {
  setMarker: (selection: MapSelection, options?: { flyTo?: boolean }) => void
  setPoiMarkers: (
    pois: Array<{ id: string; name: string; category: string; lat: number; lng: number }>,
    onSelectPoi: (poiId: string) => void
  ) => void
  getCenter: () => LatLng
  destroy: () => void
}

function toLeafletLatLng(p: LatLng): L.LatLngExpression {
  return [p.lat, p.lng]
}

function markerIconFor(kind: SelectionKind): L.Icon {
  const color =
    kind === 'hotel'
      ? '#FFB020'
      : kind === 'poi'
        ? '#18D3C5'
        : kind === 'location'
          ? '#7C3AED'
          : '#FF6A90'

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
    iconSize: [44, 44],
    iconAnchor: [22, 44],
    popupAnchor: [0, -44]
  })
}

function poiCircleStyle() {
  return {
    radius: 7.5,
    color: 'rgba(255, 226, 190, 0.96)',
    weight: 1.5,
    fillColor: '#d96c5f',
    fillOpacity: 0.9
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

  const setMarkerInternal = (selection: MapSelection, options?: { flyTo?: boolean }) => {
    const icon = markerIconFor(selection.kind)

    if (!marker) {
      marker = L.marker(toLeafletLatLng(selection.latlng), { icon }).addTo(map)
    } else {
      marker.setIcon(icon)
      marker.setLatLng(toLeafletLatLng(selection.latlng))
    }

    const popup = `<div style="font-weight:700; letter-spacing:-0.2px">${selection.label}</div>`

    marker.bindPopup(popup, { closeButton: false })
    marker.openPopup()

    if (options?.flyTo) {
      map.flyTo(toLeafletLatLng(selection.latlng), 13, {
        duration: 0.8
      })
    }
  }

  map.on('click', (e: L.LeafletMouseEvent) => {
    const selection: MapSelection = {
      latlng: { lat: e.latlng.lat, lng: e.latlng.lng },
      label: 'Pinned location',
      kind: 'map'
    }
    setMarkerInternal(selection)
    opts.onSelect(selection)
  })

  return {
    setMarker: (selection, options) => setMarkerInternal(selection, options),
    setPoiMarkers: (pois, onSelectPoi) => {
      poiLayer.clearLayers()

      for (const poi of pois) {
        const circle = L.circleMarker([poi.lat, poi.lng], poiCircleStyle()).addTo(poiLayer)
        const popup = `
          <div style="font-weight:700; letter-spacing:-0.2px">${poi.name}</div>
          <div style="font-size:12px; opacity:0.78; margin-top:2px">${poi.category}</div>
        `
        circle.bindPopup(popup, { closeButton: false })
        circle.on('mouseover', () => circle.openPopup())
        circle.on('mouseout', () => circle.closePopup())
        circle.on('click', (e) => {
          L.DomEvent.stopPropagation(e)
          onSelectPoi(poi.id)
        })
      }
    },
    getCenter: () => {
      const c = map.getCenter()
      return { lat: c.lat, lng: c.lng }
    },
    destroy: () => {
      window.removeEventListener('orientationchange', onOrient)
      ro.disconnect()
      map.remove()
    }
  }
}
