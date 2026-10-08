// Frontend: the theme's storage key, context object and hook. The provider is
// ThemeContext.jsx; see there for what the theme is and where it is kept.
import { createContext, useContext } from 'react'

/** `cg1618:food:<thing>`, like lib/libraryView.js's keys. */
export const THEME_STORAGE_KEY = 'cg1618:food:theme'

export const ThemeContext = createContext(null)

/** `{ theme, preference, setTheme, toggle }` from the nearest ThemeProvider. */
export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used inside <ThemeProvider>')
  return context
}
