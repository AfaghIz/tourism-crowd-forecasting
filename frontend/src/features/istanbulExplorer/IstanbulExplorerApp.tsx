import { useCallback, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { useExplorerStore } from './store'
import { EXPLORER_POIS, SIDEBAR_ROUTES } from './data'
import { buildCurvedRoutePath, orderByRouteMode, walkFromPrevious } from './geometry'
import type { ExplorerPOI, ExplorerTag, RouteMode, ThemeMode } from './types'
import {
  mapThreadToRoutePlate,
  routePlateRectForViewBoxHeight
} from './istanbulExplorerShellMask'
import iconBlueMosque from '../../ui/blue mosque png.webp'
import iconDolmabahce from '../../ui/dolmabache png.png'
import iconBosphorusBridge from '../../ui/istanbul bridge.avif'
import iconGalataTower from '../../ui/galata tower ong.jpg'
import iconGrandBazaar from '../../ui/grand bazar png.webp'
import iconHagiaSophia from '../../ui/hagia sofia mosque png.jpg'
import iconMaidenTower from '../../ui/maiden tower png.png'
import iconSpiceBazaar from '../../ui/spice bazaar png.webp'
import iconTaksim from '../../ui/taksim png.png'
import iconTopkapi from '../../ui/topkapi palace png.jpg'

const TAGS: { id: ExplorerTag; label: string }[] = [
  { id: 'historical', label: 'Historical' },
  { id: 'food', label: 'Food' },
  { id: 'shopping', label: 'Shopping' },
  { id: 'nature', label: 'Nature' },
  { id: 'nightlife', label: 'Nightlife' },
  { id: 'family', label: 'Family' },
  { id: 'rain', label: 'Rain-friendly' }
]

const MODES: { id: RouteMode; label: string }[] = [
  { id: 'avoid-crowds', label: 'Avoid crowds' },
  { id: 'scenic', label: 'Most scenic' },
  { id: 'fastest', label: 'Fastest' },
  { id: 'budget', label: 'Budget' }
]

/** Curated images in `src/ui` — keyed by POI id (`premiumHelpers` / explorer data). */
const POI_ICON_SRC: Partial<Record<string, string>> = {
  hagia: iconHagiaSophia,
  blue: iconBlueMosque,
  topkapi: iconTopkapi,
  bazaar: iconGrandBazaar,
  galata: iconGalataTower,
  dolma: iconDolmabahce,
  bridge: iconBosphorusBridge,
  spice: iconSpiceBazaar,
  maiden: iconMaidenTower,
  taksim: iconTaksim
}

/** SVG marker colors — aligned with thread stops (same viewBox as path). */
const ACCENT_MARKER: Record<ExplorerPOI['accentKey'], { fill: string; stroke: string }> = {
  blue: { fill: 'rgba(26, 58, 82, 0.92)', stroke: 'rgba(110, 184, 232, 0.95)' },
  sand: { fill: 'rgba(139, 105, 20, 0.9)', stroke: 'rgba(196, 165, 116, 0.98)' },
  olive: { fill: 'rgba(31, 52, 40, 0.92)', stroke: 'rgba(120, 180, 140, 0.95)' },
  sunset: { fill: 'rgba(180, 83, 42, 0.9)', stroke: 'rgba(255, 160, 120, 0.95)' }
}

function useFilteredOrdered() {
  const tagsFilter = useExplorerStore((s) => s.tagsFilter)
  const routeMode = useExplorerStore((s) => s.routeMode)

  return useMemo(() => {
    const filtered =
      tagsFilter.size === 0
        ? EXPLORER_POIS
        : EXPLORER_POIS.filter((p) => p.tags.some((t) => tagsFilter.has(t)))
    const ordered = orderByRouteMode(filtered, routeMode)
    return { filtered, ordered }
  }, [tagsFilter, routeMode])
}

function StopListGlyph({
  id,
  emoji,
  matteFilterId
}: {
  id: string
  emoji: string
  matteFilterId?: string
}) {
  const src = POI_ICON_SRC[id]
  if (src) {
    const matte = matteFilterId ? `url(#${matteFilterId})` : undefined
    return (
      <img
        src={src}
        alt=""
        className="h-7 w-7 shrink-0 object-cover"
        style={{
          filter: matte
            ? `${matte} drop-shadow(0 1px 1px rgba(0,0,0,0.12))`
            : 'drop-shadow(0 1px 1px rgba(0,0,0,0.12))'
        }}
      />
    )
  }
  return (
    <span className="text-base leading-none" aria-hidden>
      {emoji}
    </span>
  )
}

/** Mobile: no landmark map — lightweight “live processing” shell so the band still feels active. */
function MobileRouteActivityShell({
  theme,
  playback
}: {
  theme: ThemeMode
  playback: boolean
}) {
  const night = theme === 'night'
  return (
    <div
      role="status"
      aria-live="polite"
      aria-label="Route overview is summarized on this device; use the list below for stops."
      className={`relative isolate min-h-[min(220px,36vh)] w-full overflow-hidden rounded-2xl border ${
        night
          ? 'border-white/14 bg-[#0e1824]/88'
          : 'border-[#2a241c]/12 bg-gradient-to-br from-[#f6f1e8] via-[#faf6ee] to-[#ebe4d6]'
      }`}
    >
      <div
        aria-hidden
        className={`pointer-events-none absolute inset-0 opacity-90 ${
          night
            ? 'bg-[radial-gradient(ellipse_85%_70%_at_30%_20%,rgba(45,106,143,0.35),transparent),radial-gradient(ellipse_70%_55%_at_78%_72%,rgba(217,119,87,0.22),transparent)]'
            : 'bg-[radial-gradient(ellipse_80%_65%_at_25%_25%,rgba(45,106,143,0.12),transparent),radial-gradient(ellipse_65%_50%_at_82%_68%,rgba(196,165,116,0.2),transparent)]'
        }`}
      />
      <svg
        aria-hidden
        className="pointer-events-none absolute inset-0 h-full w-full"
        viewBox="0 0 320 120"
        preserveAspectRatio="none"
      >
        <motion.path
          d="M 12 78 C 52 22, 108 102, 168 48 S 268 92, 308 36"
          fill="none"
          stroke={night ? 'rgba(120, 190, 210, 0.42)' : 'rgba(45, 106, 143, 0.38)'}
          strokeWidth={2.2}
          strokeLinecap="round"
          strokeDasharray="6 14"
          initial={false}
          animate={
            playback
              ? { strokeDashoffset: [0, -240] }
              : { strokeDashoffset: [0, -80, 0] }
          }
          transition={
            playback
              ? { duration: 10, ease: 'linear', repeat: Infinity }
              : { duration: 5.5, ease: 'easeInOut', repeat: Infinity }
          }
          opacity={night ? 0.55 : 0.5}
        />
      </svg>
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 overflow-hidden opacity-[0.55]"
      >
        <div
          className="ie-mobile-activity__shimmer absolute -left-1/2 top-0 h-full w-[45%] bg-gradient-to-r from-transparent via-white/25 to-transparent"
          style={{ animationDelay: '0.4s' }}
        />
      </div>
      {[
        { l: '14%', t: '42%', d: '0s' },
        { l: '38%', t: '58%', d: '0.35s' },
        { l: '62%', t: '36%', d: '0.7s' },
        { l: '84%', t: '52%', d: '1.05s' }
      ].map((dot) => (
        <span
          key={dot.l}
          aria-hidden
          className={`ie-mobile-activity__dot absolute h-2 w-2 rounded-full ${
            night ? 'bg-cyan-300/70 shadow-[0_0_12px_rgba(34,211,238,0.35)]' : 'bg-[#2d6a8f]/55'
          }`}
          style={{ left: dot.l, top: dot.t, animationDelay: dot.d }}
        />
      ))}
      <div
        className={`pointer-events-none absolute bottom-3 left-4 right-4 flex items-end justify-between gap-3 ${
          night ? 'text-white/55' : 'text-[#3a342c]/65'
        }`}
      >
        <p className="m-0 max-w-[72%] text-[11px] font-medium leading-snug">
          Blending crowd signals for your picks…
        </p>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${
            playback
              ? night
                ? 'bg-emerald-500/25 text-emerald-200/95'
                : 'bg-emerald-600/15 text-emerald-900/90'
              : night
                ? 'bg-white/10 text-white/70'
                : 'bg-black/8 text-[#2a241c]/75'
          }`}
        >
          {playback ? 'Live' : 'Sync'}
        </span>
      </div>
    </div>
  )
}

export function IstanbulExplorerApp({
  openDirections
}: {
  openDirections: (lat: number, lng: number) => void
}) {
  const theme = useExplorerStore((s) => s.theme)
  const tagsFilter = useExplorerStore((s) => s.tagsFilter)
  const playback = useExplorerStore((s) => s.playback)
  const hoveredId = useExplorerStore((s) => s.hoveredId)
  const selectedId = useExplorerStore((s) => s.selectedId)
  const sheetExpanded = useExplorerStore((s) => s.sheetExpanded)
  const filterFabOpen = useExplorerStore((s) => s.filterFabOpen)
  const favorites = useExplorerStore((s) => s.favorites)

  const setHoveredId = useExplorerStore((s) => s.setHoveredId)
  const setSelectedId = useExplorerStore((s) => s.setSelectedId)
  const setSheetExpanded = useExplorerStore((s) => s.setSheetExpanded)
  const toggleTag = useExplorerStore((s) => s.toggleTag)
  const clearTags = useExplorerStore((s) => s.clearTags)
  const toggleFavorite = useExplorerStore((s) => s.toggleFavorite)
  const setFilterFabOpen = useExplorerStore((s) => s.setFilterFabOpen)

  const { ordered } = useFilteredOrdered()

  const shellRef = useRef<HTMLDivElement>(null)
  const mx = useMotionValue(0)
  const my = useMotionValue(0)
  const sx = useSpring(mx, { stiffness: 280, damping: 28 })
  const sy = useSpring(my, { stiffness: 280, damping: 28 })
  const glowBg = useTransform([sx, sy], ([x, y]) => {
    const nx = typeof x === 'number' ? x : 50
    const ny = typeof y === 'number' ? y : 40
    return `radial-gradient(42% 38% at ${nx}% ${ny}%, rgba(255,255,255,0.42), transparent 62%)`
  })

  const onShellMove = useCallback(
    (e: React.PointerEvent) => {
      if (!shellRef.current) return
      const r = shellRef.current.getBoundingClientRect()
      mx.set(((e.clientX - r.left) / r.width) * 100)
      my.set(((e.clientY - r.top) / r.height) * 100)
    },
    [mx, my]
  )

  const [zoom, setZoom] = useState(1)
  const onWheel = useCallback((e: React.WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return
    e.preventDefault()
    setZoom((z) => Math.min(1.55, Math.max(0.85, z - e.deltaY * 0.0015)))
  }, [])

  const routeCanvasRef = useRef<HTMLDivElement>(null)
  const [videoStackHeightPx, setVideoStackHeightPx] = useState<number | null>(null)

  /**
   * Size the route canvas so its bottom lines up with the lower of the search / trip
   * video stacks (not just matching their height — padding above the canvas is included).
   */
  useLayoutEffect(() => {
    const left = document.querySelector<HTMLElement>('.panel--search > .sideVideoStack')
    const trip = document.querySelector<HTMLElement>('.sideVideoStack--trip')
    const mapColumn = document.querySelector<HTMLElement>('.mapColumn')
    if (!left && !trip) return

    const read = () => {
      if (typeof window !== 'undefined' && window.innerWidth < 1024) {
        setVideoStackHeightPx(null)
        return
      }
      const canvas = routeCanvasRef.current
      const leftB = left?.getBoundingClientRect().bottom ?? 0
      const tripB = trip?.getBoundingClientRect().bottom ?? 0
      const targetBottom = Math.max(leftB, tripB)

      if (canvas && targetBottom > 1) {
        const z = Math.max(0.85, Math.min(1.55, zoom))
        const top = canvas.getBoundingClientRect().top
        const h = Math.round((targetBottom - top) / z)
        if (h > 0) setVideoStackHeightPx(Math.max(160, h))
        return
      }

      const hl = left ? Math.round(left.getBoundingClientRect().height) : 0
      const ht = trip ? Math.round(trip.getBoundingClientRect().height) : 0
      const h = Math.max(hl, ht)
      if (h > 0) setVideoStackHeightPx(Math.max(160, h))
    }

    read()
    const ro = new ResizeObserver(read)
    if (left) ro.observe(left)
    if (trip) ro.observe(trip)
    if (mapColumn) ro.observe(mapColumn)
    window.addEventListener('resize', read)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', read)
    }
  }, [zoom])

  /** Match SVG viewBox aspect to the route canvas so `meet` does not letterbox the frosted plate vertically. */
  const [routeViewBoxH, setRouteViewBoxH] = useState(100)
  useLayoutEffect(() => {
    const el = routeCanvasRef.current
    if (!el) return
    const read = () => {
      if (typeof window !== 'undefined' && window.innerWidth < 1024) return
      const w = el.clientWidth
      const h = el.clientHeight
      if (w < 8 || h < 8) return
      setRouteViewBoxH(Math.max(100, (h / w) * 240))
    }
    read()
    const ro = new ResizeObserver(read)
    ro.observe(el)
    window.addEventListener('resize', read)
    return () => {
      ro.disconnect()
      window.removeEventListener('resize', read)
    }
  }, [videoStackHeightPx, zoom])

  const routePlateRect = useMemo(
    () => routePlateRectForViewBoxHeight(routeViewBoxH),
    [routeViewBoxH]
  )

  const points = useMemo(
    () =>
      ordered.map((p) => mapThreadToRoutePlate(p.thread as [number, number], routePlateRect)),
    [ordered, routePlateRect]
  )
  const pathD = useMemo(() => buildCurvedRoutePath(points, 0.42), [points])

  const hourTint =
    typeof window !== 'undefined'
      ? new Date().getHours()
      : 12
  const dusk = hourTint >= 18 || hourTint < 6

  const incidentOpacity = useCallback(
    (edgeFrom: number, edgeTo: number) => {
      if (!hoveredId) return 0.35
      const a = ordered[edgeFrom]?.id
      const b = ordered[edgeTo]?.id
      if (a === hoveredId || b === hoveredId) return 1
      return 0.12
    },
    [hoveredId, ordered]
  )

  const selected = ordered.find((p) => p.id === selectedId) ?? null
  const selIndex = selected ? ordered.indexOf(selected) : -1

  /** Unique SVG defs ids (avoid clashes if multiple roots ever mount). */
  const svgUid = useId().replace(/:/g, '')
  const gradId = `ieRouteGrad-${svgUid}`
  const glowId = `ieGlow-${svgUid}`
  /** Knocks out baked-in white / light-gray (e.g. fake “transparency” checker) so only darker landmark pixels stay. */
  const matteId = `ieMatteLight-${svgUid}`
  const routeStroke = `url(#${gradId})`

  const regionShellFilter =
    theme === 'night'
      ? 'drop-shadow(0 0 0.75px rgba(255,255,255,0.14)) drop-shadow(0 22px 56px rgba(0,0,0,0.55))'
      : 'drop-shadow(0 0 0.5px rgba(42,36,28,0.18)) drop-shadow(0 16px 44px rgba(42,36,28,0.18))'

  return (
    <div className="relative isolate">
      <div className="transition-[filter] duration-500" style={{ filter: regionShellFilter }}>
      <div
        data-explorer-theme={theme}
        className={`ie-root group relative isolate overflow-hidden transition-[background-color] duration-500 ${
          theme === 'night'
            ? 'bg-gradient-to-br from-[#0c1520] via-[#121c28] to-[#0a1018]'
            : 'bg-transparent'
        }`}
      >
      {/* Cursor-follow ambient light (night only — day stays clear behind the map) */}
      {theme === 'night' && (
        <motion.div
          aria-hidden
          className="pointer-events-none absolute inset-0 z-0 opacity-[0.22]"
          style={{ backgroundImage: glowBg }}
        />
      )}
      <div
        ref={shellRef}
        onPointerMove={onShellMove}
        className="relative z-[1] flex flex-col gap-3 px-0 pt-0 pb-2 sm:gap-4 sm:pb-3 lg:pb-0"
      >
        <div className="min-w-0">
        {/* Desktop: full landmark route map; mobile: activity shell only (no pins / map). */}
        <div className="relative w-full min-h-0 max-w-full overflow-hidden py-1 pr-0 sm:pr-0.5">
          <div className="lg:hidden">
            <MobileRouteActivityShell theme={theme} playback={playback} />
          </div>
          <div
            ref={routeCanvasRef}
            onWheel={onWheel}
            className="relative isolate hidden min-h-0 w-full max-w-full origin-center overflow-hidden transition-transform duration-300 ease-out lg:block"
            style={{
              transform: `scale(${zoom})`,
              ...(videoStackHeightPx
                ? { height: videoStackHeightPx, maxHeight: videoStackHeightPx }
                : { minHeight: 'min(420px, 50vh)' })
            }}
          >
            <svg
              viewBox={`-70 0 240 ${routeViewBoxH}`}
              className="absolute inset-0 block h-full w-full overflow-visible"
              preserveAspectRatio="xMidYMid meet"
              role="img"
              aria-label="Istanbul landmark route map"
            >
              <defs>
                <linearGradient id={gradId} x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#2d6a8f" />
                  <stop offset="45%" stopColor="#c4a574" />
                  <stop offset="100%" stopColor="#d97757" />
                </linearGradient>
                <filter id={glowId} x="-40%" y="-40%" width="180%" height="180%">
                  <feGaussianBlur stdDeviation="1.2" result="b" />
                  <feMerge>
                    <feMergeNode in="b" />
                    <feMergeNode in="SourceGraphic" />
                  </feMerge>
                </filter>
                <filter
                  id={matteId}
                  colorInterpolationFilters="sRGB"
                  filterUnits="objectBoundingBox"
                  x="0"
                  y="0"
                  width="1"
                  height="1"
                >
                  <feColorMatrix
                    in="SourceGraphic"
                    type="matrix"
                    values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  -1 -1 -1 0 2.28"
                  />
                </filter>
              </defs>

              <rect
                {...routePlateRect}
                fill={theme === 'night' ? 'rgba(255,255,255,0.085)' : 'rgba(255,252,247,0.55)'}
                stroke={theme === 'night' ? 'rgba(255,255,255,0.22)' : 'rgba(42,36,28,0.14)'}
                strokeWidth={0.55}
                strokeLinejoin="round"
                pointerEvents="none"
              />

              {/* Segment highlights — paint underneath markers */}
              {ordered.slice(0, -1).map((_, i) => {
                const segPts = [
                  mapThreadToRoutePlate(ordered[i].thread as [number, number], routePlateRect),
                  mapThreadToRoutePlate(ordered[i + 1].thread as [number, number], routePlateRect)
                ] as [number, number][]
                const sd = buildCurvedRoutePath(segPts, 0.42)
                const lo = incidentOpacity(i, i + 1)
                return (
                  <path
                    key={`seg-${ordered[i].id}-${ordered[i + 1].id}`}
                    d={sd}
                    fill="none"
                    stroke={routeStroke}
                    strokeWidth={1.4}
                    opacity={lo}
                    strokeLinecap="round"
                    pointerEvents="none"
                  />
                )
              })}

              <path
                d={pathD}
                fill="none"
                stroke={routeStroke}
                strokeWidth={2.6}
                strokeLinecap="round"
                strokeLinejoin="round"
                opacity={0.55}
                filter={`url(#${glowId})`}
                pointerEvents="none"
              />

              <motion.path
                d={pathD}
                fill="none"
                stroke={
                  theme === 'night' ? 'rgba(255,255,255,0.38)' : 'rgba(42, 36, 28, 0.32)'
                }
                strokeWidth={1.1}
                strokeLinecap="round"
                strokeDasharray="5 14"
                pointerEvents="none"
                animate={
                  playback
                    ? { strokeDashoffset: [0, -380] }
                    : { strokeDashoffset: 0 }
                }
                transition={
                  playback
                    ? { duration: 14, ease: 'linear', repeat: Infinity }
                    : { duration: 0.4 }
                }
              />

              {/* Stops share the path viewBox so icons sit on the thread */}
              {ordered.map((p) => {
                const pop = p.popularity / 100
                /** Slightly larger than before so landmark photos stay readable on tall route plates. */
                const baseR = (3.15 + pop * 2.45) * 1.18
                /** Bounding square for PNG markers — `meet` keeps transparent silhouette, no circular mask. */
                const imgBox = baseR * 3.55
                const active = hoveredId === p.id || selectedId === p.id
                const fav = favorites.has(p.id)
                const am = ACCENT_MARKER[p.accentKey]
                const iconSrc = POI_ICON_SRC[p.id]
                const label = `${p.name}. Crowd ${p.crowdScore} of 100. Open walking directions in Google Maps.`
                const favX = iconSrc ? imgBox * 0.38 : baseR * 0.75
                const favY = iconSrc ? -imgBox * 0.38 : -baseR * 0.75
                const [sx, sy] = mapThreadToRoutePlate(p.thread as [number, number], routePlateRect)
                return (
                  <g key={p.id} transform={`translate(${sx}, ${sy})`}>
                    <motion.g
                      style={{ cursor: 'pointer', transformOrigin: '0px 0px', outline: 'none' }}
                      whileHover={{ scale: 1.06 }}
                      whileTap={{ scale: 0.96 }}
                      onMouseDown={(e) => {
                        // Pointer focus on SVG <g> draws a heavy default outline; keep Tab focus for keyboard.
                        e.preventDefault()
                      }}
                      onMouseEnter={() => setHoveredId(p.id)}
                      onMouseLeave={() => setHoveredId(null)}
                      onClick={(e) => {
                        e.preventDefault()
                        e.stopPropagation()
                        openDirections(p.lat, p.lng)
                      }}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          openDirections(p.lat, p.lng)
                        }
                      }}
                      aria-label={label}
                    >
                      <title>{label}</title>
                      {iconSrc ? (
                        <>
                          <image
                            href={iconSrc}
                            x={-imgBox / 2}
                            y={-imgBox / 2}
                            width={imgBox}
                            height={imgBox}
                            preserveAspectRatio="xMidYMid slice"
                            opacity={active ? 1 : theme === 'night' ? 0.95 : 0.98}
                            style={{
                              pointerEvents: 'none',
                              filter: `url(#${matteId}) ${
                                theme === 'night'
                                  ? 'drop-shadow(0 1px 2px rgba(0,0,0,0.4))'
                                  : 'drop-shadow(0 1px 1px rgba(42,36,28,0.12))'
                              }`
                            }}
                          />
                          <rect
                            x={-imgBox / 2}
                            y={-imgBox / 2}
                            width={imgBox}
                            height={imgBox}
                            fill="transparent"
                            stroke="none"
                            pointerEvents="all"
                          />
                        </>
                      ) : (
                        <>
                          <circle
                            r={baseR}
                            fill={am.fill}
                            stroke={
                              active
                                ? am.stroke
                                : theme === 'night'
                                  ? 'rgba(255,255,255,0.35)'
                                  : 'rgba(42, 36, 28, 0.28)'
                            }
                            strokeWidth={active ? 0.55 : 0.32}
                            opacity={theme === 'night' ? 0.98 : 1}
                          />
                          <text
                            textAnchor="middle"
                            dominantBaseline="central"
                            fontSize={baseR * 1.05}
                            fill={theme === 'night' ? '#f8fafc' : '#1c1814'}
                            style={{ pointerEvents: 'none', userSelect: 'none' }}
                          >
                            {p.icon}
                          </text>
                        </>
                      )}
                      {fav && (
                        <text
                          x={favX}
                          y={favY}
                          textAnchor="middle"
                          dominantBaseline="central"
                          fontSize={2.45}
                          fill="#fda4af"
                          style={{ pointerEvents: 'none', userSelect: 'none' }}
                        >
                          ♥
                        </text>
                      )}
                    </motion.g>
                  </g>
                )
              })}
            </svg>

            {playback && (
              <div className="pointer-events-none absolute right-2 top-2 z-[50] sm:right-2.5 sm:top-2.5">
                <span className="rounded-full border border-emerald-400/35 bg-emerald-500/80 px-2 py-0.5 text-[10px] font-medium text-white shadow-sm">
                  Playback
                </span>
              </div>
            )}
          </div>

          <aside
            aria-label="Tap any pin for directions to Istanbul’s top spots"
            className="pointer-events-none absolute right-0 top-1/2 z-[50] hidden -translate-y-1/2 translate-x-1.5 flex-col items-center justify-center sm:translate-x-2.5 lg:flex"
          >
            <p
              className={`m-0 flex max-h-full min-h-0 items-center justify-center overflow-hidden text-center text-[9px] font-bold leading-[1.2] tracking-wide sm:text-[10.5px] md:text-[11px] ${
                theme === 'night'
                  ? 'text-white [text-shadow:0_1px_3px_rgba(0,0,0,0.92),0_0_14px_rgba(0,0,0,0.5)]'
                  : 'text-[#1a1612] [text-shadow:0_0_2px_rgba(255,255,255,0.95),0_1px_3px_rgba(0,0,0,0.45)]'
              }`}
              style={{
                writingMode: 'vertical-lr',
                textOrientation: 'upright',
                WebkitTextOrientation: 'upright'
              }}
            >
              Tap for directions
            </p>
          </aside>
        </div>
        </div>
      </div>
      </div>
      </div>

      {/* Mobile sheet */}
      <MobileInsightRail
        dusk={dusk}
        sheetExpanded={sheetExpanded}
        setSheetExpanded={setSheetExpanded}
        ordered={ordered}
        selectedId={selectedId}
        setSelectedId={setSelectedId}
        matteFilterId={matteId}
      />

      {/* Filters floating */}
      <AnimatePresence>
        {filterFabOpen && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 12 }}
            className="fixed bottom-24 right-5 z-[40] w-[min(92vw,380px)] rounded-3xl border border-white/15 bg-[#0c1520]/92 p-4 shadow-2xl backdrop-blur-2xl lg:hidden"
          >
            <div className="mb-3 flex items-center justify-between">
              <span className="text-[12px] font-semibold text-white">Experience filters</span>
              <button type="button" className="text-[11px] text-white/55" onClick={() => clearTags()}>
                Clear
              </button>
            </div>
            <div className="flex flex-wrap gap-2">
              {TAGS.map((t) => {
                const on = tagsFilter.has(t.id)
                return (
                  <button
                    key={t.id}
                    type="button"
                    onClick={() => toggleTag(t.id)}
                    className={`rounded-full px-3 py-1.5 text-[12px] font-medium ${
                      on ? 'bg-white text-[#0c1520]' : 'bg-white/10 text-white/85'
                    }`}
                  >
                    {t.label}
                  </button>
                )
              })}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <button
        type="button"
        onClick={() => setFilterFabOpen(!filterFabOpen)}
        className="fixed bottom-6 right-5 z-[38] flex h-14 w-14 items-center justify-center rounded-full bg-gradient-to-br from-[#2d6a8f] to-[#d97757] text-xl text-white shadow-xl shadow-black/45 lg:hidden"
        aria-label="Filters"
      >
        ◎
      </button>

      {/* Detail panel */}
      <AnimatePresence>
        {selected && (
          <DetailSheet
            poi={selected}
            index={selIndex}
            ordered={ordered}
            openDirections={openDirections}
            onClose={() => {
              setSelectedId(null)
              setSheetExpanded(false)
            }}
            onFavorite={() => toggleFavorite(selected.id)}
            favorite={favorites.has(selected.id)}
          />
        )}
      </AnimatePresence>
    </div>
  )
}

function MobileInsightRail({
  dusk,
  sheetExpanded,
  setSheetExpanded,
  ordered,
  selectedId,
  setSelectedId,
  matteFilterId
}: {
  dusk: boolean
  sheetExpanded: boolean
  setSheetExpanded: (v: boolean) => void
  ordered: ExplorerPOI[]
  selectedId: string | null
  setSelectedId: (id: string | null) => void
  matteFilterId: string
}) {
  const routeMode = useExplorerStore((s) => s.routeMode)
  const setRouteMode = useExplorerStore((s) => s.setRouteMode)
  const playback = useExplorerStore((s) => s.playback)
  const togglePlayback = useExplorerStore((s) => s.togglePlayback)

  return (
    <motion.div
      drag="y"
      dragConstraints={{ top: 0, bottom: 120 }}
      className={`fixed inset-x-0 bottom-0 z-[30] rounded-t-[26px] border border-white/12 lg:hidden ${
        dusk ? 'bg-[#0b1420]/96' : 'bg-[#faf6ee]/96'
      } backdrop-blur-2xl`}
      style={{ maxHeight: sheetExpanded ? '72vh' : '140px' }}
    >
      <button
        type="button"
        className="mx-auto mt-2 h-1.5 w-14 rounded-full bg-white/25"
        onClick={() => setSheetExpanded(!sheetExpanded)}
        aria-label="Expand insights"
      />
      <div className="max-h-[68vh] overflow-y-auto px-4 pb-6 pt-3">
        <div className="mb-3 flex gap-2 overflow-x-auto pb-1">
          {MODES.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => setRouteMode(m.id)}
              className={`flex-shrink-0 rounded-full px-3 py-1.5 text-[12px] font-semibold ${
                routeMode === m.id
                  ? 'bg-[#1e3a52] text-white'
                  : 'bg-black/10 text-[#2a241c]/85'
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        <button
          type="button"
          onClick={togglePlayback}
          className={`mb-4 w-full rounded-2xl border px-4 py-3 text-left text-[13px] font-medium ${
            playback ? 'border-emerald-400/40 bg-emerald-500/12 text-emerald-900' : 'border-black/10 bg-white/60'
          }`}
        >
          <span className="block text-[10px] uppercase tracking-wider opacity-60">Route playback</span>
          {playback ? 'Animating river-like motion along paths' : 'Tap to animate flowing routes'}
        </button>
        {sheetExpanded && (
          <div className="space-y-4">
            <div>
              <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#b08a55]">
                Stops · details
              </p>
              <ul className="mt-2 max-h-[min(32vh,220px)] space-y-1 overflow-y-auto">
                {ordered.map((p) => (
                  <li key={p.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedId(p.id)}
                      className={`flex w-full items-center gap-2 rounded-xl px-2 py-2 text-left text-[13px] ${
                        selectedId === p.id ? 'bg-black/10' : 'hover:bg-black/5'
                      }`}
                    >
                      <StopListGlyph id={p.id} emoji={p.icon} matteFilterId={matteFilterId} />
                      <span className="truncate font-medium text-[#2a241c]">{p.name}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            {SIDEBAR_ROUTES.map((block) => (
              <div key={block.title}>
                <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-[#b08a55]">
                  {block.title}
                </p>
                <ul className="mt-2 space-y-1.5 text-[13px] leading-snug text-[#3a342c]">
                  {block.items.map((it) => (
                    <li key={it}>• {it}</li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  )
}

function DetailSheet({
  poi,
  index,
  ordered,
  openDirections,
  onClose,
  onFavorite,
  favorite
}: {
  poi: ExplorerPOI
  index: number
  ordered: ExplorerPOI[]
  openDirections: (lat: number, lng: number) => void
  onClose: () => void
  onFavorite: () => void
  favorite: boolean
}) {
  const walk = walkFromPrevious(ordered, index)
  const crowdLabel =
    poi.crowdScore >= 75 ? 'Busy' : poi.crowdScore >= 50 ? 'Moderate' : 'Comfortable'

  const share = () => {
    const url = new URL(window.location.href)
    url.hash = `explorer=${encodeURIComponent(poi.id)}`
    void navigator.clipboard.writeText(url.toString()).catch(() => {})
  }

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
        className="fixed inset-0 z-[50] max-[768px]:z-[1200] flex items-end justify-center bg-black/45 p-4 sm:items-center"
      onClick={onClose}
    >
      <motion.div
        initial={{ y: 40, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        exit={{ y: 30, opacity: 0 }}
        transition={{ type: 'spring', stiffness: 320, damping: 32 }}
        onClick={(e) => e.stopPropagation()}
        className="w-full max-w-md overflow-hidden rounded-3xl border border-white/15 bg-gradient-to-br from-[#121c28]/98 to-[#0a1018]/98 p-6 text-white shadow-2xl backdrop-blur-2xl"
      >
        <div className="flex items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.2em] text-[#c4a574]">
              Stop {index + 1} · {crowdLabel} crowds
            </p>
            <h4 className="mt-1 text-2xl font-semibold tracking-tight">{poi.name}</h4>
            <p className="mt-1 text-[13px] text-white/65">{poi.subtitle}</p>
          </div>
          <button
            type="button"
            onClick={onFavorite}
            className={`rounded-full px-3 py-1.5 text-[12px] font-semibold ${
              favorite ? 'bg-rose-500 text-white' : 'bg-white/10 text-white/85'
            }`}
          >
            {favorite ? 'Saved' : 'Save'}
          </button>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 text-[13px]">
          <div className="rounded-2xl bg-white/8 p-3">
            <p className="text-[10px] uppercase tracking-wider text-white/45">Crowd score</p>
            <p className="mt-1 text-lg font-semibold">{poi.crowdScore}</p>
            <p className="text-[11px] text-white/55">Simulated blend · refreshes with picks</p>
          </div>
          <div className="rounded-2xl bg-white/8 p-3">
            <p className="text-[10px] uppercase tracking-wider text-white/45">Weather fit</p>
            <p className="mt-1 capitalize">{poi.weatherFit.replaceAll('-', ' ')}</p>
            <p className="text-[11px] text-white/55">{poi.microWeather}</p>
          </div>
          <div className="rounded-2xl bg-white/8 p-3">
            <p className="text-[10px] uppercase tracking-wider text-white/45">Best window</p>
            <p className="mt-1 leading-snug">{poi.bestWindow}</p>
          </div>
          <div className="rounded-2xl bg-white/8 p-3">
            <p className="text-[10px] uppercase tracking-wider text-white/45">Walk from prev</p>
            <p className="mt-1 text-lg font-semibold">{walk ? `${walk} min` : 'Start here'}</p>
          </div>
        </div>

        <div className="mt-4 rounded-2xl bg-black/25 p-3">
          <p className="text-[10px] uppercase tracking-wider text-white/45">Nearby alternatives</p>
          <ul className="mt-2 space-y-1 text-[13px] text-white/78">
            {poi.alternatives.map((a) => (
              <li key={a}>• {a}</li>
            ))}
          </ul>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => openDirections(poi.lat, poi.lng)}
            className="flex-1 rounded-2xl bg-gradient-to-r from-[#2d6a8f] to-[#1e3a52] px-4 py-3 text-[14px] font-semibold text-white shadow-lg shadow-black/35"
          >
            Open in Google Maps
          </button>
          <button
            type="button"
            onClick={share}
            className="rounded-2xl border border-white/20 px-4 py-3 text-[13px] font-semibold text-white/85"
          >
            Copy link
          </button>
          <button
            type="button"
            onClick={onClose}
            className="rounded-2xl border border-white/15 px-4 py-3 text-[13px] text-white/75"
          >
            Close
          </button>
        </div>

        <div className="mt-4 rounded-2xl border border-dashed border-white/18 bg-white/5 p-3 text-[11px] leading-relaxed text-white/55">
          Crowd forecast timeline · AI itinerary stitching · analytics widgets ship next — data blends live picks + curated baselines for a believable “live” feel.
        </div>
      </motion.div>
    </motion.div>
  )
}
