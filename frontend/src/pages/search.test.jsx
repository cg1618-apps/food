// The universal search: the top bar's box and its dropdown
// (components/layout/NavSearch.jsx), the phone's search row
// (components/layout/Layout.jsx), and the results page, /search.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider } from '../contexts/ThemeContext'
import AppRoutes from '../routes'

const hit = (id, display_name, detail = null, cover = null) => ({ id, display_name, detail, cover })

const EMPTY = {
  dishes: [],
  recipes: [],
  ingredients: [],
  notes: [],
  authors: [],
  heating: [],
  tbd: [],
}

const RESULTS = {
  ...EMPTY,
  dishes: [hit(1, '咖哩', '料理'), hit(2, '咖哩飯', '料理')],
  recipes: [hit(5, '快速版', '咖哩 · 阿基師', { thumb_url: '/images/t.jpg', focus: null })],
  heating: [hit(8, '咖哩調理包', '微波 2 分鐘')],
  tbd: [hit(9, '咖哩粉連結', '1 個連結')],
}

let answer
let searchRequests

function LocationProbe() {
  const { pathname, search, hash } = useLocation()
  return <output data-testid="location">{`${pathname}${search}${hash}`}</output>
}

const location = () => screen.getByTestId('location').textContent

function renderAt(path) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
          <LocationProbe />
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>,
  )
}

beforeEach(() => {
  answer = () => new Response(JSON.stringify({ query: 'x', results: RESULTS }), { status: 200 })
  searchRequests = []
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false, addEventListener() {}, removeEventListener() {} })),
  )
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => {
      if (String(url).startsWith('/api/search')) {
        searchRequests.push(String(url))
        return answer(url)
      }
      return new Response('[]', { status: 200 })
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

// The desktop field; the phone's row is a second NavSearch, opened below.
function topBarBox() {
  return screen.getAllByRole('combobox', { name: '搜尋全部' })[0]
}

async function typeInto(box, text) {
  fireEvent.change(box, { target: { value: text } })
  return screen.findByRole('listbox', { name: '搜尋建議' })
}

describe('the top bar search box', () => {
  it('asks the API once the typing settles, for a few rows per kind', async () => {
    renderAt('/schedule')
    await typeInto(topBarBox(), '咖哩')
    expect(searchRequests).toEqual([`/api/search?q=${encodeURIComponent('咖哩')}&limit=3`])
  })

  it('groups the rows under their kind, in kind order, each with its secondary line', async () => {
    renderAt('/schedule')
    const list = await typeInto(topBarBox(), '咖哩')
    const groups = within(list).getAllByRole('group')
    expect(groups.map((g) => g.getAttribute('aria-label'))).toEqual(['料理', '食譜', '加熱', 'TBD'])
    expect(within(groups[0]).getAllByRole('option').map((o) => o.textContent)).toEqual([
      '咖哩料理',
      '咖哩飯料理',
    ])
    expect(within(groups[1]).getByRole('option').textContent).toBe('快速版咖哩 · 阿基師')
  })

  it('opens a row on a click, and closes behind it', async () => {
    renderAt('/schedule')
    const list = await typeInto(topBarBox(), '咖哩')
    fireEvent.click(within(list).getByRole('option', { name: /快速版/ }))
    expect(location()).toBe('/recipes/5')
    expect(screen.queryByRole('listbox', { name: '搜尋建議' })).toBeNull()
    expect(topBarBox().value).toBe('')
  })

  it('opens a 加熱 row at its entry on the list page', async () => {
    renderAt('/schedule')
    const list = await typeInto(topBarBox(), '咖哩')
    fireEvent.click(within(list).getByRole('option', { name: /咖哩調理包/ }))
    expect(location()).toBe('/heating#heating-8')
  })

  it('walks the rows with the arrows and opens the highlighted one with Enter', async () => {
    renderAt('/schedule')
    const box = topBarBox()
    await typeInto(box, '咖哩')
    fireEvent.keyDown(box, { key: 'ArrowDown' })
    fireEvent.keyDown(box, { key: 'ArrowDown' })
    const selected = screen.getByRole('option', { selected: true })
    expect(selected.textContent).toBe('咖哩飯料理')
    expect(box.getAttribute('aria-activedescendant')).toBe(selected.id)
    // Up from the first row is "nothing highlighted"; up again wraps to the last.
    fireEvent.keyDown(box, { key: 'ArrowUp' })
    fireEvent.keyDown(box, { key: 'ArrowUp' })
    expect(screen.queryByRole('option', { selected: true })).toBeNull()
    fireEvent.keyDown(box, { key: 'ArrowUp' })
    expect(screen.getByRole('option', { selected: true }).textContent).toBe('咖哩粉連結1 個連結')
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(location()).toBe('/tbd#tbd-9')
  })

  it('opens the results page with Enter when no row is highlighted', async () => {
    renderAt('/schedule')
    const box = topBarBox()
    await typeInto(box, ' 咖哩 ')
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(location()).toBe(`/search?q=${encodeURIComponent('咖哩')}`)
  })

  it('closes on Escape and on a click outside', async () => {
    renderAt('/schedule')
    const box = topBarBox()
    await typeInto(box, '咖哩')
    fireEvent.keyDown(box, { key: 'Escape' })
    expect(screen.queryByRole('listbox', { name: '搜尋建議' })).toBeNull()
    expect(box.value).toBe('咖哩')

    fireEvent.focus(box)
    expect(screen.getByRole('listbox', { name: '搜尋建議' })).toBeTruthy()
    fireEvent.mouseDown(document.body)
    expect(screen.queryByRole('listbox', { name: '搜尋建議' })).toBeNull()
  })

  it('says when nothing matched', async () => {
    answer = () => new Response(JSON.stringify({ query: 'x', results: EMPTY }), { status: 200 })
    renderAt('/schedule')
    const list = await typeInto(topBarBox(), '沒有')
    expect(list.textContent).toContain('找不到「沒有」')
  })

  it('asks nothing for a blank term', async () => {
    renderAt('/schedule')
    fireEvent.change(topBarBox(), { target: { value: '   ' } })
    await act(() => new Promise((resolve) => setTimeout(resolve, 400)))
    expect(searchRequests).toEqual([])
  })
})

describe('the phone search row', () => {
  it('opens from the search icon, full width, and closes again', () => {
    renderAt('/schedule')
    expect(screen.getAllByRole('combobox', { name: '搜尋全部' })).toHaveLength(1)
    const toggle = screen.getByRole('button', { name: '搜尋' })
    expect(toggle.getAttribute('aria-expanded')).toBe('false')
    fireEvent.click(toggle)
    const row = document.getElementById('phone-search')
    expect(row).toBeTruthy()
    expect(within(row).getByRole('combobox', { name: '搜尋全部' })).toBe(document.activeElement)
    const close = screen.getByRole('button', { name: '關閉搜尋' })
    expect(close.getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(close)
    expect(document.getElementById('phone-search')).toBeNull()
  })

  it('closes once a search has gone somewhere', async () => {
    renderAt('/schedule')
    fireEvent.click(screen.getByRole('button', { name: '搜尋' }))
    const box = within(document.getElementById('phone-search')).getByRole('combobox')
    const list = await typeInto(box, '咖哩')
    fireEvent.click(within(list).getByRole('option', { name: /咖哩飯/ }))
    expect(location()).toBe('/dishes/2')
    expect(document.getElementById('phone-search')).toBeNull()
  })

  it('closes on a second Escape, once the dropdown is closed', async () => {
    renderAt('/schedule')
    fireEvent.click(screen.getByRole('button', { name: '搜尋' }))
    const box = within(document.getElementById('phone-search')).getByRole('combobox')
    await typeInto(box, '咖哩')
    fireEvent.keyDown(box, { key: 'Escape' })
    expect(document.getElementById('phone-search')).toBeTruthy()
    fireEvent.keyDown(box, { key: 'Escape' })
    expect(document.getElementById('phone-search')).toBeNull()
  })

  it('keeps the bar to one row at 360px: the field is hidden there, the icon is not', () => {
    renderAt('/schedule')
    const field = topBarBox().closest('[role="search"]')
    // The desktop field only shows from lg; below it the icon opens the row.
    expect(field.className).toContain('hidden')
    expect(field.className).toContain('lg:block')
    expect(screen.getByRole('button', { name: '搜尋' }).className).toContain('lg:hidden')
  })
})

describe('the results page', () => {
  it('asks for the term in the URL, up to the cap per kind', async () => {
    renderAt('/search?q=咖哩')
    await screen.findByRole('region', { name: '料理' })
    expect(searchRequests).toContain(`/api/search?q=${encodeURIComponent('咖哩')}&limit=50`)
    expect(screen.getByRole('searchbox', { name: '搜尋詞' }).value).toBe('咖哩')
  })

  it('lists each kind under its heading, every row linking to its page and its edit page', async () => {
    renderAt('/search?q=咖哩')
    const dishes = await screen.findByRole('region', { name: '料理' })
    expect(within(dishes).getByRole('link', { name: '咖哩' }).getAttribute('href')).toBe('/dishes/1')
    expect(within(dishes).getByRole('link', { name: '編輯 咖哩' }).getAttribute('href')).toBe(
      '/edit/dishes/1',
    )
    const recipes = screen.getByRole('region', { name: '食譜' })
    expect(within(recipes).getByRole('link', { name: '編輯 快速版' }).getAttribute('href')).toBe(
      '/edit/recipes/5',
    )
    expect(within(recipes).getByText('咖哩 · 阿基師')).toBeTruthy()
    const heating = screen.getByRole('region', { name: '加熱' })
    expect(within(heating).getByRole('link', { name: '咖哩調理包' }).getAttribute('href')).toBe(
      '/heating#heating-8',
    )
    expect(within(heating).getByRole('link', { name: '編輯 咖哩調理包' }).getAttribute('href')).toBe(
      '/edit/heating',
    )
    const tbd = screen.getByRole('region', { name: 'TBD' })
    expect(within(tbd).getByRole('link', { name: '編輯 咖哩粉連結' }).getAttribute('href')).toBe(
      '/edit/tbd',
    )
    // A kind with no match has no heading.
    expect(screen.queryByRole('region', { name: '食材' })).toBeNull()
  })

  it('says when nothing matched', async () => {
    answer = () => new Response(JSON.stringify({ query: 'x', results: EMPTY }), { status: 200 })
    renderAt('/search?q=沒有')
    expect(await screen.findByText('找不到「沒有」。')).toBeTruthy()
  })

  it('shows the error when the search fails', async () => {
    answer = () => new Response(JSON.stringify({ detail: '搜尋失敗' }), { status: 500 })
    renderAt('/search?q=咖哩')
    expect((await screen.findByRole('alert')).textContent).toContain('搜尋失敗')
  })

  it('asks nothing and invites a term when there is none', () => {
    renderAt('/search')
    expect(screen.getByText(/輸入名稱/)).toBeTruthy()
    expect(searchRequests).toEqual([])
  })

  it('shows that it is loading while it asks', async () => {
    answer = () => new Promise(() => {})
    renderAt('/search?q=咖哩')
    expect(await screen.findByText('載入中…')).toBeTruthy()
  })
})

describe('an entry opened at its anchor', () => {
  it('marks the 加熱 note the URL names, and only that one', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url) => {
        const body =
          url === '/api/heating'
            ? [
                { id: 3, name: '冷凍吐司', body: null, sort_order: 0 },
                { id: 8, name: '咖哩調理包', body: null, sort_order: 1 },
              ]
            : []
        return new Response(JSON.stringify(body), { status: 200 })
      }),
    )
    renderAt('/heating#heating-8')
    const list = await screen.findByRole('list', { name: '加熱' })
    const items = within(list).getAllByRole('listitem')
    expect(items.map((item) => item.getAttribute('aria-current'))).toEqual([null, 'true'])
    expect(items[1].id).toBe('heating-8')
  })

  it('marks the TBD entry the URL names', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url) => {
        const body =
          url === '/api/tbd'
            ? [
                { id: 9, name: '咖哩粉', sort_order: 0, links: [] },
                { id: 4, name: '別的', sort_order: 1, links: [] },
              ]
            : []
        return new Response(JSON.stringify(body), { status: 200 })
      }),
    )
    renderAt('/tbd#tbd-9')
    const list = await screen.findByRole('list', { name: 'TBD' })
    const items = within(list).getAllByRole('listitem')
    expect(items.map((item) => item.getAttribute('aria-current'))).toEqual(['true', null])
  })
})
