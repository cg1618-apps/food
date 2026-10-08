// TBD's read page, /tbd: each entry's name and its links, in the order the
// API gives, the links opening in a new tab; the empty state points at the
// edit page.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider } from '../../contexts/ThemeContext'
import AppRoutes from '../../routes'

const ENTRIES = [
  {
    id: 3,
    name: '想試的店',
    sort_order: 0,
    links: [
      { id: 7, url: 'https://example.com/shop', label: '甲店' },
      { id: 8, url: 'https://www.icook.tw/recipes/12/', label: null },
    ],
  },
  { id: 1, name: '只有名字', sort_order: 1, links: [] },
  { id: 2, name: null, sort_order: 2, links: [{ id: 9, url: 'https://youtu.be/x', label: null }] },
]

let entries

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
  entries = ENTRIES
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => {
      const body = url === '/api/tbd' ? entries : []
      return new Response(JSON.stringify(body), { status: 200 })
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('the TBD page', () => {
  it('lists the entries in order, each name over its links', async () => {
    renderAt('/tbd')
    const list = await screen.findByRole('list', { name: 'TBD' })
    const items = within(list).getAllByRole('listitem', { name: /./ })
    expect(items.map((item) => item.getAttribute('aria-label'))).toEqual(['想試的店', '只有名字', '未命名'])

    expect(within(items[0]).getByText('想試的店')).toBeTruthy()
    const links = within(items[0]).getAllByRole('link')
    expect(links.map((link) => link.textContent)).toEqual(['甲店', 'icook.tw/recipes/12'])
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      'https://example.com/shop',
      'https://www.icook.tw/recipes/12/',
    ])
    for (const link of links) {
      expect(link.getAttribute('target')).toBe('_blank')
      expect(link.getAttribute('rel')).toContain('noopener')
    }
    expect(within(items[1]).queryAllByRole('link')).toEqual([])
    // An entry with no name shows its links alone; the unlabelled link by its host.
    expect(within(items[2]).getByRole('link').textContent).toBe('youtu.be/x')
  })

  it('links to the edit page', async () => {
    renderAt('/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    const edit = screen.getByRole('link', { name: '編輯' })
    expect(edit.getAttribute('href')).toBe('/edit/tbd')
  })

  it('says it is empty and points at the edit page', async () => {
    entries = []
    renderAt('/tbd')
    expect(await screen.findByText(/還沒有任何東西/)).toBeTruthy()
    const edits = screen.getAllByRole('link', { name: '編輯' })
    expect(edits.every((link) => link.getAttribute('href') === '/edit/tbd')).toBe(true)
    expect(edits.length).toBe(2)
  })
})
