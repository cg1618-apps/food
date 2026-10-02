// The three detail pages through the real routes: what each shows, what it
// leaves out when empty, the recipe's in-place status change, and the
// ingredient merge including the stale-preview 409.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AppRoutes from '../../routes'

const FIXED = {
  preservation_methods: ['常溫', '冷藏', '冷凍'].map((m) => ({ value: m, label: m })),
  preservation_states: [
    { value: 'unused', label: '未使用' },
    { value: 'opened', label: '已開封' },
    { value: 'cooked', label: '熟食' },
  ],
  ratings: [],
  recipe_kinds: [
    { value: 'dish', label: '料理' },
    { value: 'base', label: '基底' },
  ],
  recipe_statuses: [
    { value: 'want_to_try', label: '想試' },
    { value: 'can_cook', label: '可煮' },
    { value: 'regular', label: '常煮' },
  ],
  source_platforms: [{ value: 'youtube', label: 'YouTube' }],
  kitchen_note_kinds: [{ value: 'technique', label: '技巧' }],
}

const RECIPE = {
  id: 5,
  display_name: '麻婆豆腐',
  name_cn: '麻婆豆腐',
  name_en: 'Mapo tofu',
  kind: 'dish',
  status: 'want_to_try',
  course: { id: 1, display_name: '主菜' },
  servings: '2 人',
  time: '20 分鐘',
  description: null,
  storage_notes: null,
  notes: '花椒最後下',
  aliases: [],
  sources: [],
  lines: [
    { id: 1, position: 0, section: null, ingredient: { id: 10, display_name: '豆腐', needs_detail: false }, sub_recipe: null, amount: '1 盒', note: null, is_optional: false },
    { id: 2, position: 1, section: '醬汁', ingredient: null, sub_recipe: { id: 7, display_name: '辣油', kind: 'base' }, amount: '2 匙', note: null, is_optional: false },
    { id: 3, position: 2, section: '醬汁', ingredient: { id: 11, display_name: '花椒粉', needs_detail: true }, sub_recipe: null, amount: null, note: '現磨', is_optional: true },
  ],
  steps: [
    { id: 1, position: 0, section: '醬汁', body: '炒香辣油' },
    { id: 2, position: 1, section: null, body: '下豆腐' },
  ],
  serves_as: [],
  labels: [],
  methods: [{ id: 3, display_name: '炒' }],
  equipment: [],
  images: [],
  variant_of: { id: 4, display_name: '麻婆豆腐（原版）', kind: 'dish' },
  versions: [],
  used_in: [],
  written_up: true,
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
  used_in: [{ id: 5, display_name: '麻婆豆腐', kind: 'dish' }],
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
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
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

  it('groups lines and steps by section and marks optional and stub lines', async () => {
    renderAt('/recipes/5')
    expect(await screen.findByRole('heading', { level: 1, name: '麻婆豆腐' })).toBeTruthy()

    const lines = screen.getByRole('heading', { name: '材料' }).closest('section')
    expect(within(lines).getByRole('heading', { level: 3, name: '醬汁' })).toBeTruthy()
    expect(within(lines).getByRole('link', { name: '辣油' }).getAttribute('href')).toBe('/recipes/7')
    const optional = within(lines).getByText('（可省略）').closest('li')
    expect(optional.className).toContain('text-text-faint')
    expect(within(optional).getByText('待補')).toBeTruthy()

    const steps = screen.getByRole('heading', { name: '步驟' }).closest('section')
    expect(within(steps).getAllByRole('listitem').map((li) => li.textContent)).toEqual([
      '1第 1 步：炒香辣油',
      '2第 2 步：下豆腐',
    ])
  })

  it('shows the original as another version and hides empty sections', async () => {
    renderAt('/recipes/5')
    const versions = (await screen.findByRole('heading', { name: '其他版本' })).closest('section')
    expect(within(versions).getByRole('link').getAttribute('href')).toBe('/recipes/4')
    expect(within(versions).getByText('原版')).toBeTruthy()
    expect(screen.queryByRole('heading', { name: '來源' })).toBeNull()
    expect(screen.queryByRole('heading', { name: '用在' })).toBeNull()
  })

  it('changes the status in place with a PATCH of status alone', async () => {
    renderAt('/recipes/5')
    const group = await screen.findByRole('group', { name: '狀態' })
    fireEvent.click(await within(group).findByRole('button', { name: '常煮' }))
    await waitFor(() =>
      expect(calls.find((c) => c.method === 'PATCH')).toEqual({
        url: '/api/edit/recipes/5',
        method: 'PATCH',
        body: { status: 'regular' },
      }),
    )
  })

  // The PATCH answers with the saved recipe, and that is what the page shows -
  // not the old status again when the refetch after it fails.
  it('shows the saved status even when the refetch after it fails', async () => {
    let reads = 0
    handler = ({ url, method }) => {
      if (method === 'PATCH') return json({ ...RECIPE, status: 'regular' })
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
