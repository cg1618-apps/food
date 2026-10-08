// The library scaffold, through the four real pages: filters come from and go
// to the URL, the list is fetched with them, the two empties point different
// ways, and the 封面 / 清單 choice is remembered.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider } from '../../contexts/ThemeContext'
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
  display_name: '阿基師版',
  name: '阿基師版',
  dish: { id: 11, display_name: '炒高麗菜', kind: 'dish' },
  status: { id: 2, display_name: '想試' },
  course: { id: 1, display_name: '配菜' },
  methods: [{ id: 3, display_name: '炒' }],
  authors: [{ id: 6, display_name: '阿基師' }],
  time: '15 分鐘',
  written_up: false,
  cover: { thumb_url: '/images/t.jpg', focus: '20% 80%' },
}

const TERIYAKI = {
  id: 11,
  display_name: '照燒醬',
  name_cn: '照燒醬',
  name_en: 'Teriyaki sauce',
  name_alt: null,
  kind: 'sauce',
  course: null,
  region: { id: 3, display_name: '日式' },
  labels: [],
  recipe_count: 2,
  cover: { thumb_url: '/images/d.jpg', focus: null },
}

const FIXED = {
  dish_kinds: [
    { value: 'dish', label: '料理' },
    { value: 'sauce', label: '醬料' },
  ],
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

  // Branches start closed: 葉菜 is reached by opening 蔬菜.
  it('writes a filter click to the URL and refetches with it', async () => {
    responses['/api/ingredient-categories'] = CATEGORIES
    renderAt('/ingredients')
    const sidebar = screen.getByRole('complementary', { name: '篩選' })
    expect(within(sidebar).queryByRole('button', { name: /葉菜/ })).toBeNull()
    fireEvent.click(await within(sidebar).findByRole('button', { name: '展開 蔬菜' }))
    fireEvent.click(within(sidebar).getByRole('button', { name: /葉菜/ }))
    expect(location()).toBe('/ingredients?category=9')
    await waitFor(() =>
      expect(listRequests('/api/ingredients')).toContain('/api/ingredients?category_id=9'),
    )
  })

  describe('groups', () => {
    const MEAT = [{ id: 3, display_name: '肉類', parent_id: null, children: [], ingredient_count: 3 }]
    const meat = (id, name, parent_id = null) => ({
      ...CABBAGE,
      id,
      display_name: name,
      name_en: null,
      category_id: 3,
      parent_id,
      needs_detail: false,
      rating: null,
      fridge: null,
      used_in_count: 0,
    })
    const CHICKEN = meat(20, '雞肉')
    const THIGH = meat(21, '雞腿', 20)
    const BACON = meat(22, '培根')

    beforeEach(() => {
      responses['/api/ingredient-categories'] = MEAT
      responses['/api/ingredients'] = [BACON, CHICKEN, THIGH]
    })

    it('files a group under its category in the tree, and choosing it lists the group', async () => {
      renderAt('/ingredients?category=3')
      const sidebar = screen.getByRole('complementary', { name: '篩選' })
      fireEvent.click(await within(sidebar).findByRole('button', { name: '展開 肉類' }))
      fireEvent.click(await within(sidebar).findByRole('button', { name: /雞肉/ }))
      // The category is cleared in the same step: never both.
      expect(location()).toBe('/ingredients?group=20')
      await waitFor(() =>
        expect(listRequests('/api/ingredients')).toContain('/api/ingredients?group_id=20'),
      )
    })

    // The categories answer before the ingredient list that holds the groups,
    // so the path to 雞肉 does not exist on the first draw. Delaying the list
    // is what makes this bite: answered together, it passed while the real
    // page left 肉類 closed.
    it('opens the path to a group chosen in the URL, once the groups arrive', async () => {
      let release
      const gate = new Promise((resolve) => (release = resolve))
      const fetchNow = globalThis.fetch
      vi.stubGlobal(
        'fetch',
        vi.fn(async (url) => {
          if (url.startsWith('/api/ingredients')) await gate
          return fetchNow(url)
        }),
      )
      renderAt('/ingredients?group=20')
      const sidebar = screen.getByRole('complementary', { name: '篩選' })
      await within(sidebar).findByRole('button', { name: /肉類/ })
      release()
      expect(await within(sidebar).findByRole('button', { name: /雞肉/, pressed: true })).toBeTruthy()
    })

    it('sections the list by category, the group first with its variety inside it', async () => {
      renderAt('/ingredients')
      const section = await screen.findByRole('region', { name: '肉類' })
      const names = within(section)
        .getAllByRole('link')
        .map((link) => link.textContent.replace('└', ''))
      expect(names[0]).toContain('雞肉')
      expect(names.at(-1)).toContain('培根')
      const varieties = within(section).getByRole('list', { name: '雞肉 的品種' })
      expect(within(varieties).getByText('雞腿')).toBeTruthy()
      expect(within(section).getByText('1 個品種')).toBeTruthy()
    })

    // 只看主項 sends has_parent=false; a bool key could never send false.
    it('sends 只看主項 and 只看品種 as has_parent', async () => {
      renderAt('/ingredients')
      const sidebar = screen.getByRole('complementary', { name: '篩選' })
      fireEvent.click(within(sidebar).getByRole('button', { name: '只看主項' }))
      expect(location()).toBe('/ingredients?variety=top')
      await waitFor(() =>
        expect(listRequests('/api/ingredients')).toContain('/api/ingredients?has_parent=false'),
      )
    })

    it('still reads the old 只看品種 switch from a link', async () => {
      renderAt('/ingredients?variety=1')
      await waitFor(() =>
        expect(listRequests('/api/ingredients')).toContain('/api/ingredients?has_parent=true'),
      )
      const sidebar = screen.getByRole('complementary', { name: '篩選' })
      expect(within(sidebar).getByRole('button', { name: '只看品種', pressed: true })).toBeTruthy()
    })
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

describe('the dish library', () => {
  it('sends every filter in the URL as the key repeated', async () => {
    renderAt('/dishes?kind=sauce&course=1&course=4&region=3&label=7')
    await waitFor(() =>
      expect(listRequests('/api/dishes')).toContain(
        '/api/dishes?kind=sauce&course_id=1&course_id=4&region_id=3&label_id=7',
      ),
    )
  })

  it('writes a 種類 and a 地區 click to the URL and refetches with them', async () => {
    responses['/api/vocabularies/fixed'] = FIXED
    responses['/api/regions'] = [{ id: 3, display_name: '日式', sort_order: 30, usage_count: 1 }]
    renderAt('/dishes')
    const sidebar = screen.getByRole('complementary', { name: '篩選' })
    fireEvent.click(await within(sidebar).findByRole('button', { name: /醬料/ }))
    expect(location()).toBe('/dishes?kind=sauce')
    fireEvent.click(await within(sidebar).findByRole('button', { name: /日式/ }))
    expect(location()).toBe('/dishes?kind=sauce&region=3')
    await waitFor(() =>
      expect(listRequests('/api/dishes')).toContain('/api/dishes?kind=sauce&region_id=3'),
    )
  })

  it('draws a dish as a cover with its kind, region and recipe count, and as a table row', async () => {
    responses['/api/dishes'] = [TERIYAKI]
    responses['/api/vocabularies/fixed'] = FIXED
    renderAt('/dishes')
    const title = await screen.findByText('照燒醬')
    const card = title.closest('a')
    expect(card.getAttribute('href')).toBe('/dishes/11')
    await waitFor(() => expect(card.textContent).toContain('醬料 · 日式 · 2 份食譜'))

    fireEvent.click(screen.getByRole('button', { name: '清單', pressed: false }))
    const table = screen.getByRole('table')
    expect(within(table).getByText('2 份')).toBeTruthy()
    expect(localStorage.getItem('cg1618:food:dishes-view')).toBe('list')
  })

  it('offers the add button when the library is empty', async () => {
    renderAt('/dishes')
    expect(await screen.findByText('還沒有任何料理。')).toBeTruthy()
    const adds = screen.getAllByRole('link', { name: '新增料理' })
    expect(adds.at(-1).getAttribute('href')).toBe('/edit/dishes/new')
  })
})

describe('the recipe library', () => {
  it('filters by dish and by the dish kind, with the dishes as the options', async () => {
    responses['/api/dishes'] = [TERIYAKI]
    responses['/api/vocabularies/fixed'] = FIXED
    renderAt('/recipes')
    const sidebar = screen.getByRole('complementary', { name: '篩選' })
    fireEvent.click(await within(sidebar).findByRole('button', { name: /照燒醬/ }))
    expect(location()).toBe('/recipes?dish=11')
    fireEvent.click(await within(sidebar).findByRole('button', { name: /料理/ }))
    expect(location()).toBe('/recipes?dish=11&kind=dish')
    await waitFor(() =>
      expect(listRequests('/api/recipes')).toContain('/api/recipes?dish_id=11&kind=dish'),
    )
  })


  it('sends an "any of" filter as the key repeated', async () => {
    renderAt('/recipes?course=1&course=4&written=false')
    await waitFor(() =>
      expect(listRequests('/api/recipes')).toContain(
        '/api/recipes?course_id=1&course_id=4&written_up=false',
      ),
    )
  })

  it('filters by status id, with the statuses as the options', async () => {
    responses['/api/recipe-statuses'] = [
      { id: 2, display_name: '想試', sort_order: 10, usage_count: 1 },
      { id: 3, display_name: '可煮', sort_order: 20, usage_count: 0 },
    ]
    renderAt('/recipes')
    const sidebar = screen.getByRole('complementary', { name: '篩選' })
    fireEvent.click(await within(sidebar).findByRole('button', { name: /可煮/ }))
    expect(location()).toBe('/recipes?status=3')
    await waitFor(() => expect(listRequests('/api/recipes')).toContain('/api/recipes?status_id=3'))
  })

  it('filters by author id, with the authors as the options', async () => {
    responses['/api/authors'] = [
      { id: 6, display_name: '阿基師', sort_order: 0, usage_count: 1 },
      { id: 8, display_name: '詹姆士', sort_order: 0, usage_count: 1 },
    ]
    renderAt('/recipes')
    const sidebar = screen.getByRole('complementary', { name: '篩選' })
    fireEvent.click(await within(sidebar).findByRole('button', { name: /詹姆士/ }))
    expect(location()).toBe('/recipes?author=8')
    await waitFor(() => expect(listRequests('/api/recipes')).toContain('/api/recipes?author_id=8'))
  })

  it('shows the status and the authors by name in the table', async () => {
    responses['/api/recipes'] = [RECIPE]
    localStorage.setItem('cg1618:food:recipes-view', 'list')
    renderAt('/recipes')
    const table = await screen.findByRole('table')
    expect(within(table).getByText('想試')).toBeTruthy()
    expect(within(table).getByText('阿基師')).toBeTruthy()
    // The recipe's own name, and its dish beside it.
    expect(within(table).getByText('阿基師版')).toBeTruthy()
    expect(within(table).getByText('炒高麗菜')).toBeTruthy()
  })

  it('marks a recipe that is only a bookmark, and applies the cover focus', async () => {
    responses['/api/recipes'] = [RECIPE]
    renderAt('/recipes')
    expect(await screen.findByText('阿基師版')).toBeTruthy()
    // Its dish's name under its own.
    expect(screen.getByText('炒高麗菜')).toBeTruthy()
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
