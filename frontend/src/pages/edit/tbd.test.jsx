// TBD's edit page, /edit/tbd: every entry a card edited in place, saved and
// deleted one at a time, reordered by drag (the keyboard path here, as jsdom
// cannot drag) and saved at once, frozen until the order lands; 「＋ 新增」
// puts a fresh card at the end.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { ThemeProvider } from '../../contexts/ThemeContext'
import AppRoutes from '../../routes'

const ENTRIES = [
  {
    id: 3,
    name: '想試的店',
    sort_order: 0,
    links: [{ id: 7, url: 'https://example.com/shop', label: '甲店' }],
  },
  { id: 1, name: '只有名字', sort_order: 1, links: [] },
  { id: 2, name: null, sort_order: 2, links: [{ id: 9, url: 'https://youtu.be/x', label: null }] },
]

let calls
let handler

function json(body, status = 200) {
  return new Response(body === null ? null : JSON.stringify(body), { status })
}

function renderAt(path) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <ThemeProvider>
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </QueryClientProvider>
    </ThemeProvider>,
  )
}

const writes = () => calls.filter((call) => call.method !== 'GET' && call.url !== '/api/edit/session')

function read(call) {
  if (call.method === 'GET' && call.url === '/api/tbd') return json(ENTRIES)
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
  within(screen.getByRole('list', { name: 'TBD' }))
    .getAllByRole('listitem')
    .filter((item) => item.hasAttribute('aria-label'))
const names = () => cards().map((card) => card.getAttribute('aria-label'))
const card = (name) => screen.getByRole('listitem', { name })

describe('the TBD edit page', () => {
  it('shows every entry as a card, filled in', async () => {
    renderAt('/edit/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    expect(names()).toEqual(['想試的店', '只有名字', '未命名'])
    expect(within(card('想試的店')).getByRole('textbox', { name: '名稱' }).value).toBe('想試的店')
    expect(within(card('想試的店')).getByRole('textbox', { name: '連結 1 網址' }).value).toBe(
      'https://example.com/shop',
    )
    expect(within(card('想試的店')).getByRole('textbox', { name: '連結 1 文字' }).value).toBe('甲店')
    expect(screen.getByRole('link', { name: '完成' }).getAttribute('href')).toBe('/tbd')
  })

  it('saves an entry with its name and its links, wholesale', async () => {
    handler = (call) => (call.method === 'PATCH' ? json(ENTRIES[0]) : null)
    renderAt('/edit/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    const shop = card('想試的店')
    fireEvent.change(within(shop).getByRole('textbox', { name: '名稱' }), { target: { value: '想去的店 ' } })
    fireEvent.click(within(shop).getByRole('button', { name: /新增連結/ }))
    fireEvent.change(within(shop).getByRole('textbox', { name: '連結 2 網址' }), {
      target: { value: ' example.org/b ' },
    })
    fireEvent.click(within(shop).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(writes()).toHaveLength(1))
    expect(writes()[0]).toEqual({
      url: '/api/edit/tbd/3',
      method: 'PATCH',
      body: {
        name: '想去的店',
        links: [
          { url: 'https://example.com/shop', label: '甲店' },
          { url: 'example.org/b', label: null },
        ],
      },
    })
  })

  it('leaves an untouched empty link row out of the save', async () => {
    handler = (call) => (call.method === 'PATCH' ? json(ENTRIES[1]) : null)
    renderAt('/edit/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    const named = card('只有名字')
    fireEvent.click(within(named).getByRole('button', { name: /新增連結/ }))
    fireEvent.click(within(named).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(writes()).toHaveLength(1))
    expect(writes()[0].body).toEqual({ name: '只有名字', links: [] })
  })

  it('refuses to save an entry with neither a name nor a link, sending nothing', async () => {
    renderAt('/edit/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    const named = card('只有名字')
    fireEvent.change(within(named).getByRole('textbox', { name: '名稱' }), { target: { value: '  ' } })
    fireEvent.click(within(named).getByRole('button', { name: '儲存' }))
    expect((await within(named).findByRole('alert')).textContent).toContain('名稱或連結')
    expect(writes()).toEqual([])
  })

  it("shows the server's sentence when a save is refused", async () => {
    handler = (call) => (call.method === 'PATCH' ? json({ detail: 'A link must be an http or https URL' }, 422) : null)
    renderAt('/edit/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    const shop = card('想試的店')
    fireEvent.click(within(shop).getByRole('button', { name: '儲存' }))
    expect((await within(shop).findByRole('alert')).textContent).toBe('A link must be an http or https URL')
  })

  it('adds a new card at the end and creates it with POST', async () => {
    handler = (call) => (call.method === 'POST' ? json({ id: 9, name: '新的', sort_order: 3, links: [] }, 201) : null)
    renderAt('/edit/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    fireEvent.click(screen.getByRole('button', { name: '＋ 新增' }))
    expect(names()).toEqual(['想試的店', '只有名字', '未命名', '新項目'])
    const fresh = card('新項目')
    fireEvent.change(within(fresh).getByRole('textbox', { name: '名稱' }), { target: { value: '新的' } })
    fireEvent.click(within(fresh).getByRole('button', { name: /新增連結/ }))
    fireEvent.change(within(fresh).getByRole('textbox', { name: '連結 1 網址' }), {
      target: { value: 'https://example.com/new' },
    })
    fireEvent.change(within(fresh).getByRole('textbox', { name: '連結 1 文字' }), {
      target: { value: '新連結' },
    })
    fireEvent.click(within(fresh).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(writes()).toHaveLength(1))
    expect(writes()[0]).toEqual({
      url: '/api/edit/tbd',
      method: 'POST',
      body: { name: '新的', links: [{ url: 'https://example.com/new', label: '新連結' }] },
    })
  })

  it('drops an unsaved card without asking or sending anything', async () => {
    renderAt('/edit/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    fireEvent.click(screen.getByRole('button', { name: '＋ 新增' }))
    fireEvent.click(within(card('新項目')).getByRole('button', { name: '取消' }))
    expect(names()).toEqual(['想試的店', '只有名字', '未命名'])
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(writes()).toEqual([])
  })

  it('deletes an entry after asking', async () => {
    handler = (call) => (call.method === 'DELETE' ? json(null, 204) : null)
    renderAt('/edit/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    fireEvent.click(within(card('想試的店')).getByRole('button', { name: '刪除' }))
    const dialog = screen.getByRole('dialog')
    expect(writes()).toEqual([])
    fireEvent.click(within(dialog).getByRole('button', { name: '刪除' }))
    await waitFor(() => expect(writes()).toEqual([{ url: '/api/edit/tbd/3', method: 'DELETE', body: undefined }]))
  })

  it('reorders by keyboard, sending every id, frozen until it lands', async () => {
    let release
    handler = (call) =>
      call.method === 'PUT'
        ? new Promise((resolve) => {
            release = () => resolve(json(ENTRIES))
          })
        : null
    renderAt('/edit/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    // The first has nowhere to go up to: nothing is sent.
    fireEvent.keyDown(screen.getByRole('button', { name: '排序 「想試的店」' }), { key: 'ArrowUp' })
    expect(writes()).toEqual([])

    fireEvent.keyDown(screen.getByRole('button', { name: '排序 「想試的店」' }), { key: 'ArrowDown' })
    expect(names()).toEqual(['只有名字', '想試的店', '未命名'])
    expect(screen.getByRole('button', { name: '排序 「只有名字」' }).disabled).toBe(true)
    await waitFor(() => expect(writes()).toHaveLength(1))
    expect(writes()[0]).toEqual({ url: '/api/edit/tbd/order', method: 'PUT', body: { ids: [1, 3, 2] } })
    release()
    await waitFor(() => expect(screen.getByRole('button', { name: '排序 「只有名字」' }).disabled).toBe(false))
  })

  it("puts the stored order back with the server's sentence when a move is refused", async () => {
    handler = (call) => (call.method === 'PUT' ? json({ detail: '順序對不上' }, 422) : null)
    renderAt('/edit/tbd')
    await screen.findByRole('list', { name: 'TBD' })
    fireEvent.keyDown(screen.getByRole('button', { name: '排序 「想試的店」' }), { key: 'ArrowDown' })
    expect(await screen.findByText('順序對不上')).toBeTruthy()
    expect(names()).toEqual(['想試的店', '只有名字', '未命名'])
  })
})
