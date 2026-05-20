import type { ExplorerPOI } from './types'

export function haversineKm(a: { lat: number; lng: number }, b: { lat: number; lng: number }): number {
  const R = 6371
  const dLat = ((b.lat - a.lat) * Math.PI) / 180
  const dLng = ((b.lng - a.lng) * Math.PI) / 180
  const lat1 = (a.lat * Math.PI) / 180
  const lat2 = (b.lat * Math.PI) / 180
  const x =
    Math.sin(dLat / 2) ** 2 + Math.sin(dLng / 2) ** 2 * Math.cos(lat1) * Math.cos(lat2)
  const c = 2 * Math.atan2(Math.sqrt(x), Math.sqrt(1 - x))
  return R * c
}

/** Smooth quadratic segments between points in SVG user space (route plate coords). */
export function buildCurvedRoutePath(points: [number, number][], bendFactor = 0.38): string {
  if (points.length === 0) return ''
  if (points.length === 1) {
    const [x, y] = points[0]
    return `M ${x} ${y}`
  }
  const [x0, y0] = points[0]
  let d = `M ${x0} ${y0}`
  for (let i = 1; i < points.length; i++) {
    const [x1, y1] = points[i - 1]
    const [x2, y2] = points[i]
    const mx = (x1 + x2) / 2
    const my = (y1 + y2) / 2
    const dx = x2 - x1
    const dy = y2 - y1
    const len = Math.hypot(dx, dy) || 1
    const nx = (-dy / len) * bendFactor * 22
    const ny = (dx / len) * bendFactor * 22
    const cx = mx + nx
    const cy = my + ny
    d += ` Q ${cx} ${cy} ${x2} ${y2}`
  }
  return d
}

export function walkingMinutes(km: number, kmh = 4.6): number {
  return Math.max(3, Math.round((km / kmh) * 60))
}

export function walkFromPrevious(ordered: ExplorerPOI[], index: number): number {
  if (index <= 0) return 0
  return walkingMinutes(haversineKm(ordered[index - 1], ordered[index]))
}

export function applyCrowdSorting(places: ExplorerPOI[], avoidCrowds: boolean): ExplorerPOI[] {
  const copy = [...places]
  if (avoidCrowds) {
    return copy.sort((a, b) => a.crowdScore - b.crowdScore)
  }
  return copy.sort((a, b) => (b.routeWeight ?? 0) - (a.routeWeight ?? 0))
}
