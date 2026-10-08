import { act, cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { THEME_STORAGE_KEY, useTheme } from './theme'
import { ThemeProvider } from './ThemeContext'

function Probe() {
  const { theme, preference, toggle, setTheme } = useTheme()
  return (
    <div>
      <span data-testid="theme">{theme}</span>
      <span data-testid="pref">{preference}</span>
      <button onClick={toggle}>toggle</button>
      <button onClick={() => setTheme('system')}>system</button>
    </div>
  )
}

function renderProbe() {
  render(
    <ThemeProvider>
      <Probe />
    </ThemeProvider>,
  )
}

let listeners
function stubMatchMedia(matches) {
  listeners = []
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({
      matches,
      addEventListener: (_, fn) => listeners.push(fn),
      removeEventListener: (_, fn) => listeners.splice(listeners.indexOf(fn), 1),
    })),
  )
}

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

it("uses food's own storage key", () => {
  expect(THEME_STORAGE_KEY).toBe('cg1618:food:theme')
})

it('follows the OS when nothing is stored, and stamps <html data-theme>', () => {
  stubMatchMedia(true)
  renderProbe()
  expect(screen.getByTestId('theme').textContent).toBe('dark')
  expect(screen.getByTestId('pref').textContent).toBe('system')
  expect(document.documentElement.dataset.theme).toBe('dark')
})

it('a stored choice beats the OS', () => {
  stubMatchMedia(true)
  localStorage.setItem(THEME_STORAGE_KEY, 'light')
  renderProbe()
  expect(screen.getByTestId('theme').textContent).toBe('light')
  expect(document.documentElement.dataset.theme).toBe('light')
})

it('toggle flips the theme and remembers it; system forgets it', () => {
  stubMatchMedia(false)
  renderProbe()
  expect(document.documentElement.dataset.theme).toBe('light')
  act(() => screen.getByText('toggle').click())
  expect(screen.getByTestId('theme').textContent).toBe('dark')
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  expect(document.documentElement.dataset.theme).toBe('dark')

  act(() => screen.getByText('system').click())
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBeNull()
  expect(screen.getByTestId('theme').textContent).toBe('light')
})

it('tracks OS changes while following the system', () => {
  stubMatchMedia(false)
  renderProbe()
  act(() => listeners.forEach((fn) => fn({ matches: true })))
  expect(screen.getByTestId('theme').textContent).toBe('dark')
  expect(document.documentElement.dataset.theme).toBe('dark')
})

it('still works when storage throws: the choice lasts for the session', () => {
  stubMatchMedia(false)
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
    throw new Error('blocked')
  })
  renderProbe()
  expect(screen.getByTestId('theme').textContent).toBe('light')
  act(() => screen.getByText('toggle').click())
  expect(screen.getByTestId('theme').textContent).toBe('dark')
  expect(document.documentElement.dataset.theme).toBe('dark')
})

it('useTheme outside the provider says so', () => {
  vi.spyOn(console, 'error').mockImplementation(() => {})
  expect(() => render(<Probe />)).toThrow(/ThemeProvider/)
})
