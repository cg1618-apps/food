// The library scaffold, through the three real pages: filters come from and go
// to the URL, the list is fetched with them, the two empties point different
// ways, and the 封面 / 清單 choice is remembered.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AppRoutes from '../../routes'

const CATEGORIES = [
  {
    id: 2,
    display_name: '蔬菜',
    parent_id: null,
    children: [{ id: 9, display_name: '葉菜', parent_id: 2, children: [], ingredient_count: 1 }],
    ingredient_count: 1,
  },
]

const CABBAGE = {
  id: 1,
  display_name: '高麗菜',
  name_en: 'Cabbage',
  category_id: 2,
  parent_id: null,
  needs_detail: true,
  rating: 'A',
  fridge: { min: 7, max: 14 },
  cover: null,
  used_in_count: 2,
}

const RECIPE = {
  id: 5,
  display_name: '炒高麗菜',
  kind: 'dish',
  status: 'want',
  course: { id: 1, display_name: '配菜' },
  methods: [{ id: 3, display_name: '炒' }],
  creators: ['阿基師'],
  time: '15 分鐘',
  written_up: false,
  cover: { thumb_url: '/images/t.jpg', focus: '20% 80%' },
}

let responses
let requested

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
}

const location = () => screen.getByTestId('location').textContent

// The list request for `path` (no other endpoint shares its path), decoded.
const listRequests = (path) =>
  requested.filter((url) => url === path || url.startsWith(`${path}?`)).map(decodeURIComponent)

beforeEach(() => {
  localStorage.clear()
  requested = []
  responses = {}
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url) => {
      requested.push(url)
      const path = url.split('?')[0]
      const body = typeof responses[path] === 'function' ? responses[path](url) : responses[path]
      return new Response(JSON.stringify(body ?? []), { status: 200 })
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('the ingredient library', () => {
  // The known defect: the ingredient page links to /ingredients?category=N
  // and the library ignored the query.
  it('filters by the category in the URL, as the detail page links it', async () => {
    responses['/api/ingredient-categories'] = CATEGORIES
    renderAt('/ingredients?category=2')
    await waitFor(() =>
      expect(listRequests('/api/ingredients')).toContain('/api/ingredients?category_id=2'),
    )
    const node = await screen.findByRole('button', { name: /蔬菜/, pressed: true })
    expect(node).toBeTruthy()
  })

  it('writes a filter click to the URL and refetches with it', async () => {
    responses['/api/ingredient-categories'] = CATEGORIES
    renderAt('/ingredients')
    const sidebar = screen.getByRole('complementary', { name: '篩選' })
    fireEvent.click(await within(sidebar).findByRole('button', { name: /葉菜/ }))
    expect(location()).toBe('/ingredients?category=9')
    await waitFor(() =>
      expect(listRequests('/api/ingredients')).toContain('/api/ingredients?category_id=9'),
    )
  })

  it('shows the stub backlog count before the filter is on', async () => {
    responses['/api/ingredients'] = (url) => (url.includes('?') ? [] : [CABBAGE])
    renderAt('/ingredients')
    const sidebar = screen.getByRole('complementary', { name: '篩選' })
    const toggle = within(sidebar).getByRole('checkbox', { name: /只看待補/ })
    await waitFor(() => expect(toggle.closest('label').textContent).toContain('1'))
    fireEvent.click(toggle)
    expect(location()).toBe('/ingredients?stub=1')
  })

  it('offers the add button when the library is empty', async () => {
    renderAt('/ingredients')
    expect(await screen.findByText('還沒有任何食材。')).toBeTruthy()
    const adds = screen.getAllByRole('link', { name: '新增食材' })
    expect(adds.at(-1).getAttribute('href')).toBe('/edit/ingredients/new')
  })

  it('offers clearing when only the filters leave it empty', async () => {
    renderAt('/ingredients?category=2&q=蔥')
    expect(await screen.findByText('沒有符合條件的食材。')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '清除搜尋與篩選' }))
    expect(location()).toBe('/ingredients')
  })

  it('draws a cover with its badges, and a table remembered once chosen', async () => {
    responses['/api/ingredients'] = [CABBAGE]
    responses['/api/ingredient-categories'] = CATEGORIES
    renderAt('/ingredients')
    expect(await screen.findByText('高麗菜')).toBeTruthy()
    expect(screen.getByText('待補')).toBeTruthy()
    expect(screen.getByLabelText('評等 A')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '清單', pressed: false }))
    const table = screen.getByRole('table')
    expect(within(table).getByText('7–14 天')).toBeTruthy()
    expect(within(table).getByText('蔬菜')).toBeTruthy()
    expect(localStorage.getItem('cg1618:food:ingredients-view')).toBe('list')
  })
})

describe('the recipe library', () => {
  it('sends an "any of" filter as the key repeated', async () => {
    renderAt('/recipes?course=1&course=4&written=false')
    await waitFor(() =>
      expect(listRequests('/api/recipes')).toContain(
        '/api/recipes?course_id=1&course_id=4&written_up=false',
      ),
    )
  })

  it('marks a recipe that is only a bookmark, and applies the cover focus', async () => {
    responses['/api/recipes'] = [RECIPE]
    renderAt('/recipes')
    expect(await screen.findByText('炒高麗菜')).toBeTruthy()
    expect(screen.getByText('書籤')).toBeTruthy()
    const img = document.querySelector('img')
    expect(img.getAttribute('loading')).toBe('lazy')
    expect(img.style.objectPosition).toBe('20% 80%')
  })

  it('writes the search term to the URL once the typing stops', async () => {
    renderAt('/recipes')
    fireEvent.change(screen.getByRole('searchbox', { name: '搜尋' }), {
      target: { value: '高麗菜' },
    })
    expect(location()).toBe('/recipes')
    await waitFor(() => expect(location()).toBe('/recipes?q=%E9%AB%98%E9%BA%97%E8%8F%9C'))
    await waitFor(() => expect(listRequests('/api/recipes')).toContain('/api/recipes?q=高麗菜'))
  })
})

describe('the note library', () => {
  it('filters by kind from the URL', async () => {
    renderAt('/notes?kind=technique')
    await waitFor(() =>
      expect(listRequests('/api/kitchen-notes')).toContain('/api/kitchen-notes?kind=technique'),
    )
  })
})
