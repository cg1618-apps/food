// 加熱's read page, /heating: each note's name over how to heat it, in the
// order the API gives; the empty state points at the edit page.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider } from '../../contexts/ThemeContext'
import AppRoutes from '../../routes'

const NOTES = [
  { id: 3, name: '冷凍吐司', body: '烤箱 180 度\n5 分鐘', sort_order: 0 },
  { id: 1, name: '香腸', body: null, sort_order: 1 },
]

let notes

function renderAt(path) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>,
  )
}

beforeEach(() => {
  notes = NOTES
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => {
      const body = url === '/api/heating' ? notes : []
      return new Response(JSON.stringify(body), { status: 200 })
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('the 加熱 page', () => {
  it('lists the notes in order, each name over how to heat it', async () => {
    renderAt('/heating')
    const list = await screen.findByRole('list', { name: '加熱' })
    const items = within(list).getAllByRole('listitem')
    expect(items.map((item) => item.getAttribute('aria-label'))).toEqual(['冷凍吐司', '香腸'])
    const how = within(items[0]).getByText(/烤箱 180 度/)
    expect(how.textContent).toBe('烤箱 180 度\n5 分鐘')
    expect(how.className).toContain('whitespace-pre-line')
    // A note with no body is its name alone.
    expect(items[1].textContent).toBe('香腸')
  })

  it('links to the edit page', async () => {
    renderAt('/heating')
    await screen.findByRole('list', { name: '加熱' })
    expect(screen.getByRole('link', { name: '編輯' }).getAttribute('href')).toBe('/edit/heating')
  })

  it('says it is empty and points at the edit page', async () => {
    notes = []
    renderAt('/heating')
    expect(await screen.findByText(/還沒有任何加熱筆記/)).toBeTruthy()
    const edits = screen.getAllByRole('link', { name: '編輯' })
    expect(edits.length).toBe(2)
    expect(edits.every((link) => link.getAttribute('href') === '/edit/heating')).toBe(true)
  })
})
