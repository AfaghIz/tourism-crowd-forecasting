type Props = { className?: string }

export function PlaceGlyph({ id, className }: Props & { id: string }) {
  switch (id) {
    case 'hagia':
      return <IconDome className={className} />
    case 'blue':
      return <IconMinaret className={className} />
    case 'topkapi':
      return <IconPalace className={className} />
    case 'bazaar':
      return <IconMarket className={className} />
    case 'galata':
      return <IconTower className={className} />
    case 'dolma':
      return <IconWaterPalace className={className} />
    case 'bridge':
      return <IconBridge className={className} />
    case 'spice':
      return <IconSpice className={className} />
    case 'maiden':
      return <IconIslandTower className={className} />
    case 'taksim':
      return <IconSquare className={className} />
    default:
      return <IconPin className={className} />
  }
}

function IconDome({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path
        d="M20 6c-8 4.5-12 12.5-12 21h24c0-8.5-4-16.5-12-21z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <path d="M10 27h20M14 31h12" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function IconMinaret({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path
        d="M20 4L16 32h8L20 4z"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinejoin="round"
      />
      <circle cx="20" cy="8" r="2.2" fill="currentColor" />
    </svg>
  )
}

function IconPalace({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path
        d="M6 32V18l6-4 4 3 4-3 4 3 4-3 6 4v14H6z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M10 32V22M20 19v13M30 32V22" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  )
}

function IconMarket({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path
        d="M6 16L10 8h20l4 8v4H6v-4zM8 32V20M20 20v12M32 20v12"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconTower({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path
        d="M20 4L12 32h16L20 4z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path
        d="M16 20c0-2.2 1.8-4 4-4s4 1.8 4 4"
        stroke="currentColor"
        strokeWidth="1.4"
      />
    </svg>
  )
}

function IconWaterPalace({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path
        d="M6 28c4-6 8-4 12-8 4 4 8 2 12 8v6H6v-6z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M8 18h24" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function IconBridge({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path
        d="M4 26h32M8 26V14M20 26V10M32 26V14"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path
        d="M4 18c5-4 11-4 16 0s11 4 16 0"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
      />
    </svg>
  )
}

function IconSpice({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path
        d="M14 8l12 8-12 8V8zM26 16v18l-8-5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconIslandTower({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path d="M8 28c8-10 16-10 24 0" stroke="currentColor" strokeWidth="1.4" />
      <path
        d="M18 28V14h4l2 14"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <path d="M16 14h8" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" />
    </svg>
  )
}

function IconSquare({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <rect x="10" y="14" width="20" height="18" rx="2" stroke="currentColor" strokeWidth="1.5" />
      <path d="M14 22h12M14 26h12" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

function IconPin({ className }: Props) {
  return (
    <svg viewBox="0 0 40 40" fill="none" className={className} aria-hidden="true">
      <path
        d="M20 6c-5 0-9 4-9 9 0 7 9 17 9 17s9-10 9-17c0-5-4-9-9-9z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
      <circle cx="20" cy="15" r="2.5" fill="currentColor" />
    </svg>
  )
}
