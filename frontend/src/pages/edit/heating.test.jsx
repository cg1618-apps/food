// 加熱's edit page, /edit/heating: every note a card edited in place, saved
// and deleted one at a time, reordered by drag (the keyboard path here, as
// jsdom cannot drag) and saved at once; 「＋ 新增」 puts a fresh card at the end.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AppRoutes from '../../routes'

const NOTES = [
  { id: 3, name: '冷凍吐司', body: '烤箱 180 度 5 分鐘', sort_order: 0 },
  { id: 1, name: '香腸', body: null, sort_order: 1 },
  { id: 2, name: '便當', body: '微波 2 分鐘', sort_order: 2 },
]

let calls
let handler

function json(body, status = 200) {
  return new Response(body === null ? null : JSON.stringify(body), { status })
}

function renderAt(path) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const writes = () => calls.filter((call) => call.method !== 'GET' && call.url !== '/api/edit/session')

function read(call) {
  if (call.method === 'GET' && call.url === '/api/heating') return json(NOTES)
  if (call.url === '/api/edit/session') return new Response(null, { status: 204 })
  return null
}

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
      return handler(call) ?? read(call) ?? json([])
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
})

const cards = () =>
  within(screen.getByRole('list', { name: '加熱' }))
    .getAllByRole('listitem')
    .filter((item) => item.hasAttribute('aria-label'))
const names = () => cards().map((card) => card.getAttribute('aria-label'))
const card = (name) => screen.getByRole('listitem', { name })

describe('the 加熱 edit page', () => {
  it('shows every note as a card, filled in', async () => {
    renderAt('/edit/heating')
    await screen.findByRole('list', { name: '加熱' })
    expect(names()).toEqual(['冷凍吐司', '香腸', '便當'])
    expect(within(card('冷凍吐司')).getByRole('textbox', { name: '名稱' }).value).toBe('冷凍吐司')
    expect(within(card('冷凍吐司')).getByRole('textbox', { name: '怎麼加熱' }).value).toBe('烤箱 180 度 5 分鐘')
    expect(within(card('香腸')).getByRole('textbox', { name: '怎麼加熱' }).value).toBe('')
    expect(screen.getByRole('link', { name: '完成' }).getAttribute('href')).toBe('/heating')
  })

  it('saves a note with its name and how to heat it, blanks as null', async () => {
    handler = (call) => (call.method === 'PATCH' ? json(NOTES[0]) : null)
    renderAt('/edit/heating')
    await screen.findByRole('list', { name: '加熱' })
    const toast = card('冷凍吐司')
    fireEvent.change(within(toast).getByRole('textbox', { name: '名稱' }), { target: { value: ' 冷凍厚片 ' } })
    fireEvent.change(within(toast).getByRole('textbox', { name: '怎麼加熱' }), { target: { value: '  ' } })
    fireEvent.click(within(toast).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(writes()).toHaveLength(1))
    expect(writes()[0]).toEqual({
      url: '/api/edit/heating/3',
      method: 'PATCH',
      body: { name: '冷凍厚片', body: null },
    })
  })

  it('refuses to save a note without a name, sending nothing', async () => {
    renderAt('/edit/heating')
    await screen.findByRole('list', { name: '加熱' })
    const sausage = card('香腸')
    fireEvent.change(within(sausage).getByRole('textbox', { name: '名稱' }), { target: { value: '  ' } })
    fireEvent.click(within(sausage).getByRole('button', { name: '儲存' }))
    expect((await within(sausage).findByRole('alert')).textContent).toContain('名稱')
    expect(writes()).toEqual([])
  })

  it('adds a new card at the end and creates it with POST', async () => {
    handler = (call) =>
      call.method === 'POST' ? json({ id: 9, name: '水餃', body: '水滾下鍋', sort_order: 3 }, 201) : null
    renderAt('/edit/heating')
    await screen.findByRole('list', { name: '加熱' })
    fireEvent.click(screen.getByRole('button', { name: '＋ 新增' }))
    expect(names()).toEqual(['冷凍吐司', '香腸', '便當', '新項目'])
    const fresh = card('新項目')
    fireEvent.change(within(fresh).getByRole('textbox', { name: '名稱' }), { target: { value: '水餃' } })
    fireEvent.change(within(fresh).getByRole('textbox', { name: '怎麼加熱' }), { target: { value: '水滾下鍋' } })
    fireEvent.click(within(fresh).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(writes()).toHaveLength(1))
    expect(writes()[0]).toEqual({
      url: '/api/edit/heating',
      method: 'POST',
      body: { name: '水餃', body: '水滾下鍋' },
    })
  })

  it('drops an unsaved card without asking or sending anything', async () => {
    renderAt('/edit/heating')
    await screen.findByRole('list', { name: '加熱' })
    fireEvent.click(screen.getByRole('button', { name: '＋ 新增' }))
    fireEvent.click(within(card('新項目')).getByRole('button', { name: '取消' }))
    expect(names()).toEqual(['冷凍吐司', '香腸', '便當'])
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(writes()).toEqual([])
  })

  it('deletes a note after asking', async () => {
    handler = (call) => (call.method === 'DELETE' ? json(null, 204) : null)
    renderAt('/edit/heating')
    await screen.findByRole('list', { name: '加熱' })
    fireEvent.click(within(card('冷凍吐司')).getByRole('button', { name: '刪除' }))
    const dialog = screen.getByRole('dialog')
    expect(writes()).toEqual([])
    fireEvent.click(within(dialog).getByRole('button', { name: '刪除' }))
    await waitFor(() =>
      expect(writes()).toEqual([{ url: '/api/edit/heating/3', method: 'DELETE', body: undefined }]),
    )
  })

  it('reorders by keyboard, sending every id', async () => {
    handler = (call) => (call.method === 'PUT' ? json(NOTES) : null)
    renderAt('/edit/heating')
    await screen.findByRole('list', { name: '加熱' })
    fireEvent.keyDown(screen.getByRole('button', { name: '排序 「冷凍吐司」' }), { key: 'ArrowDown' })
    expect(names()).toEqual(['香腸', '冷凍吐司', '便當'])
    await waitFor(() => expect(writes()).toHaveLength(1))
    expect(writes()[0]).toEqual({ url: '/api/edit/heating/order', method: 'PUT', body: { ids: [1, 3, 2] } })
  })

  it("puts the stored order back with the server's sentence when a move is refused", async () => {
    handler = (call) => (call.method === 'PUT' ? json({ detail: '順序對不上' }, 422) : null)
    renderAt('/edit/heating')
    await screen.findByRole('list', { name: '加熱' })
    fireEvent.keyDown(screen.getByRole('button', { name: '排序 「冷凍吐司」' }), { key: 'ArrowDown' })
    expect(await screen.findByText('順序對不上')).toBeTruthy()
    expect(names()).toEqual(['冷凍吐司', '香腸', '便當'])
  })
})
