// Recipe templates through the real routes: the new-recipe chooser and its
// three ways in (空白, 從範本, 複製另一份食譜), each kept in the URL with the
// preset dish; the form prefilled from a template - and saying what the
// template had that no longer exists - or from another recipe, with that
// recipe's dish but not its name, sources or status; and the template form's
// own save. 存成範本 on a recipe's page is in pages/detail/details.test.jsx;
// the 範本 tab on 設定 in settings.test.jsx.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider } from '../../contexts/ThemeContext'
import AppRoutes from '../../routes'

let calls
let handler

function json(body, status = 200) {
  return new Response(body === null ? null : JSON.stringify(body), { status })
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
const posts = () => calls.filter((call) => call.method === 'POST')

const FIXED = {
  dish_kinds: [
    { value: 'dish', label: '料理' },
    { value: 'sauce', label: '醬料' },
  ],
  step_kinds: [
    { value: 'step', label: '步驟' },
    { value: 'optional', label: '可省略' },
    { value: 'note', label: '備註' },
  ],
}
const STATUSES = [
  { id: 1, display_name: '想試', name_cn: '想試', sort_order: 10, usage_count: 0 },
  { id: 2, display_name: '常煮', name_cn: '常煮', sort_order: 20, usage_count: 0 },
]
const DISHES = {
  40: { id: 40, display_name: '照燒雞腿排', name_cn: '照燒雞腿排', kind: 'dish', recipes: [] },
  41: { id: 41, display_name: '照燒豆腐', name_cn: '照燒豆腐', kind: 'dish', recipes: [] },
}
const TEMPLATES = [
  { id: 11, name: '基本照燒', sort_order: 0, line_count: 2, step_count: 2 },
  { id: 12, name: '燉湯', sort_order: 1, line_count: 0, step_count: 1 },
]
const TEMPLATE = {
  id: 11,
  name: '基本照燒',
  sort_order: 0,
  dropped: 2,
  body: {
    servings: '2 人份',
    time: '30 分鐘',
    lines: [{ ingredient: { id: 1, display_name: '薑', needs_detail: false }, sub_dish: null, amount: '1 片', note: null, is_optional: false }],
    line_groups: [
      {
        group: null,
        name: '醬汁',
        display_name: '醬汁',
        lines: [{ ingredient: null, sub_dish: { id: 7, display_name: '照燒醬', kind: 'sauce' }, amount: '3 匙', note: null, is_optional: false }],
      },
    ],
    steps: [{ body: '煎皮', kind: 'step' }],
    step_groups: [{ group: null, name: '收尾', display_name: '收尾', steps: [{ body: '別燒焦', kind: 'note' }] }],
    methods: [{ id: 3, display_name: '煎' }],
    equipment: [],
  },
}
const SOURCE = {
  id: 5,
  display_name: '阿嬤版',
  name: '阿嬤版',
  dish: { id: 40, display_name: '照燒雞腿排', kind: 'dish', course: null, region: null, labels: [], serves_as: [] },
  status: { id: 2, display_name: '常煮' },
  servings: '4 人份',
  time: null,
  storage_notes: '冷藏三天',
  notes: '醬汁先調',
  sources: [{ id: 1, platform: { id: 1, display_name: 'YouTube' }, author: null, url: 'https://example.com', title: '影片', sort_order: 0 }],
  lines: [{ id: 1, position: 0, ingredient: { id: 1, display_name: '薑', needs_detail: false }, sub_dish: null, amount: '2 片', note: null, is_optional: true }],
  line_groups: [],
  steps: [{ id: 1, position: 0, kind: 'optional', body: '先醃' }],
  step_groups: [],
  methods: [],
  equipment: [{ id: 4, display_name: '平底鍋' }],
  images: [{ image_id: 9, url: '/images/9.jpg', thumb_url: '/images/t9.jpg', focus: null }],
  other_recipes: [],
  written_up: true,
}

function data({ url, method }) {
  if (method !== 'GET') return null
  if (url === '/api/vocabularies/fixed') return json(FIXED)
  if (url === '/api/recipe-statuses') return json(STATUSES)
  const dish = url.match(/^\/api\/dishes\/(\d+)$/)
  if (dish) return json(DISHES[dish[1]])
  if (url === '/api/recipe-templates') return json(TEMPLATES)
  if (url === '/api/recipe-templates/11') return json(TEMPLATE)
  if (url === '/api/recipes/5') return json(SOURCE)
  if (url.startsWith('/api/recipes?q=')) return json([{ id: 5, display_name: '阿嬤版', name: '阿嬤版', dish: SOURCE.dish }])
  if (url.startsWith('/api/ingredients?')) return json([{ id: 1, display_name: '薑', name_cn: '薑', needs_detail: false }])
  return null
}

beforeEach(() => {
  calls = []
  handler = (call) =>
    call.method === 'POST' && call.url === '/api/edit/recipes' ? json({ id: 42, images: [] }, 201) : data(call)
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, options = {}) => {
      const call = {
        url: decodeURIComponent(url),
        method: options.method ?? 'GET',
        body: typeof options.body === 'string' ? JSON.parse(options.body) : undefined,
      }
      calls.push(call)
      return handler(call) ?? json([])
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

async function save() {
  fireEvent.click(await screen.findByRole('button', { name: '儲存' }))
  await waitFor(() => expect(location()).toBe('/recipes/42'))
  return posts().find((call) => call.url === '/api/edit/recipes').body
}

describe('the new-recipe chooser', () => {
  it('asks how to start before any form, naming the dish it came from', async () => {
    renderAt('/edit/recipes/new?dish=40')
    expect(screen.getByRole('heading', { level: 1, name: '新增食譜' })).toBeTruthy()
    for (const name of ['空白', '從範本', '複製另一份食譜']) {
      expect(screen.getByRole('heading', { name })).toBeTruthy()
    }
    expect(await screen.findByText(/這份食譜會放在「照燒雞腿排」底下/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: '儲存' })).toBeNull()
  })

  it('opens the empty form on 空白, keeping the dish in the URL and on the form', async () => {
    renderAt('/edit/recipes/new?dish=40')
    fireEvent.click(screen.getByRole('button', { name: '空白食譜' }))
    expect(location()).toBe('/edit/recipes/new?dish=40&blank=1')
    expect(await screen.findByText('照燒雞腿排')).toBeTruthy()
    const body = await save()
    expect(body.dish_id).toBe(40)
    expect(body.lines).toEqual([])
  })

  it('lists the templates in order and opens the form on the one chosen', async () => {
    renderAt('/edit/recipes/new?dish=41')
    const list = await screen.findByRole('list', { name: '範本' })
    expect(within(list).getAllByRole('button').map((b) => b.textContent)).toEqual([
      '基本照燒材料 2 · 步驟 2',
      '燉湯材料 0 · 步驟 1',
    ])
    fireEvent.click(within(list).getByRole('button', { name: /基本照燒/ }))
    expect(location()).toBe('/edit/recipes/new?dish=41&template=11')
    expect(await screen.findByText('從範本「基本照燒」開始。')).toBeTruthy()
  })

  it('says where templates come from when there are none', async () => {
    handler = (call) => (call.url === '/api/recipe-templates' ? json([]) : data(call))
    renderAt('/edit/recipes/new')
    expect(await screen.findByText(/還沒有範本/)).toBeTruthy()
    expect(screen.getByRole('link', { name: '到設定管理範本' }).getAttribute('href')).toBe('/edit/settings?tab=templates')
  })

  it('finds a recipe to copy by searching the recipe library', async () => {
    renderAt('/edit/recipes/new')
    fireEvent.change(screen.getByRole('combobox', { name: '要複製的食譜' }), { target: { value: '阿嬤' } })
    const option = await screen.findByRole('option', { name: /阿嬤版/ })
    expect(option.textContent).toContain('照燒雞腿排')
    fireEvent.click(option)
    expect(location()).toBe('/edit/recipes/new?from=5')
    expect(await screen.findByRole('link', { name: '阿嬤版' })).toBeTruthy()
  })
})

describe('a new recipe from a template', () => {
  it('fills the structure, says what was dropped, and saves it as a new recipe', async () => {
    renderAt('/edit/recipes/new?dish=41&template=11')
    expect(await screen.findByText('範本裡有 2 個項目已不存在，已略過。')).toBeTruthy()
    expect(screen.getByPlaceholderText('例如 2 人份').value).toBe('2 人份')
    expect(screen.getByLabelText('時間').value).toBe('30 分鐘')
    expect(screen.getByRole('textbox', { name: '步驟 2' }).value).toBe('別燒焦')
    // The template has no dish: the dish is ?dish='s.
    expect(screen.getByText('照燒豆腐')).toBeTruthy()

    const body = await save()
    expect(body.dish_id).toBe(41)
    expect(body.servings).toBe('2 人份')
    expect(body.lines).toEqual([{ ingredient_id: 1, amount: '1 片', note: null, is_optional: false }])
    expect(body.line_groups).toEqual([
      { name: '醬汁', lines: [{ sub_dish_id: 7, amount: '3 匙', note: null, is_optional: false }] },
    ])
    expect(body.steps).toEqual([{ body: '煎皮', kind: 'step' }])
    expect(body.step_groups).toEqual([{ name: '收尾', steps: [{ body: '別燒焦', kind: 'note' }] }])
    expect(body.method_ids).toEqual([3])
    expect(body.equipment_ids).toEqual([])
    // Nothing was written before 儲存, and nothing but the recipe after.
    expect(calls.filter((c) => c.method !== 'GET').map((c) => `${c.method} ${c.url}`)).toEqual([
      'POST /api/edit/recipes',
    ])
  })

  it('says nothing about dropped items when nothing was', async () => {
    handler = (call) =>
      call.url === '/api/recipe-templates/11' ? json({ ...TEMPLATE, dropped: 0 }) : data(call)
    renderAt('/edit/recipes/new?template=11')
    expect(await screen.findByText('從範本「基本照燒」開始。')).toBeTruthy()
    expect(screen.queryByText(/已不存在/)).toBeNull()
  })

  it('offers to choose again when the template cannot be read', async () => {
    handler = (call) =>
      call.url === '/api/recipe-templates/11' ? json({ detail: 'No such template.' }, 404) : data(call)
    renderAt('/edit/recipes/new?dish=40&template=11')
    expect((await screen.findByRole('alert')).textContent).toMatch(/讀不到這個範本/)
    expect(screen.getByRole('link', { name: '重新選擇' }).getAttribute('href')).toBe('/edit/recipes/new?dish=40')
    expect(screen.queryByRole('button', { name: '儲存' })).toBeNull()
  })
})

describe('a new recipe copied from another', () => {
  it("copies the structure and notes under the source's dish, not its name, sources, status or pictures", async () => {
    renderAt('/edit/recipes/new?from=5')
    expect(await screen.findByText(/名稱、來源、狀態和圖片沒有複製/)).toBeTruthy()
    expect(screen.getByRole('link', { name: '阿嬤版' }).getAttribute('href')).toBe('/recipes/5')
    expect(screen.getByLabelText(/^名稱/).value).toBe('')

    const body = await save()
    expect(body.dish_id).toBe(40)
    expect(body.name).toBeNull()
    expect(body.sources).toEqual([])
    // The first status, as any new recipe - not the source's 常煮.
    expect(body.status_id).toBe(1)
    expect(body.servings).toBe('4 人份')
    expect(body.storage_notes).toBe('冷藏三天')
    expect(body.notes).toBe('醬汁先調')
    expect(body.lines).toEqual([{ ingredient_id: 1, amount: '2 片', note: null, is_optional: true }])
    expect(body.steps).toEqual([{ body: '先醃', kind: 'optional' }])
    expect(body.equipment_ids).toEqual([4])
    // No gallery PUT: the pictures stayed with the source.
    expect(calls.filter((c) => c.method === 'PUT')).toEqual([])
  })

  it('keeps the dish ?dish= names over the source recipe’s', async () => {
    renderAt('/edit/recipes/new?dish=41&from=5')
    expect(await screen.findByText(/名稱、來源、狀態和圖片沒有複製/)).toBeTruthy()
    const body = await save()
    expect(body.dish_id).toBe(41)
  })
})

describe('the template form', () => {
  it('saves a new template, offering only what is already in the libraries', async () => {
    handler = (call) =>
      call.method === 'POST' ? json({ id: 13, name: call.body.name }, 201) : data(call)
    renderAt('/edit/templates/new')
    expect(screen.getByRole('heading', { level: 1, name: '新增範本' })).toBeTruthy()
    fireEvent.change(screen.getByLabelText('名稱'), { target: { value: ' 快炒 ' } })
    fireEvent.change(screen.getByPlaceholderText('例如 2 人份'), { target: { value: '2 人份' } })

    fireEvent.click(screen.getByRole('button', { name: /加一行材料/ }))
    fireEvent.change(screen.getByRole('combobox', { name: '材料 1' }), { target: { value: '薑末' } })
    const option = await screen.findByRole('option', { name: /^薑/ })
    expect(screen.queryByRole('option', { name: /新增/ })).toBeNull()
    fireEvent.click(option)

    fireEvent.click(screen.getByRole('button', { name: /加一個步驟/ }))
    fireEvent.change(screen.getByRole('textbox', { name: '步驟 1' }), { target: { value: '大火' } })

    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(location()).toBe('/edit/settings?tab=templates'))
    expect(posts()).toEqual([
      {
        url: '/api/edit/recipe-templates',
        method: 'POST',
        body: {
          name: '快炒',
          body: {
            servings: '2 人份',
            time: null,
            lines: [{ ingredient_id: 1, amount: null, note: null, is_optional: false }],
            line_groups: [],
            steps: [{ body: '大火', kind: 'step' }],
            step_groups: [],
            method_ids: [],
            equipment_ids: [],
          },
        },
      },
    ])
  })

  it('refuses to save without a name', async () => {
    renderAt('/edit/templates/new')
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    expect((await screen.findByRole('alert')).textContent).toBe('範本要有名稱。')
    expect(posts()).toEqual([])
  })

  it('loads a saved template, says what was dropped, and sends it back whole', async () => {
    handler = (call) => (call.method === 'PATCH' ? json(TEMPLATE) : data(call))
    renderAt('/edit/templates/11')
    expect(await screen.findByText(/範本裡有 2 個項目已不存在/)).toBeTruthy()
    expect(screen.getByLabelText('名稱').value).toBe('基本照燒')
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(location()).toBe('/edit/settings?tab=templates'))
    const patch = calls.find((c) => c.method === 'PATCH')
    expect(patch.url).toBe('/api/edit/recipe-templates/11')
    expect(patch.body.name).toBe('基本照燒')
    expect(patch.body.body.line_groups).toEqual([
      { name: '醬汁', lines: [{ sub_dish_id: 7, amount: '3 匙', note: null, is_optional: false }] },
    ])
    expect(patch.body.body.step_groups).toEqual([{ name: '收尾', steps: [{ body: '別燒焦', kind: 'note' }] }])
  })
})
