// 設定 and 圖片 through the real routes: 設定's tabs and the URL that picks
// one, what each vocabulary sends for add, rename, reorder and delete, the
// refusals explained inline with their counts, the error state, and the image
// library's owners, filter, paging and delete.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AppRoutes from '../../routes'
import { PAGE_SIZE } from './ImageLibrary'

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
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const location = () => screen.getByTestId('location').textContent
const writes = () => calls.filter((call) => call.method !== 'GET')

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
      return handler(call) ?? json([])
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const COURSES = [
  { id: 1, display_name: '主菜', name_cn: '主菜', name_en: null, sort_order: 1, usage_count: 3 },
  { id: 2, display_name: '湯', name_cn: '湯', name_en: null, sort_order: 2, usage_count: 0 },
  { id: 3, display_name: '甜點', name_cn: '甜點', name_en: null, sort_order: 3, usage_count: 0 },
]

const STATUSES = [
  { id: 4, display_name: '想試', name_cn: '想試', name_en: null, sort_order: 10, usage_count: 2 },
  { id: 5, display_name: '常煮', name_cn: '常煮', name_en: null, sort_order: 20, usage_count: 0 },
]

const PLATFORMS = [
  { id: 6, display_name: 'YouTube', name_cn: 'YouTube', name_en: null, sort_order: 10, usage_count: 4 },
]

const TREE = [
  {
    id: 1,
    display_name: '未分類',
    name_cn: '未分類',
    parent_id: null,
    sort_order: 0,
    is_fallback: true,
    ingredient_count: 2,
    children: [],
  },
  {
    id: 2,
    display_name: '蔬菜',
    name_cn: '蔬菜',
    parent_id: null,
    sort_order: 1,
    is_fallback: false,
    ingredient_count: 4,
    children: [
      {
        id: 3,
        display_name: '葉菜',
        name_cn: '葉菜',
        parent_id: 2,
        sort_order: 0,
        is_fallback: false,
        ingredient_count: 0,
        children: [],
      },
    ],
  },
]

// As the server sends them: every author at sort_order 0, so in name order.
const AUTHORS = [
  { id: 4, display_name: 'Babish', name_cn: null, name_en: 'Babish', sort_order: 0, usage_count: 0 },
  { id: 3, display_name: '阿基師', name_cn: '阿基師', name_en: null, sort_order: 0, usage_count: 2 },
]

const LABELS = [
  {
    id: 7,
    display_name: '常備',
    name_cn: '常備',
    name_en: null,
    ingredient_count: 1,
    recipe_count: 2,
    note_count: 0,
    usage_count: 3,
  },
]

function settingsData({ url, method }) {
  if (method !== 'GET') return null
  if (url === '/api/recipe-courses') return json(COURSES)
  if (url === '/api/recipe-statuses') return json(STATUSES)
  if (url === '/api/source-platforms') return json(PLATFORMS)
  if (url === '/api/authors') return json(AUTHORS)
  if (url === '/api/ingredient-categories') return json(TREE)
  if (url === '/api/labels') return json(LABELS)
  return null
}

const section = (name) => screen.getByRole('list', { name })

describe('設定', () => {
  beforeEach(() => {
    handler = settingsData
  })

  it('opens on the first tab, and shows only its panel', async () => {
    renderAt('/edit/settings')
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map((tab) => tab.textContent)).toEqual([
      '食材分類',
      '標籤',
      '類別',
      '狀態',
      '來源',
      '作者',
      '做法',
      '器材',
    ])
    expect(tabs[0].getAttribute('aria-selected')).toBe('true')
    const panel = screen.getByRole('tabpanel')
    expect(panel.getAttribute('aria-labelledby')).toBe(tabs[0].id)
    expect(tabs[0].getAttribute('aria-controls')).toBe(panel.id)
    expect(await within(panel).findByRole('list', { name: '食材分類' })).toBeTruthy()
    // Only the selected tab's editor is mounted, so only its query runs.
    expect(screen.queryByRole('list', { name: '類別' })).toBeNull()
    expect(calls.some(({ url }) => url === '/api/recipe-courses')).toBe(false)
    expect(screen.getByRole('link', { name: '圖片庫' }).getAttribute('href')).toBe('/edit/images')
  })

  it('selects the panel the URL names', async () => {
    renderAt('/edit/settings?tab=courses')
    expect(screen.getByRole('tab', { name: '類別' }).getAttribute('aria-selected')).toBe('true')
    expect(await within(screen.getByRole('tabpanel')).findByRole('list', { name: '類別' })).toBeTruthy()
    expect(screen.queryByRole('list', { name: '食材分類' })).toBeNull()
  })

  it('falls back to the first tab for an unknown one', async () => {
    renderAt('/edit/settings?tab=nonsense')
    expect(screen.getByRole('tab', { name: '食材分類' }).getAttribute('aria-selected')).toBe('true')
    expect(await screen.findByRole('list', { name: '食材分類' })).toBeTruthy()
  })

  it('puts a clicked tab in the URL and shows its panel', async () => {
    renderAt('/edit/settings')
    fireEvent.click(screen.getByRole('tab', { name: '標籤' }))
    expect(location()).toBe('/edit/settings?tab=labels')
    expect(screen.getByRole('tab', { name: '標籤' }).getAttribute('aria-selected')).toBe('true')
    expect(screen.getByRole('tab', { name: '食材分類' }).getAttribute('aria-selected')).toBe('false')
    expect(await screen.findByRole('list', { name: '標籤' })).toBeTruthy()
    expect(screen.queryByRole('list', { name: '食材分類' })).toBeNull()
  })

  it('moves between tabs with the arrow keys, Home and End, wrapping at the ends', () => {
    renderAt('/edit/settings')
    const tab = (name) => screen.getByRole('tab', { name })
    // Only the selected tab is in the Tab order; the arrows move within the bar.
    expect(tab('食材分類').tabIndex).toBe(0)
    expect(tab('標籤').tabIndex).toBe(-1)

    fireEvent.keyDown(tab('食材分類'), { key: 'ArrowRight' })
    expect(location()).toBe('/edit/settings?tab=labels')
    expect(document.activeElement).toBe(tab('標籤'))

    fireEvent.keyDown(tab('標籤'), { key: 'ArrowLeft' })
    fireEvent.keyDown(tab('食材分類'), { key: 'ArrowLeft' })
    expect(location()).toBe('/edit/settings?tab=equipment')
    expect(document.activeElement).toBe(tab('器材'))

    fireEvent.keyDown(tab('器材'), { key: 'ArrowRight' })
    expect(location()).toBe('/edit/settings?tab=categories')
    fireEvent.keyDown(tab('食材分類'), { key: 'End' })
    expect(location()).toBe('/edit/settings?tab=equipment')
    fireEvent.keyDown(tab('器材'), { key: 'Home' })
    expect(location()).toBe('/edit/settings?tab=categories')
    expect(document.activeElement).toBe(tab('食材分類'))
  })

  it('shows each vocabulary with its counts, and labels with every owner', async () => {
    renderAt('/edit/settings?tab=courses')
    const courses = await screen.findByRole('list', { name: '類別' })
    expect(within(courses).getByRole('listitem', { name: '主菜' }).textContent).toContain('用在 3 個地方')
    fireEvent.click(screen.getByRole('tab', { name: '標籤' }))
    const labels = await screen.findByRole('list', { name: '標籤' })
    expect(labels.textContent).toContain('食材 1 · 食譜 2 · 筆記 0')
    // Labels have no order to move by.
    expect(within(labels).queryByRole('button', { name: /^排序/ })).toBeNull()
  })

  it('renames in place', async () => {
    handler = (call) =>
      call.method === 'PATCH' ? json({ ...COURSES[1], name_en: 'soup' }) : settingsData(call)
    renderAt('/edit/settings?tab=courses')
    fireEvent.click(await screen.findByRole('button', { name: '改名「湯」' }))
    fireEvent.change(screen.getByRole('textbox', { name: '湯 的英文名' }), { target: { value: 'soup' } })
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() =>
      expect(writes()).toEqual([
        { url: '/api/edit/recipe-courses/2', method: 'PATCH', body: { name_cn: '湯', name_en: 'soup' } },
      ]),
    )
  })

  it('moves a value by swapping sort_order with its neighbour', async () => {
    handler = (call) => (call.method === 'PATCH' ? json({}) : settingsData(call))
    renderAt('/edit/settings?tab=courses')
    // The first row has nowhere to go up to: nothing is sent.
    fireEvent.keyDown(await screen.findByRole('button', { name: '排序 「主菜」' }), { key: 'ArrowUp' })
    expect(writes()).toEqual([])

    fireEvent.keyDown(screen.getByRole('button', { name: '排序 「甜點」' }), { key: 'ArrowUp' })
    // The new order shows at once, and the list holds still until it lands.
    const names = () =>
      within(section('類別'))
        .getAllByRole('listitem')
        .map((row) => row.getAttribute('aria-label'))
    expect(names()).toEqual(['主菜', '甜點', '湯'])
    expect(screen.getByRole('button', { name: '排序 「湯」' }).disabled).toBe(true)
    await waitFor(() => expect(writes()).toHaveLength(2))
    expect(writes()).toEqual(
      expect.arrayContaining([
        { url: '/api/edit/recipe-courses/3', method: 'PATCH', body: { sort_order: 2 } },
        { url: '/api/edit/recipe-courses/2', method: 'PATCH', body: { sort_order: 3 } },
      ]),
    )
    await waitFor(() => expect(screen.getByRole('button', { name: '排序 「湯」' }).disabled).toBe(false))
  })

  it('puts the stored order back and says why when a move is refused', async () => {
    handler = (call) =>
      call.method === 'PATCH' ? json({ detail: '資料庫連不上' }, 503) : settingsData(call)
    renderAt('/edit/settings?tab=courses')
    fireEvent.keyDown(await screen.findByRole('button', { name: '排序 「甜點」' }), { key: 'ArrowUp' })
    await waitFor(() =>
      expect(within(section('類別').parentElement).getByRole('alert').textContent).toBe('資料庫連不上'),
    )
    expect(
      within(section('類別'))
        .getAllByRole('listitem')
        .map((row) => row.getAttribute('aria-label')),
    ).toEqual(['主菜', '湯', '甜點'])
  })

  it('moves a category among its own siblings, carrying its children', async () => {
    handler = (call) => (call.method === 'PATCH' ? json({}) : settingsData(call))
    renderAt('/edit/settings')
    await screen.findByRole('list', { name: '食材分類' })
    // 葉菜 is an only child: neither key has anywhere to take it.
    fireEvent.keyDown(screen.getByRole('button', { name: '排序 「葉菜」' }), { key: 'ArrowUp' })
    fireEvent.keyDown(screen.getByRole('button', { name: '排序 「葉菜」' }), { key: 'ArrowDown' })
    expect(writes()).toEqual([])

    fireEvent.keyDown(screen.getByRole('button', { name: '排序 「蔬菜」' }), { key: 'ArrowUp' })
    const roots = screen.getByRole('list', { name: '食材分類' })
    expect([...roots.children].map((row) => row.getAttribute('aria-label'))).toEqual(['蔬菜', '未分類'])
    expect(within(roots.children[0]).getByRole('listitem', { name: '葉菜' })).toBeTruthy()
    await waitFor(() => expect(writes()).toHaveLength(2))
    expect(writes()).toEqual(
      expect.arrayContaining([
        { url: '/api/edit/ingredient-categories/2', method: 'PATCH', body: { sort_order: 0 } },
        { url: '/api/edit/ingredient-categories/1', method: 'PATCH', body: { sort_order: 1 } },
      ]),
    )
  })

  it('lists authors by name, with no order to move by, and adds one without a sort_order', async () => {
    handler = (call) => (call.method === 'POST' ? json({}, 201) : settingsData(call))
    renderAt('/edit/settings?tab=authors')
    const authors = await screen.findByRole('list', { name: '作者' })
    expect(within(authors).getAllByRole('listitem').map((row) => row.getAttribute('aria-label'))).toEqual([
      'Babish',
      '阿基師',
    ])
    expect(within(authors).getByRole('listitem', { name: '阿基師' }).textContent).toContain('用在 2 個地方')
    expect(within(authors).queryByRole('button', { name: /^排序/ })).toBeNull()

    const add = screen.getByRole('form', { name: '新增作者' })
    fireEvent.change(within(add).getByRole('textbox', { name: '新增作者：中文名' }), {
      target: { value: '詹姆士' },
    })
    fireEvent.click(within(add).getByRole('button', { name: '＋ 新增作者' }))
    await waitFor(() =>
      expect(writes()).toEqual([
        { url: '/api/edit/authors', method: 'POST', body: { name_cn: '詹姆士', name_en: null } },
      ]),
    )
  })

  it('adds a value after the last one', async () => {
    handler = (call) => (call.method === 'POST' ? json({}, 201) : settingsData(call))
    renderAt('/edit/settings?tab=courses')
    const add = await screen.findByRole('form', { name: '新增類別' })
    fireEvent.change(within(add).getByRole('textbox', { name: '新增類別：中文名' }), {
      target: { value: '前菜' },
    })
    fireEvent.click(within(add).getByRole('button', { name: '＋ 新增類別' }))
    await waitFor(() =>
      expect(writes()).toEqual([
        {
          url: '/api/edit/recipe-courses',
          method: 'POST',
          body: { name_cn: '前菜', name_en: null, sort_order: 4 },
        },
      ]),
    )
  })

  it("explains a refused delete inline with the server's count", async () => {
    // The page says 3; the server knows 5, and its number wins.
    handler = (call) =>
      call.method === 'DELETE'
        ? json({ detail: 'still used', usage_count: 5 }, 409)
        : settingsData(call)
    renderAt('/edit/settings?tab=courses')
    fireEvent.click(await screen.findByRole('button', { name: '刪除「主菜」' }))
    const dialog = screen.getByRole('dialog')
    expect(dialog.textContent).toContain('還用在 3 個地方')
    fireEvent.click(within(dialog).getByRole('button', { name: '刪除' }))
    const row = section('類別').querySelector('[aria-label="主菜"]')
    await waitFor(() =>
      expect(within(row).getByRole('alert').textContent).toBe('「主菜」還用在 5 個地方，先改掉那些再刪。'),
    )
  })

  it('draws the category tree, offers no delete for the fallback, and explains a refusal', async () => {
    handler = (call) =>
      call.method === 'DELETE' ? json({ detail: 'referenced' }, 409) : settingsData(call)
    renderAt('/edit/settings')
    await screen.findByRole('list', { name: '食材分類' })
    expect(screen.queryByRole('button', { name: '刪除「未分類」' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '刪除「蔬菜」' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '刪除' }))
    await waitFor(() =>
      expect(screen.getByRole('alert').textContent).toBe('「蔬菜」底下還有 4 種食材、1 個子分類，先移走再刪。'),
    )
  })

  it('adds a child under the node it was asked for, after its siblings', async () => {
    handler = (call) => (call.method === 'POST' ? json({}, 201) : settingsData(call))
    renderAt('/edit/settings')
    fireEvent.click(await screen.findByRole('button', { name: '在「蔬菜」下新增子分類' }))
    const add = screen.getByRole('form', { name: '蔬菜的子分類' })
    fireEvent.change(within(add).getByRole('textbox', { name: '蔬菜的子分類：中文名' }), {
      target: { value: '根莖' },
    })
    fireEvent.click(within(add).getByRole('button', { name: '＋ 蔬菜的子分類' }))
    await waitFor(() =>
      expect(writes()).toEqual([
        {
          url: '/api/edit/ingredient-categories',
          method: 'POST',
          body: { name_cn: '根莖', name_en: null, parent_id: 2, sort_order: 1 },
        },
      ]),
    )
  })

  it('edits the statuses in their own tab, and marks the recipes stale', async () => {
    handler = (call) => (call.method === 'POST' ? json({}, 201) : settingsData(call))
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    client.setQueryData(['/api/recipes', null], [])
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={['/edit/settings?tab=statuses']}>
          <AppRoutes />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    const statuses = await screen.findByRole('list', { name: '狀態' })
    expect(within(statuses).getByRole('listitem', { name: '想試' }).textContent).toContain('用在 2 個地方')
    const add = screen.getByRole('form', { name: '新增狀態' })
    fireEvent.change(within(add).getByRole('textbox', { name: '新增狀態：中文名' }), {
      target: { value: '冷凍好' },
    })
    fireEvent.click(within(add).getByRole('button', { name: '＋ 新增狀態' }))
    await waitFor(() =>
      expect(writes()).toEqual([
        {
          url: '/api/edit/recipe-statuses',
          method: 'POST',
          body: { name_cn: '冷凍好', name_en: null, sort_order: 21 },
        },
      ]),
    )
    await waitFor(() => expect(client.getQueryState(['/api/recipes', null]).isInvalidated).toBe(true))
  })

  it("explains a refused platform delete with the server's count", async () => {
    handler = (call) =>
      call.method === 'DELETE'
        ? json({ detail: 'still used', usage_count: 4 }, 409)
        : settingsData(call)
    renderAt('/edit/settings?tab=platforms')
    fireEvent.click(await screen.findByRole('button', { name: '刪除「YouTube」' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '刪除' }))
    const row = section('來源').querySelector('[aria-label="YouTube"]')
    await waitFor(() =>
      expect(within(row).getByRole('alert').textContent).toBe('「YouTube」還用在 4 個地方，先改掉那些再刪。'),
    )
    expect(writes()).toEqual([{ url: '/api/edit/source-platforms/6', method: 'DELETE', body: undefined }])
  })

  it('shows an error state in its own tab, leaving the others', async () => {
    handler = (call) =>
      call.url === '/api/equipment' ? json({ detail: '資料庫連不上' }, 503) : settingsData(call)
    renderAt('/edit/settings?tab=equipment')
    expect((await screen.findByRole('alert')).textContent).toBe('資料庫連不上')
    fireEvent.click(screen.getByRole('tab', { name: '類別' }))
    expect(await screen.findByRole('list', { name: '類別' })).toBeTruthy()
    expect(screen.queryByRole('alert')).toBeNull()
  })
})

const image = (id, attachment_count = 0) => ({
  id,
  url: `/images/${id}.jpg`,
  thumb_url: `/images/${id}-t.jpg`,
  width: 800,
  height: 600,
  byte_size: 14540,
  original_filename: `photo-${id}.jpg`,
  uploaded_at: null,
  attachment_count,
})

describe('圖片', () => {
  it("lists each image with its owners as links, and delete only for the unused", async () => {
    handler = ({ url }) => {
      if (url.startsWith('/api/images?')) return json([image(1, 2), image(2)])
      if (url === '/api/images/1')
        return json({
          ...image(1, 2),
          owners: [
            { type: 'recipe', id: 5, display_name: '麻婆豆腐' },
            { type: 'kitchen_note', id: 8, display_name: '油溫' },
          ],
        })
      return null
    }
    renderAt('/edit/images')
    const used = await screen.findByRole('listitem', { name: 'photo-1.jpg' })
    expect((await within(used).findByRole('link', { name: '麻婆豆腐' })).getAttribute('href')).toBe('/recipes/5')
    expect(within(used).getByRole('link', { name: '油溫' }).getAttribute('href')).toBe('/notes/8')
    expect(within(used).queryByRole('button', { name: '刪除' })).toBeNull()
    const unused = screen.getByRole('listitem', { name: 'photo-2.jpg' })
    expect(within(unused).getByRole('button', { name: '刪除' })).toBeTruthy()
    // The unused image's owners are never asked for.
    expect(calls.some((call) => call.url === '/api/images/2')).toBe(false)
  })

  it('puts the unused filter and the page in the URL and the request', async () => {
    const full = Array.from({ length: PAGE_SIZE + 1 }, (_, i) => image(i + 1))
    handler = ({ url }) => (url.startsWith('/api/images?') ? json(full) : null)
    renderAt('/edit/images')
    fireEvent.click(await screen.findByRole('button', { name: '只看未使用' }))
    expect(location()).toBe('/edit/images?unused=1')
    fireEvent.click(await screen.findByRole('button', { name: '下一頁' }))
    expect(location()).toBe('/edit/images?unused=1&page=2')
    // The last IMAGES request: the edit pages also ask the session probe as
    // the URL changes (components/layout/EditSignIn.jsx).
    const lastImages = () => calls.filter(({ url }) => url.startsWith('/api/images')).at(-1)
    await waitFor(() =>
      expect(lastImages().url).toBe(`/api/images?unused=true&limit=${PAGE_SIZE + 1}&offset=${PAGE_SIZE}`),
    )
    expect(await screen.findAllByRole('listitem', { name: /^photo-/ })).toHaveLength(PAGE_SIZE)
  })

  it('deletes an unused image after asking, and shows the owners when the server refuses', async () => {
    handler = ({ url, method }) => {
      if (method === 'DELETE')
        return json(
          { detail: 'attached', owners: [{ type: 'ingredient', id: 3, display_name: '番茄' }] },
          409,
        )
      if (url.startsWith('/api/images?')) return json([image(2)])
      return null
    }
    renderAt('/edit/images')
    const tile = await screen.findByRole('listitem', { name: 'photo-2.jpg' })
    fireEvent.click(within(tile).getByRole('button', { name: '刪除' }))
    fireEvent.click(within(screen.getByRole('dialog')).getByRole('button', { name: '刪除' }))
    await waitFor(() => expect(writes()).toEqual([{ url: '/api/edit/images/2', method: 'DELETE', body: undefined }]))
    expect((await within(tile).findByRole('link', { name: '番茄' })).getAttribute('href')).toBe('/ingredients/3')
    expect(within(tile).queryByRole('button', { name: '刪除' })).toBeNull()
  })

  it('says why the list is empty', async () => {
    renderAt('/edit/images?unused=1')
    expect(await screen.findByText('沒有未使用的圖片。')).toBeTruthy()
  })
})
