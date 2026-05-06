export type LatLng = { lat: number; lng: number }

export type SelectionKind = 'hotel' | 'location' | 'poi' | 'map'

export type MapSelection = {
  latlng: LatLng
  label: string
  kind: SelectionKind
}

