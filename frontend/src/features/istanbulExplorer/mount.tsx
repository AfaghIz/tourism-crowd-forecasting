import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './explorer.css'
import { IstanbulExplorerApp } from './IstanbulExplorerApp'
import type { ExplorerPOI } from './types'

export function mountIstanbulExplorer(openDirections: (poi: ExplorerPOI) => void): void {
  const el = document.getElementById('popularPathMount')
  if (!el) return
  createRoot(el).render(
    <StrictMode>
      <IstanbulExplorerApp openDirections={openDirections} />
    </StrictMode>
  )
}
