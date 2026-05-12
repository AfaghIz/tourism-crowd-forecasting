import { create } from 'zustand'
import type { ExplorerTag, RouteMode, ThemeMode } from './types'

const FAV_KEY = 'icc_explorer_fav_v1'

function loadFavs(): Set<string> {
  try {
    const raw = localStorage.getItem(FAV_KEY)
    if (!raw) return new Set()
    const p = JSON.parse(raw) as unknown
    return new Set(Array.isArray(p) ? p.filter((x): x is string => typeof x === 'string') : [])
  } catch {
    return new Set()
  }
}

function saveFavs(set: Set<string>) {
  try {
    localStorage.setItem(FAV_KEY, JSON.stringify([...set]))
  } catch {
    /* ignore */
  }
}

export interface ExplorerStore {
  tagsFilter: Set<ExplorerTag>
  routeMode: RouteMode
  theme: ThemeMode
  hoveredId: string | null
  selectedId: string | null
  sheetExpanded: boolean
  playback: boolean
  favorites: Set<string>
  filterFabOpen: boolean
  setHoveredId: (id: string | null) => void
  setSelectedId: (id: string | null) => void
  setSheetExpanded: (v: boolean) => void
  togglePlayback: () => void
  setRouteMode: (m: RouteMode) => void
  toggleTheme: () => void
  toggleTag: (t: ExplorerTag) => void
  clearTags: () => void
  toggleFavorite: (id: string) => void
  setFilterFabOpen: (v: boolean) => void
}

export const useExplorerStore = create<ExplorerStore>((set) => ({
  tagsFilter: new Set(),
  routeMode: 'scenic',
  theme: 'day',
  hoveredId: null,
  selectedId: null,
  sheetExpanded: false,
  playback: false,
  favorites: loadFavs(),
  filterFabOpen: false,

  setHoveredId: (id) => set({ hoveredId: id }),
  setSelectedId: (id) => set({ selectedId: id, sheetExpanded: Boolean(id) }),
  setSheetExpanded: (v) => set({ sheetExpanded: v }),
  togglePlayback: () => set((s) => ({ playback: !s.playback })),
  setRouteMode: (m) => set({ routeMode: m }),
  toggleTheme: () => set((s) => ({ theme: s.theme === 'day' ? 'night' : 'day' })),
  toggleTag: (t) =>
    set((state) => {
      const next = new Set(state.tagsFilter)
      if (next.has(t)) next.delete(t)
      else next.add(t)
      return { tagsFilter: next }
    }),
  clearTags: () => set({ tagsFilter: new Set() }),
  toggleFavorite: (id) =>
    set((state) => {
      const next = new Set(state.favorites)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      saveFavs(next)
      return { favorites: next }
    }),
  setFilterFabOpen: (v) => set({ filterFabOpen: v })
}))
