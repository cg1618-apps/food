// The four detail pages through the real routes: what each shows, what it
// leaves out when empty, the recipe's in-place status change, the dish's
// recipes and "used in", and the ingredient merge including the
// stale-preview 409.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider } from '../../contexts/ThemeContext'
import AppRoutes from '../../routes'

const FIXED = {
  preservation_methods: ['常溫', '冷藏', '冷凍'].map((m) => ({ value: m, label: m })),
  preservation_states: [
    { value: 'unused', label: '未使用' },
    { value: 'opened', label: '已開封' },
    { value: 'cooked', label: '熟食' },
  ],
  ratings: [],
  dish_kinds: [
    { value: 'dish', label: '料理' },
    { value: 'sauce', label: '醬料' },
  ],
  kitchen_note_kinds: [{ value: 'technique', label: '技巧' }],
  step_kinds: [
    { value: 'step', label: '步驟' },
    { value: 'optional', label: '可省略' },
    { value: 'note', label: '備註' },
  ],
}

const STATUSES = [
  { id: 1, display_name: '想試', name_cn: '想試', name_en: null, sort_order: 10, usage_count: 1 },
  { id: 2, display_name: '可煮', name_cn: '可煮', name_en: null, sort_order: 20, usage_count: 0 },
  { id: 3, display_name: '常煮', name_cn: '常煮', name_en: null, sort_order: 30, usage_count: 0 },
]

const RECIPE = {
  id: 5,
  display_name: '麻婆豆腐',
  name: null,
  dish: {
    id: 40,
    display_name: '麻婆豆腐',
    kind: 'dish',
    course: { id: 1, display_name: '主菜' },
    region: { id: 2, display_name: '中式' },
    labels: [{ id: 9, display_name: '下飯' }],
    serves_as: [],
  },
  status: { id: 1, display_name: '想試' },
  servings: '2 人',
  time: '20 分鐘',
  storage_notes: null,
  notes: '花椒最後下',
  sources: [],
  lines: [
    { id: 1, position: 0, ingredient: { id: 10, display_name: '豆腐', needs_detail: false }, sub_dish: null, amount: '1 盒', note: null, is_optional: false },
  ],
  line_groups: [
    {
      id: 8,
      position: 0,
      group: null,
      name: '醬汁',
      display_name: '醬汁',
      lines: [
        { id: 2, position: 1, ingredient: null, sub_dish: { id: 7, display_name: '辣油', kind: 'sauce' }, amount: '2 匙', note: null, is_optional: false },
        { id: 3, position: 2, ingredient: { id: 11, display_name: '花椒粉', needs_detail: true }, sub_dish: null, amount: null, note: '現磨', is_optional: true },
      ],
    },
    // Empty: kept by the server, nothing to read here.
    { id: 9, position: 1, group: { id: 2, display_name: '配料' }, name: null, display_name: '配料', lines: [] },
  ],
  steps: [{ id: 1, position: 0, body: '看一遍' }],
  step_groups: [
    { id: 4, position: 0, group: { id: 1, display_name: '備料' }, name: null, display_name: '備料', steps: [{ id: 2, position: 1, body: '切豆腐' }] },
    { id: 5, position: 1, group: null, name: '炒', display_name: '炒', steps: [{ id: 3, position: 2, body: '炒香辣油' }, { id: 4, position: 3, body: '下豆腐' }] },
  ],
  methods: [{ id: 3, display_name: '炒' }],
  equipment: [],
  images: [],
  other_recipes: [{ id: 4, display_name: '麻婆豆腐（陳家）', dish: { id: 40, display_name: '麻婆豆腐', kind: 'dish' } }],
  written_up: true,
}

const DISH = {
  id: 40,
  display_name: '麻婆豆腐',
  name_cn: '麻婆豆腐',
  name_en: 'Mapo tofu',
  name_alt: null,
  kind: 'dish',
  course: { id: 1, display_name: '主菜' },
  region: { id: 2, display_name: '中式' },
  description: '下飯的川菜',
  aliases: [],
  serves_as: [],
  labels: [{ id: 9, display_name: '下飯' }],
  images: [],
  recipes: [
    {
      id: 5,
      display_name: '麻婆豆腐',
      name: null,
      dish: { id: 40, display_name: '麻婆豆腐', kind: 'dish' },
      status: { id: 1, display_name: '想試' },
      course: { id: 1, display_name: '主菜' },
      methods: [],
      authors: [{ id: 6, display_name: '阿基師' }],
      time: null,
      written_up: true,
      cover: null,
    },
    {
      id: 4,
      display_name: '麻婆豆腐（陳家）',
      name: '麻婆豆腐（陳家）',
      dish: { id: 40, display_name: '麻婆豆腐', kind: 'dish' },
      status: { id: 2, display_name: '可煮' },
      course: { id: 1, display_name: '主菜' },
      methods: [],
      authors: [],
      time: null,
      written_up: false,
      cover: { thumb_url: '/images/c.jpg', focus: null },
    },
  ],
  used_in: [],
}

const SAUCE = {
  ...DISH,
  id: 7,
  display_name: '辣油',
  name_cn: '辣油',
  name_en: null,
  kind: 'sauce',
  course: null,
  region: null,
  description: null,
  labels: [],
  recipes: [],
  used_in: [{ id: 5, display_name: '麻婆豆腐', dish: { id: 40, display_name: '麻婆豆腐', kind: 'dish' } }],
}

const PRESERVATION = (state, method, min, max, notes = null) => ({
  state,
  method,
  duration_min_days: min,
  duration_max_days: max,
  notes,
  sort_order: 0,
})

const INGREDIENT = {
  id: 20,
  display_name: '青蔥',
  name_cn: '青蔥',
  name_en: 'Scallion',
  name_alt: null,
  category: { id: 2, display_name: '蔬菜' },
  parent: null,
  children: [
    { id: 21, display_name: '三星蔥', rating: 'S', needs_detail: false, sourcing_notes: '宜蘭', used_in_count: 0 },
  ],
  description: null,
  selection_notes: '蔥白要長',
  sourcing_notes: null,
  preservation_notes: null,
  needs_detail: true,
  rating: null,
  aliases: ['蔥'],
  preservation: [PRESERVATION('unused', '冷藏', 7, 10, '報紙包'), PRESERVATION('cooked', '冷凍', 30, 30)],
  heating: [
    { id: 1, method: { id: 4, display_name: '氣炸' }, temperature_c: 180, temperature_f: 356, duration: '5 分', preheat: true, flip: false, notes: null, sort_order: 0 },
  ],
  links: [],
  labels: [],
  images: [],
  used_in: [{ id: 5, display_name: '麻婆豆腐', dish: { id: 40, display_name: '麻婆豆腐', kind: 'dish' } }],
}

const LEEK = { id: 30, display_name: '大蔥', category_id: 2, parent_id: null, needs_detail: false }

const PREVIEW = (lines) => ({
  source: { ...INGREDIENT, category_id: 2 },
  target: LEEK,
  moves: { lines, children: 1, links: 0, labels: 0, images: 0, heating: 1, preservation: 1 },
  new_aliases: ['青蔥', 'Scallion'],
  dropped_preservation: [{ state: 'unused', method: '冷藏' }],
  prose: { selection_notes: 'dropped' },
  fingerprint: `fp-${lines}`,
})

let calls
let handler

function json(body, status = 200) {
  return new Response(JSON.stringify(body), { status })
}

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

beforeEach(() => {
  calls = []
  handler = () => null
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, options = {}) => {
      const call = {
        url: decodeURIComponent(url),
        method: options.method ?? 'GET',
        body: typeof options.body === 'string' ? JSON.parse(options.body) : undefined,
      }
      calls.push(call)
      if (call.url === '/api/vocabularies/fixed') return json(FIXED)
      if (call.url === '/api/recipe-statuses') return json(STATUSES)
      return handler(call) ?? json([])
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

describe('the recipe page', () => {
  beforeEach(() => {
    handler = ({ url, method }) => (method === 'GET' && url === '/api/recipes/5' ? json(RECIPE) : null)
  })

  it('shows lines and steps in their groups and marks optional and stub lines', async () => {
    renderAt('/recipes/5')
    expect(await screen.findByRole('heading', { level: 1, name: '麻婆豆腐' })).toBeTruthy()

    const lines = screen.getByRole('heading', { name: '材料' }).closest('section')
    // Ungrouped first, without a heading; then each group under its name; an
    // empty group is left out.
    expect(within(lines).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['醬汁'])
    expect(within(lines).getAllByRole('listitem').map((li) => li.textContent.slice(0, 2))).toEqual([
      '豆腐',
      '辣油',
      '花椒',
    ])
    // A line names the dish, so it links to the dish.
    expect(within(lines).getByRole('link', { name: '辣油' }).getAttribute('href')).toBe('/dishes/7')
    const optional = within(lines).getByText('（可省略）').closest('li')
    expect(optional.className).toContain('text-text-faint')
    expect(within(optional).getByText('待補')).toBeTruthy()

    const steps = screen.getByRole('heading', { name: '步驟' }).closest('section')
    expect(within(steps).getAllByRole('heading', { level: 3 }).map((h) => h.textContent)).toEqual(['備料', '炒'])
    // Numbered through every group.
    expect(within(steps).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      '1第 1 步：看一遍',
      '2第 2 步：切豆腐',
      '3第 3 步：炒香辣油',
      '4第 4 步：下豆腐',
    ])
  })

  it('numbers only ordinary steps, marks an optional step and draws a note as a callout', async () => {
    const recipe = {
      ...RECIPE,
      steps: [
        { id: 1, position: 0, kind: 'step', body: '看一遍' },
        { id: 2, position: 1, kind: 'note', body: '豆腐先泡鹽水' },
      ],
      step_groups: [
        {
          ...RECIPE.step_groups[0],
          steps: [
            { id: 3, position: 2, kind: 'optional', body: '撒蔥花' },
            { id: 4, position: 3, kind: 'step', body: '切豆腐' },
          ],
        },
      ],
    }
    handler = ({ url, method }) => (method === 'GET' && url === '/api/recipes/5' ? json(recipe) : null)
    renderAt('/recipes/5')
    expect(await screen.findByRole('heading', { level: 1, name: '麻婆豆腐' })).toBeTruthy()

    const steps = screen.getByRole('heading', { name: '步驟' }).closest('section')
    expect(within(steps).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      '1第 1 步：看一遍',
      '備註豆腐先泡鹽水',
      '可省略撒蔥花',
      '2第 2 步：切豆腐',
    ])
    const note = within(steps).getByText('豆腐先泡鹽水').closest('li')
    expect(note.className).toContain('border-l-4')
    expect(note.className).toContain('bg-surface-2')
    const optional = within(steps).getByText('撒蔥花')
    expect(optional.className).toContain('text-text-muted')
  })

  it('shows its dish, the dish’s other recipes as 其他版本, and hides empty sections', async () => {
    renderAt('/recipes/5')
    expect(await screen.findByRole('heading', { level: 1, name: '麻婆豆腐' })).toBeTruthy()
    // The dish, a link, with what it says shown read-only.
    const dishLinks = screen.getAllByRole('link', { name: '麻婆豆腐' })
    expect(dishLinks.map((link) => link.getAttribute('href'))).toContain('/dishes/40')
    expect(screen.getByText('中式')).toBeTruthy()
    expect(screen.getByRole('link', { name: '下飯' }).getAttribute('href')).toBe('/recipes?label=9')
    const versions = screen.getByRole('heading', { name: '其他版本' }).closest('section')
    expect(within(versions).getByRole('link', { name: '麻婆豆腐（陳家）' }).getAttribute('href')).toBe('/recipes/4')
    expect(screen.queryByRole('heading', { name: '來源' })).toBeNull()
    expect(screen.queryByRole('heading', { name: '用在' })).toBeNull()
  })

  it('shows its own name over the dish’s, and no 其他版本 when it is the only recipe', async () => {
    handler = ({ url, method }) =>
      method === 'GET' && url === '/api/recipes/5'
        ? json({ ...RECIPE, name: '阿基師版', display_name: '阿基師版', other_recipes: [] })
        : null
    renderAt('/recipes/5')
    expect(await screen.findByRole('heading', { level: 1, name: '阿基師版' })).toBeTruthy()
    expect(screen.getByRole('link', { name: '麻婆豆腐' }).getAttribute('href')).toBe('/dishes/40')
    expect(screen.queryByRole('heading', { name: '其他版本' })).toBeNull()
  })

  it('names each source by its platform, and links its author to the library filter', async () => {
    handler = ({ url, method }) =>
      method === 'GET' && url === '/api/recipes/5'
        ? json({
            ...RECIPE,
            sources: [
              {
                id: 1,
                platform: { id: 4, display_name: '書' },
                author: { id: 6, display_name: '阿基師' },
                url: null,
                title: '家常菜',
                sort_order: 0,
              },
            ],
          })
        : null
    renderAt('/recipes/5')
    const sources = (await screen.findByRole('heading', { name: '來源' })).closest('section')
    expect(within(sources).getByText('書')).toBeTruthy()
    expect(within(sources).getByRole('link', { name: '阿基師' }).getAttribute('href')).toBe('/recipes?author=6')
    expect(within(sources).getByText('家常菜')).toBeTruthy()
  })

  it('saves itself as a template under the name asked for, then links to it', async () => {
    handler = ({ url, method, body }) => {
      if (method === 'GET' && url === '/api/recipes/5') return json(RECIPE)
      if (method === 'POST' && body.name === '麻婆豆腐') {
        return json({ detail: 'Another template already has that name.' }, 422)
      }
      if (method === 'POST') return json({ id: 21, name: body.name, sort_order: 0, body: {}, dropped: 0 }, 201)
      return null
    }
    renderAt('/recipes/5')
    fireEvent.click(await screen.findByRole('button', { name: '存成範本' }))
    const dialog = screen.getByRole('dialog', { name: '存成範本' })
    // The recipe's name to start with; a name another template has is
    // refused, said, and the dialog stays.
    const box = within(dialog).getByRole('textbox', { name: '範本名稱' })
    expect(box.value).toBe('麻婆豆腐')
    fireEvent.click(within(dialog).getByRole('button', { name: '存成範本' }))
    expect((await within(dialog).findByRole('alert')).textContent).toBe('Another template already has that name.')

    fireEvent.change(box, { target: { value: '麻婆系' } })
    fireEvent.click(within(dialog).getByRole('button', { name: '存成範本' }))
    const link = await within(dialog).findByRole('link', { name: '麻婆系' })
    expect(link.getAttribute('href')).toBe('/edit/templates/21')
    expect(within(dialog).getByRole('link', { name: '開啟範本' }).getAttribute('href')).toBe('/edit/templates/21')
    expect(calls.filter((c) => c.method === 'POST')).toEqual([
      { url: '/api/edit/recipe-templates/from-recipe/5', method: 'POST', body: { name: '麻婆豆腐' } },
      { url: '/api/edit/recipe-templates/from-recipe/5', method: 'POST', body: { name: '麻婆系' } },
    ])
  })

  it('changes the status in place with a PATCH of status alone', async () => {
    renderAt('/recipes/5')
    const group = await screen.findByRole('group', { name: '狀態' })
    fireEvent.click(await within(group).findByRole('button', { name: '常煮' }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'PATCH')).toEqual({
        url: '/api/edit/recipes/5',
        method: 'PATCH',
        body: { status_id: 3 },
      }),
    )
  })

  // The PATCH answers with the saved recipe, and that is what the page shows -
  // not the old status again when the refetch after it fails.
  it('shows the saved status even when the refetch after it fails', async () => {
    let reads = 0
    handler = ({ url, method }) => {
      if (method === 'PATCH') return json({ ...RECIPE, status: { id: 3, display_name: '常煮' } })
      if (url === '/api/recipes/5') {
        reads += 1
        return reads === 1 ? json(RECIPE) : json({ detail: 'down' }, 500)
      }
      return null
    }
    renderAt('/recipes/5')
    const group = await screen.findByRole('group', { name: '狀態' })
    fireEvent.click(await within(group).findByRole('button', { name: '常煮' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH')).toBe(true))
    await waitFor(() => expect(reads).toBe(2))
    expect(within(group).getByRole('button', { name: '常煮' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('says so, and shows the stored status again, when the change fails', async () => {
    handler = ({ url, method }) => {
      if (method === 'PATCH') return json({ detail: '壞掉了' }, 500)
      return url === '/api/recipes/5' ? json(RECIPE) : null
    }
    renderAt('/recipes/5')
    const group = await screen.findByRole('group', { name: '狀態' })
    fireEvent.click(await within(group).findByRole('button', { name: '常煮' }))
    expect((await screen.findByRole('alert')).textContent).toContain('狀態沒有改成')
    expect(within(group).getByRole('button', { name: '想試' }).getAttribute('aria-pressed')).toBe('true')
  })

  it('says a missing recipe is missing', async () => {
    handler = () => json({ detail: 'Recipe not found' }, 404)
    renderAt('/recipes/99')
    expect(await screen.findByText('找不到這道食譜。')).toBeTruthy()
  })
})

describe('the dish page', () => {
  beforeEach(() => {
    handler = ({ url, method }) => {
      if (method !== 'GET') return null
      if (url === '/api/dishes/40') return json(DISH)
      if (url === '/api/dishes/7') return json(SAUCE)
      return null
    }
  })

  it('shows what the dish is and lists its recipes, with an add that presets the dish', async () => {
    renderAt('/dishes/40')
    expect(await screen.findByRole('heading', { level: 1, name: '麻婆豆腐' })).toBeTruthy()
    expect(screen.getByText('Mapo tofu')).toBeTruthy()
    expect(screen.getByRole('link', { name: '主菜' }).getAttribute('href')).toBe('/dishes?course=1')
    expect(screen.getByRole('link', { name: '中式' }).getAttribute('href')).toBe('/dishes?region=2')
    expect(screen.getByRole('link', { name: '下飯' }).getAttribute('href')).toBe('/dishes?label=9')
    expect(screen.getByText('下飯的川菜')).toBeTruthy()

    const recipes = screen.getByRole('heading', { name: '食譜' }).closest('section')
    const links = within(recipes).getAllByRole('link')
    expect(links.map((link) => link.getAttribute('href'))).toEqual([
      '/edit/recipes/new?dish=40',
      '/recipes/5',
      '/recipes/4',
    ])
    expect(links[1].textContent).toContain('阿基師 · 想試')
    expect(within(links[2]).getByText('書籤')).toBeTruthy()
    expect(screen.queryByRole('heading', { name: '用在' })).toBeNull()
    expect(screen.getByRole('link', { name: '編輯' }).getAttribute('href')).toBe('/edit/dishes/40')
  })

  it('shows a sauce, and the recipes that use it', async () => {
    renderAt('/dishes/7')
    expect(await screen.findByRole('heading', { level: 1, name: '辣油' })).toBeTruthy()
    expect(screen.getByText('醬料')).toBeTruthy()
    expect(screen.getByText('還沒有食譜。')).toBeTruthy()
    const usedIn = screen.getByRole('heading', { name: '用在' }).closest('section')
    expect(within(usedIn).getByRole('link', { name: '麻婆豆腐' }).getAttribute('href')).toBe('/recipes/5')
  })

  it('lists the recipes, the recipes using it and its meals when a delete is refused', async () => {
    handler = ({ url, method }) => {
      if (method === 'GET' && url === '/api/dishes/40') return json(DISH)
      if (method === 'GET' && url === '/api/dishes/40/cascade') {
        return json({ aliases: 0, recipes: 2, used_in: 1, meals: 2 })
      }
      if (method === 'DELETE') {
        return json(
          {
            detail: 'This dish still has recipes, recipes use it, or the schedule names it, so it cannot be removed.',
            recipes: [{ id: 5, display_name: '麻婆豆腐' }],
            used_in: [{ id: 8, display_name: '燴飯' }],
            meals: ['2026-10-05', '2026-10-13'],
          },
          409,
        )
      }
      return null
    }
    renderAt('/dishes/40')
    fireEvent.click(await screen.findByRole('button', { name: '刪除' }))
    const dialog = await screen.findByRole('dialog')
    // Said up front, from the counts.
    expect(await within(dialog).findByText(/底下還有 2 份食譜/)).toBeTruthy()
    expect(within(dialog).getByText(/有 1 份食譜把它當材料用/)).toBeTruthy()
    expect(within(dialog).getByText(/排程裡排了它 2 次/)).toBeTruthy()
    fireEvent.click(within(dialog).getByRole('button', { name: '刪除' }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'DELETE').url).toBe('/api/edit/dishes/40?aliases=0'),
    )
    expect(await within(dialog).findByText('它的食譜：')).toBeTruthy()
    expect(within(dialog).getByRole('link', { name: '燴飯' }).getAttribute('href')).toBe('/recipes/8')
    // Each date links to its week, by that week's Saturday.
    expect(within(dialog).getByRole('link', { name: '10/5' }).getAttribute('href')).toBe('/schedule?week=2026-10-03')
    expect(within(dialog).getByRole('link', { name: '10/13' }).getAttribute('href')).toBe('/schedule?week=2026-10-10')
    expect(location()).toBe('/dishes/40')
  })
})

describe('the ingredient page', () => {
  beforeEach(() => {
    handler = ({ url, method }) => (method === 'GET' && url === '/api/ingredients/20' ? json(INGREDIENT) : null)
  })

  it('draws storage as a state by method grid with only what is used', async () => {
    renderAt('/ingredients/20')
    const table = (await screen.findByRole('heading', { name: '保存' })).closest('section').querySelector('table')
    const headers = within(table).getAllByRole('columnheader').map((th) => th.textContent)
    expect(headers).toEqual(['狀態', '冷藏', '冷凍'])
    const rows = within(table).getAllByRole('row').slice(1)
    expect(rows.map((row) => within(row).getByRole('rowheader').textContent)).toEqual(['未使用', '熟食'])
    expect(rows[0].textContent).toContain('7–10 天報紙包')
    expect(rows[1].textContent).toContain('30 天')
  })

  it('shows varieties with where they are bought, heating in both scales, and the stub note', async () => {
    renderAt('/ingredients/20')
    const varieties = (await screen.findByRole('heading', { name: '品種' })).closest('section')
    expect(varieties.textContent).toContain('三星蔥')
    expect(varieties.textContent).toContain('宜蘭')
    expect(screen.getByText(/180°C \/ 356°F/)).toBeTruthy()
    expect(screen.getByRole('link', { name: '去補上' }).getAttribute('href')).toBe('/edit/ingredients/20')
    expect(screen.getByRole('link', { name: '蔬菜' }).getAttribute('href')).toBe('/ingredients?category=2')
    expect(screen.queryByRole('heading', { name: '說明' })).toBeNull()
  })

  it('merges with the preview’s fingerprint, re-asks on a stale preview, then goes to the target', async () => {
    let merges = 0
    handler = ({ url, method }) => {
      if (method === 'GET' && url === '/api/ingredients/20') return json(INGREDIENT)
      if (method === 'GET' && url === '/api/ingredients?q=大') return json([LEEK])
      if (method === 'GET' && url === '/api/ingredients/20/merge-preview?into=30') return json(PREVIEW(2))
      if (method === 'POST' && url === '/api/edit/ingredients/20/merge') {
        merges += 1
        if (merges === 1) return json({ detail: 'changed', preview: PREVIEW(3) }, 409)
        return json({ ...INGREDIENT, id: 30, display_name: '大蔥' })
      }
      if (method === 'GET' && url === '/api/ingredients/30') return json({ ...INGREDIENT, id: 30, display_name: '大蔥' })
      return null
    }
    renderAt('/ingredients/20')
    fireEvent.click(await screen.findByRole('button', { name: '合併到…' }))
    const dialog = screen.getByRole('dialog')
    fireEvent.change(within(dialog).getByRole('combobox'), { target: { value: '大' } })
    fireEvent.click(await within(dialog).findByRole('option', { name: /大蔥/ }))

    expect(await within(dialog).findByText(/成為別名：青蔥、Scallion/)).toBeTruthy()
    expect(dialog.textContent).toContain('保存 未使用 · 冷藏')
    expect(dialog.textContent).toContain('筆記 挑選')
    expect(dialog.textContent).toMatch(/2\s*行食譜材料/)

    fireEvent.click(within(dialog).getByRole('button', { name: '合併' }))
    expect(await within(dialog).findByText(/有人改過/)).toBeTruthy()
    expect(dialog.textContent).toMatch(/3\s*行食譜材料/)
    fireEvent.click(within(dialog).getByRole('button', { name: '確認合併' }))

    await waitFor(() => expect(location()).toBe('/ingredients/30'))
    expect(calls.filter((c) => c.method === 'POST').map((c) => c.body)).toEqual([
      { into: 30, fingerprint: 'fp-2' },
      { into: 30, fingerprint: 'fp-3' },
    ])
  })
})

describe('the note page', () => {
  it('shows the title, kind, the link by its host, and the body', async () => {
    handler = ({ url }) =>
      url === '/api/kitchen-notes/3'
        ? json({ id: 3, title: '切洋蔥', kind: 'technique', url: 'https://www.example.com/a', body: '先對半切', labels: [], images: [] })
        : null
    renderAt('/notes/3')
    expect(await screen.findByRole('heading', { level: 1, name: '切洋蔥' })).toBeTruthy()
    expect(await screen.findByText('技巧')).toBeTruthy()
    expect(screen.getByRole('link', { name: /example\.com/ }).getAttribute('href')).toBe('https://www.example.com/a')
    expect(screen.getByText('先對半切')).toBeTruthy()
  })
})
