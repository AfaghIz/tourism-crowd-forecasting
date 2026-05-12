import type { LatLng } from '../domain/types'

export type MapsTravelMode = 'driving' | 'walking' | 'transit' | 'bicycling'

/** Factory so callers can supply live GPS / map selection without circular imports. */
export function createDirectionsOpener(
  getOrigin: () => LatLng | null,
  onFreshGps?: (ll: LatLng) => void,
  options?: { travelMode?: MapsTravelMode }
) {
  const travelMode = options?.travelMode ?? 'walking'

  return function openGoogleMapsDirectionsFromUser(destLat: number, destLng: number): void {
    const dest = `${destLat},${destLng}`
    const openWithOrigin = (origin: LatLng) => {
      const u = new URL('https://www.google.com/maps/dir/')
      u.searchParams.set('api', '1')
      u.searchParams.set('origin', `${origin.lat},${origin.lng}`)
      u.searchParams.set('destination', dest)
      u.searchParams.set('travelmode', travelMode)
      window.open(u.toString(), '_blank', 'noopener,noreferrer')
    }
    const openDestinationOnly = () => {
      window.open(
        `https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent(dest)}&travelmode=${encodeURIComponent(travelMode)}`,
        '_blank',
        'noopener,noreferrer'
      )
    }

    const origin = getOrigin()
    if (origin) {
      openWithOrigin(origin)
      return
    }
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          const ll: LatLng = { lat: pos.coords.latitude, lng: pos.coords.longitude }
          onFreshGps?.(ll)
          openWithOrigin(ll)
        },
        () => openDestinationOnly(),
        { enableHighAccuracy: false, timeout: 7000, maximumAge: 120000 }
      )
    } else {
      openDestinationOnly()
    }
  }
}
