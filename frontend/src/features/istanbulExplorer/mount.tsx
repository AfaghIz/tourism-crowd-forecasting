import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './explorer.css'
import { IstanbulExplorerApp } from './IstanbulExplorerApp'

export function mountIstanbulExplorer(openDirections: (lat: number, lng: number) => void): void {
  const el = document.getElementById('popularPathMount')
  if (!el) return
  createRoot(el).render(
    <StrictMode>
      <IstanbulExplorerApp openDirections={openDirections} />
    </StrictMode>
  )
}
