// Frontend: the top bar's line icons, drawn in currentColor so the control
// around them colours them. Decorative: the control carries the label.

const ICON_PROPS = {
  viewBox: '0 0 24 24',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.75,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
  'aria-hidden': true,
}

export function SunIcon({ className = 'size-5' }) {
  return (
    <svg {...ICON_PROPS} className={className}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2M12 19.5v2M2.5 12h2M19.5 12h2M5.3 5.3l1.4 1.4M17.3 17.3l1.4 1.4M5.3 18.7l1.4-1.4M17.3 6.7l1.4-1.4" />
    </svg>
  )
}

export function MoonIcon({ className = 'size-5' }) {
  return (
    <svg {...ICON_PROPS} className={className}>
      <path d="M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z" />
    </svg>
  )
}

export function SearchIcon({ className = 'size-5' }) {
  return (
    <svg {...ICON_PROPS} className={className}>
      <circle cx="11" cy="11" r="6.5" />
      <path d="m20 20-4.4-4.4" />
    </svg>
  )
}

export function CloseIcon({ className = 'size-5' }) {
  return (
    <svg {...ICON_PROPS} className={className}>
      <path d="M6 6l12 12M18 6 6 18" />
    </svg>
  )
}
