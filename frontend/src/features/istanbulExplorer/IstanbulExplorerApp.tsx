import { useCallback, useId, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { AnimatePresence, motion, useMotionValue, useSpring, useTransform } from 'framer-motion'
import { useExplorerStore } from './store'
import { EXPLORER_POIS, SIDEBAR_ROUTES } from './data'
import { buildCurvedRoutePath } from './geometry'
import type { ExplorerPOI } from './types'
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
  return useMemo(() => {
    const ordered = EXPLORER_POIS
    return { ordered }
  }, [])
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
          width: 28,
          height: 28,
          maxWidth: 28,
          maxHeight: 28,
          display: 'block',
          objectFit: 'cover',
          flexShrink: 0,
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

export function IstanbulExplorerApp({
  openDirections
}: {
  openDirections: (poi: ExplorerPOI) => void
}) {
  const theme = useExplorerStore((s) => s.theme)
  const hoveredId = useExplorerStore((s) => s.hoveredId)
  const selectedId = useExplorerStore((s) => s.selectedId)
  const sheetExpanded = useExplorerStore((s) => s.sheetExpanded)
  const favorites = useExplorerStore((s) => s.favorites)

  const setHoveredId = useExplorerStore((s) => s.setHoveredId)
  const setSelectedId = useExplorerStore((s) => s.setSelectedId)
  const setSheetExpanded = useExplorerStore((s) => s.setSheetExpanded)

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
  const [routeExpanded, setRouteExpanded] = useState(false)
  const onWheel = useCallback((e: React.WheelEvent) => {
    if (!e.ctrlKey && !e.metaKey) return
    e.preventDefault()
    setZoom((z) => Math.min(1.55, Math.max(0.85, z - e.deltaY * 0.0015)))
  }, [])

  const routeCanvasRef = useRef<HTMLDivElement>(null)
  const videoStackHeightPx = null

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
  }, [routeExpanded, videoStackHeightPx, zoom])

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
        <div className="relative w-full min-h-0 max-w-full overflow-hidden rounded-[22px] border border-[#2d6a8f]/12 bg-[#fffaf2]/72 shadow-[0_18px_45px_rgba(42,36,28,0.08)] backdrop-blur-sm">
          <button
            type="button"
            onClick={() => setRouteExpanded((open) => !open)}
            className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left transition-colors hover:bg-white/45 sm:px-5"
            aria-expanded={routeExpanded}
            aria-controls="istanbul-landmark-route-panel"
          >
            <span className="min-w-0">
              <span className="block text-[11px] font-semibold uppercase tracking-[0.22em] text-[#2d6a8f]">
                Istanbul Landmark Route
              </span>
              <span className="mt-0.5 block truncate text-[13px] text-[#4f463b]/72">
                {routeExpanded
                  ? 'Hide the visual route map'
                  : 'Open the visual route map for iconic POIs'}
              </span>
            </span>
            <span
              className={`grid h-8 w-8 flex-shrink-0 place-items-center rounded-full border border-[#2d6a8f]/18 bg-white/70 text-[#2d6a8f] transition-transform duration-300 ${
                routeExpanded ? 'rotate-180' : ''
              }`}
              aria-hidden
            >
             ⌄
            </span>
          </button>

          <AnimatePresence initial={false}>
            {routeExpanded && (
              <motion.div
                id="istanbul-landmark-route-panel"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                className="overflow-hidden"
              >
        <div className="relative w-full min-h-0 max-w-full overflow-hidden border-t border-[#2d6a8f]/10 py-1 pr-0 sm:pr-0.5">
          <div
            ref={routeCanvasRef}
            onWheel={onWheel}
            className="relative isolate min-h-0 w-full max-w-full origin-center overflow-hidden transition-transform duration-300 ease-out"
            style={{
              transform: `scale(${zoom})`,
              ...(videoStackHeightPx
                ? { height: videoStackHeightPx, maxHeight: videoStackHeightPx }
                : { minHeight: 'min(420px, 50vh)' })
            }}
          >
            <svg
              viewBox={`-70 0 240 ${routeViewBoxH}`}
              className="absolute inset-0 block h-full w-full overflow-hidden"
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
                {ordered.map((p) => {
                  const pop = p.popularity / 100
                  const baseR = (3.15 + pop * 2.45) * 1.18
                  const imgBox = baseR * 3.55
                  return (
                    <clipPath
                      key={`clip-${p.id}`}
                      id={`${svgUid}-${p.id}-clip`}
                      clipPathUnits="userSpaceOnUse"
                    >
                      <rect
                        x={-imgBox / 2}
                        y={-imgBox / 2}
                        width={imgBox}
                        height={imgBox}
                        rx={imgBox * 0.18}
                        ry={imgBox * 0.18}
                      />
                    </clipPath>
                  )
                })}
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

              <path
                d={pathD}
                fill="none"
                stroke={
                  theme === 'night' ? 'rgba(255,255,255,0.38)' : 'rgba(42, 36, 28, 0.32)'
                }
                strokeWidth={1.1}
                strokeLinecap="round"
                strokeDasharray="5 14"
                pointerEvents="none"
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
                const label = `${p.name}. ${p.subtitle}. Focus this landmark on the live map.`
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
                        setSelectedId(p.id)
                        openDirections(p)
                      }}
                      role="button"
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault()
                          setSelectedId(p.id)
                          openDirections(p)
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
                            clipPath={`url(#${svgUid}-${p.id}-clip)`}
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

          </div>


        </div>
              </motion.div>
            )}
          </AnimatePresence>
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
  if (!sheetExpanded) return null

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
