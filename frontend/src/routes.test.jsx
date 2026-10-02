import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AppRoutes from './routes'

// Where the router ended up, so a redirect is asserted by its destination.
function LocationProbe() {
  const { pathname, search } = useLocation()
  return <output data-testid="location">{`${pathname}${search}`}</output>
}

function renderAt(path) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
  return screen.getByTestId('location').textContent
}

beforeEach(() => {
  // The pages that already fetch get an empty answer; nothing here is about data.
  vi.stubGlobal('fetch', vi.fn(async () => new Response('[]', { status: 200 })))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('every page has a route', () => {
  it.each([
    ['/recipes', '食譜'],
    ['/recipes/1', '食譜'],
    ['/notes', '筆記'],
    ['/notes/1', '筆記'],
    ['/edit/recipes/new', '新增食譜'],
    ['/edit/recipes/1', '編輯食譜'],
    ['/edit/notes/new', '新增筆記'],
    ['/edit/notes/1', '編輯筆記'],
    ['/edit/settings', '設定'],
    ['/edit/images', '圖片'],
    ['/no/such/page', '找不到這一頁'],
  ])('%s renders its page', (path, heading) => {
    expect(renderAt(path)).toBe(path)
    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeTruthy()
  })
})

describe('redirects', () => {
  it.each([
    ['/', '/recipes'],
    ['/settings', '/edit/settings'],
    // The first release's paths: bookmarks survive, query string included.
    ['/library/ingredient', '/ingredients'],
    ['/library/ingredient?category=3', '/ingredients?category=3'],
    ['/ingredient/7', '/ingredients/7'],
    ['/edit/ingredient/new', '/edit/ingredients/new'],
    ['/edit/ingredient/7', '/edit/ingredients/7'],
    ['/edit/vocabularies', '/edit/settings'],
  ])('%s goes to %s', (from, to) => {
    expect(renderAt(from)).toBe(to)
  })
})

describe('navigation', () => {
  it('marks the section of the current page, edit pages included', () => {
    renderAt('/edit/recipes/1')
    const current = screen
      .getAllByRole('link', { current: 'page' })
      .map((link) => link.textContent)
    // Two navs - the desktop bar and the phone bar - both say 食譜.
    expect(current).toEqual(['食譜', '食譜'])
  })

  it('links 設定 to the gated settings page', () => {
    renderAt('/recipes')
    const settings = screen.getAllByRole('link', { name: '設定' })
    expect(settings.map((link) => link.getAttribute('href'))).toEqual([
      '/edit/settings',
      '/edit/settings',
    ])
  })
})
