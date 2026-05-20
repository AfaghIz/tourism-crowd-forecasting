import { create } from 'zustand'
import type { ThemeMode } from './types'

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
  theme: ThemeMode
  hoveredId: string | null
  selectedId: string | null
  sheetExpanded: boolean
  favorites: Set<string>
  setHoveredId: (id: string | null) => void
  setSelectedId: (id: string | null) => void
  setSheetExpanded: (v: boolean) => void
  toggleTheme: () => void
  toggleFavorite: (id: string) => void
}

export const useExplorerStore = create<ExplorerStore>((set) => ({
  theme: 'day',
  hoveredId: null,
  selectedId: null,
  sheetExpanded: false,
  favorites: loadFavs(),

  setHoveredId: (id) => set({ hoveredId: id }),
  setSelectedId: (id) => set({ selectedId: id }),
  setSheetExpanded: (v) => set({ sheetExpanded: v }),
  toggleTheme: () => set((s) => ({ theme: s.theme === 'day' ? 'night' : 'day' })),
  toggleFavorite: (id) =>
    set((state) => {
      const next = new Set(state.favorites)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      saveFavs(next)
      return { favorites: next }
    })
}))
