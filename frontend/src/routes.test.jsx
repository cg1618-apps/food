import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, render, screen, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { SECTIONS } from './lib/nav'
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
    ['/dishes', '料理'],
    ['/recipes', '食譜'],
    ['/notes', '筆記'],
    ['/edit/dishes/new', '新增料理'],
    ['/edit/dishes/1', '編輯料理'],
    ['/edit/recipes/new', '新增食譜'],
    ['/edit/recipes/1', '編輯食譜'],
    ['/edit/recipes/new?blank=1', '新增食譜'],
    ['/edit/templates/new', '新增範本'],
    ['/edit/templates/1', '編輯範本'],
    ['/edit/notes/new', '新增筆記'],
    ['/edit/notes/1', '編輯筆記'],
    ['/edit/settings', '設定'],
    ['/edit/images', '圖片'],
    ['/schedule', '排程'],
    ['/edit/schedule', '編輯排程'],
    ['/tbd', 'TBD'],
    ['/edit/tbd', '編輯 TBD'],
    ['/no/such/page', '找不到這一頁'],
  ])('%s renders its page', (path, heading) => {
    expect(renderAt(path)).toBe(path)
    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeTruthy()
  })
})

// The detail pages fetch before they have a heading; their content is
// pages/detail/details.test.jsx's. Here only that the route is theirs.
describe('every detail page has a route', () => {
  it.each(['/dishes/1', '/recipes/1', '/ingredients/1', '/notes/1'])('%s stays on its route', (path) => {
    expect(renderAt(path)).toBe(path)
    expect(screen.queryByRole('heading', { name: '找不到這一頁' })).toBeNull()
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
    // The dish form's path as the design named it.
    ['/edit/dishes/4/edit', '/edit/dishes/4'],
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

  it('marks TBD on its edit page too', () => {
    renderAt('/edit/tbd')
    const current = screen.getAllByRole('link', { current: 'page' }).map((link) => link.textContent)
    expect(current).toEqual(['TBD', 'TBD'])
  })

  it('gives the phone bar one column per section, whatever their number', () => {
    renderAt('/recipes')
    const [, phone] = screen.getAllByRole('navigation', { name: '主要' })
    expect(SECTIONS.length).toBe(7)
    expect(phone.style.gridTemplateColumns).toBe(`repeat(${SECTIONS.length}, minmax(0, 1fr))`)
    expect(within(phone).getAllByRole('link').map((link) => link.textContent)).toEqual(
      SECTIONS.map((section) => section.label),
    )
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

// A click into the edit pages never reaches Access, so the page asks the
// session probe and, when Access answers with a redirect, sends the whole
// window through the login (components/layout/EditSignIn.jsx).
describe('signing in on entering the edit pages', () => {
  const SESSION = '/api/edit/session'

  function stubAccess({ signedIn }) {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    const fetchMock = vi.fn(async (url) => {
      if (url !== SESSION) return new Response('[]', { status: 200 })
      return signedIn
        ? new Response(null, { status: 204 })
        : { type: 'opaqueredirect', ok: false, status: 0 }
    })
    vi.stubGlobal('fetch', fetchMock)
    return { assign, fetchMock }
  }

  const settle = () => new Promise((resolve) => setTimeout(resolve, 0))

  beforeEach(() => window.sessionStorage.clear())

  it('sends a signed-out browser through the login and back to the page', async () => {
    const { assign } = stubAccess({ signedIn: false })
    renderAt('/edit/settings?tab=labels')
    await vi.waitFor(() =>
      expect(assign).toHaveBeenCalledWith(`${SESSION}?next=%2Fedit%2Fsettings%3Ftab%3Dlabels`),
    )
  })

  // The mirror, with the same stub: a green above is the probe's answer doing
  // the redirecting, not the wrapper redirecting unconditionally.
  it('leaves a signed-in browser where it is', async () => {
    const { assign, fetchMock } = stubAccess({ signedIn: true })
    renderAt('/edit/settings')
    await vi.waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith(SESSION, expect.objectContaining({ redirect: 'manual' })),
    )
    await settle()
    expect(assign).not.toHaveBeenCalled()
  })

  it('never asks on the public pages', async () => {
    const { fetchMock } = stubAccess({ signedIn: false })
    renderAt('/recipes')
    await settle()
    expect(fetchMock.mock.calls.map(([url]) => url)).not.toContain(SESSION)
  })
})
