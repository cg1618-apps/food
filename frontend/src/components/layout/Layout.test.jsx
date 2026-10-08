import { act, cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, beforeEach, expect, it, vi } from 'vitest'

import { THEME_STORAGE_KEY } from '../../contexts/theme'
import { ThemeProvider } from '../../contexts/ThemeContext'
import Layout from './Layout'

function renderLayout() {
  render(
    <ThemeProvider>
      <MemoryRouter initialEntries={['/dishes']}>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/dishes" element={<p>page</p>} />
          </Route>
        </Routes>
      </MemoryRouter>
    </ThemeProvider>,
  )
}

beforeEach(() => {
  localStorage.clear()
  delete document.documentElement.dataset.theme
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} })),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

it('has one theme toggle, offering dark mode while the page is light', () => {
  renderLayout()
  const toggle = screen.getByRole('button', { name: '切換為深色模式' })
  expect(toggle.getAttribute('aria-pressed')).toBe('false')
  expect(screen.getAllByRole('button', { name: /切換為/ })).toHaveLength(1)
})

it('switches the theme, and then offers light mode', () => {
  renderLayout()
  act(() => screen.getByRole('button', { name: '切換為深色模式' }).click())
  expect(document.documentElement.dataset.theme).toBe('dark')
  expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe('dark')
  const toggle = screen.getByRole('button', { name: '切換為淺色模式' })
  expect(toggle.getAttribute('aria-pressed')).toBe('true')
})
