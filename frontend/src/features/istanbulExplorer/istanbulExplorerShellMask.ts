/**
 * Inset rounded plate for the route map backdrop (SVG user units).
 * Horizontal placement matches the widened explorer viewBox (`-70 0 240 …`); the plate
 * spans to the right edge of that viewBox so it sits closer to the trip column.
 * Height is derived at runtime from the route canvas aspect so `meet` scaling
 * does not leave vertical letterboxing above/below the plate.
 */
export const ISTANBUL_ROUTE_BACKDROP_RECT = {
  x: -66,
  y: 3,
  /** Nearly full viewBox width (`-70`…`170`); pulls the frosted plate toward the trip column. */
  width: 236,
  height: 94,
  rx: 6,
  ry: 6
} as const

export type RoutePlateRect = {
  readonly x: number
  readonly y: number
  readonly width: number
  readonly height: number
  readonly rx: number
  readonly ry: number
}

const PLATE_INSET_Y = 3

/** Same horizontal inset as {@link ISTANBUL_ROUTE_BACKDROP_RECT}; height fills viewBox minus vertical inset. */
export function routePlateRectForViewBoxHeight(viewBoxHeight: number): RoutePlateRect {
  const h = Math.max(40, viewBoxHeight - PLATE_INSET_Y * 2)
  return { ...ISTANBUL_ROUTE_BACKDROP_RECT, height: h }
}

/** Map `thread` percentages (0–100) onto the frosted route plate in SVG user space. */
export function mapThreadToRoutePlate(
  thread: readonly [number, number],
  rect: Pick<RoutePlateRect, 'x' | 'y' | 'width' | 'height'> = ISTANBUL_ROUTE_BACKDROP_RECT
): [number, number] {
  const { x, y, width, height } = rect
  return [x + (thread[0] / 100) * width, y + (thread[1] / 100) * height]
}
