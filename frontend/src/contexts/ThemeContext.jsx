// Frontend: light / dark theme state, media's ThemeContext with food's key.
//
// The choice lives in localStorage ("light" | "dark" | "system"); "system" -
// the default, and what nothing stored means - follows prefers-color-scheme
// live. The DOM side effects are stamping <html data-theme="...">, which
// index.css keys both palettes off, and pointing the theme-color metas at the
// canvas colour actually on screen, so a phone's browser chrome matches a
// manual choice rather than the OS. index.html stamps the same attribute
// before first paint, so there is no flash of the wrong theme on load.
//
// Like every other remembered choice here (lib/libraryView.js), it is
// per-device and never reaches the server, and every storage access is in a
// try: a private window or blocked storage keeps the choice for the session.
//
// The key, the context object and useTheme() live in ./theme.js, so this file
// exports only a component (what fast refresh, and the linter, ask for).
import { useEffect, useMemo, useState } from 'react'

import { THEME_STORAGE_KEY, ThemeContext } from './theme'

const DARK_QUERY = '(prefers-color-scheme: dark)'

function readStored() {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

function systemPrefersDark() {
  try {
    return window.matchMedia(DARK_QUERY).matches
  } catch {
    return false
  }
}

// The browser-chrome colour follows the canvas token, read from the stylesheet
// rather than repeated here, so the palette stays in index.css alone.
function syncThemeColor() {
  const canvas = getComputedStyle(document.documentElement).getPropertyValue('--c-canvas').trim()
  if (!canvas) return
  for (const meta of document.querySelectorAll('meta[name="theme-color"]')) {
    meta.setAttribute('content', canvas)
  }
}

export function ThemeProvider({ children }) {
  const [preference, setPreference] = useState(readStored)
  const [systemDark, setSystemDark] = useState(systemPrefersDark)

  useEffect(() => {
    let query
    try {
      query = window.matchMedia(DARK_QUERY)
    } catch {
      return undefined
    }
    const onChange = (event) => setSystemDark(event.matches)
    query.addEventListener('change', onChange)
    return () => query.removeEventListener('change', onChange)
  }, [])

  const theme = preference === 'system' ? (systemDark ? 'dark' : 'light') : preference

  useEffect(() => {
    document.documentElement.dataset.theme = theme
    syncThemeColor()
  }, [theme])

  const value = useMemo(() => {
    function setTheme(next) {
      setPreference(next)
      try {
        if (next === 'system') localStorage.removeItem(THEME_STORAGE_KEY)
        else localStorage.setItem(THEME_STORAGE_KEY, next)
      } catch {
        /* storage unavailable: the choice lasts for this session */
      }
    }
    return {
      theme, // "light" | "dark" - what is on screen
      preference, // "light" | "dark" | "system" - what was chosen
      setTheme,
      toggle: () => setTheme(theme === 'dark' ? 'light' : 'dark'),
    }
  }, [theme, preference])

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}
