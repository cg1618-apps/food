// The form components against a stubbed fetch: the typeahead's keyboard and
// its 「新增」, the delete dialog correcting itself on a 409 and listing what
// blocks a refusal, and the recipe form's save - one target per line, and a
// new recipe's gallery PUT only after the POST has answered with an id.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AppRoutes from '../../routes'
import DeleteDialog from './DeleteDialog'
import Typeahead from './Typeahead'

let calls
let handler

function json(body, status = 200) {
  return new Response(body === null ? null : JSON.stringify(body), { status })
}

beforeEach(() => {
  calls = []
  handler = () => json([])
  vi.stubGlobal(
    'fetch',
    vi.fn(async (url, options = {}) => {
      const call = {
        url: decodeURIComponent(url),
        method: options.method ?? 'GET',
        body: typeof options.body === 'string' ? JSON.parse(options.body) : options.body,
      }
      calls.push(call)
      return handler(call)
    }),
  )
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

function LocationProbe() {
  const { pathname } = useLocation()
  return <output data-testid="location">{pathname}</output>
}

function wrap(ui, path = '/') {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        {ui}
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const GINGER = { id: 1, display_name: '薑', name_cn: '薑', name_en: 'Ginger', needs_detail: false }
const STOCK = { id: 7, display_name: '雞高湯', name_cn: '雞高湯', kind: 'base' }

describe('Typeahead', () => {
  it('searches both libraries once the typing settles and picks with the keyboard', async () => {
    handler = ({ url }) =>
      url.startsWith('/api/ingredients?') ? json([GINGER]) : url.startsWith('/api/recipes?') ? json([STOCK]) : json([])
    const onSelect = vi.fn()
    wrap(<Typeahead label="材料" onSelect={onSelect} allowNew />)

    const box = screen.getByRole('combobox', { name: '材料' })
    fireEvent.change(box, { target: { value: '薑' } })
    await screen.findByRole('option', { name: /薑\s*Ginger/ })
    expect(calls.map((c) => c.url)).toEqual(expect.arrayContaining(['/api/ingredients?q=薑', '/api/recipes?q=薑']))

    // Down twice: the ingredient, then the recipe; Enter picks the recipe.
    fireEvent.keyDown(box, { key: 'ArrowDown' })
    fireEvent.keyDown(box, { key: 'ArrowDown' })
    expect(box.getAttribute('aria-activedescendant')).toBeTruthy()
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ type: 'recipe', id: 7 }))
    expect(box.value).toBe('')
  })

  it('offers 新增 when nothing matches exactly, and Escape closes the list', async () => {
    handler = ({ url }) => (url.startsWith('/api/ingredients?') ? json([GINGER]) : json([]))
    const onSelect = vi.fn()
    wrap(<Typeahead label="材料" sources={['ingredient']} onSelect={onSelect} allowNew />)

    const box = screen.getByRole('combobox', { name: '材料' })
    fireEvent.change(box, { target: { value: '薑末' } })
    const option = await screen.findByRole('option', { name: /新增.*薑末/ })
    expect(option).toBeTruthy()
    // Only the ingredient library was asked.
    expect(calls.some((c) => c.url.startsWith('/api/recipes'))).toBe(false)

    fireEvent.keyDown(box, { key: 'Escape' })
    expect(screen.queryByRole('listbox')).toBeNull()

    fireEvent.change(box, { target: { value: '薑末 ' } })
    fireEvent.click(await screen.findByRole('option', { name: /新增.*薑末/ }))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ type: 'new', label: '薑末' }))
  })

  it('does not submit the form around it on Enter', async () => {
    const onSubmit = vi.fn((event) => event.preventDefault())
    wrap(
      <form onSubmit={onSubmit}>
        <Typeahead label="材料" onSelect={() => {}} />
      </form>,
    )
    fireEvent.keyDown(screen.getByRole('combobox'), { key: 'Enter' })
    expect(onSubmit).not.toHaveBeenCalled()
  })
})

describe('DeleteDialog', () => {
  it('sends the counts it showed, takes the server number on a stale 409, and confirms again', async () => {
    let stale = true
    handler = ({ url, method }) => {
      if (url === '/api/recipes/5/cascade') return json({ aliases: 1, sources: 2, lines: 3, steps: 4, used_in: 0 })
      if (method === 'DELETE' && stale) {
        stale = false
        return json(
          { detail: 'This now removes 5 ingredient lines, not 3.', field: 'lines', expected: 3, actual: 5 },
          409,
        )
      }
      if (method === 'DELETE') return json(null, 204)
      return json([])
    }
    const onDeleted = vi.fn()
    wrap(<DeleteDialog kind="recipe" id={5} name="炒高麗菜" onClose={() => {}} onDeleted={onDeleted} />)

    await screen.findByText('3')
    fireEvent.click(screen.getByRole('button', { name: '刪除' }))
    await screen.findByText(/not 3/)
    // Corrected in place: the 5 is on screen and the button asks again.
    expect(screen.getByText('5')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '確認刪除' }))
    await waitFor(() => expect(onDeleted).toHaveBeenCalled())

    const deletes = calls.filter((c) => c.method === 'DELETE').map((c) => c.url)
    expect(deletes).toEqual([
      '/api/edit/recipes/5?aliases=1&sources=2&lines=3&steps=4',
      '/api/edit/recipes/5?aliases=1&sources=2&lines=5&steps=4',
    ])
  })

  it('lists the recipes that block a refused delete, as links', async () => {
    handler = ({ url, method }) => {
      if (url === '/api/ingredients/3/cascade') {
        return json({ aliases: 0, preservation: 0, heating: 0, links: 0, labels: 0, children: 0, recipes: 1 })
      }
      if (method === 'DELETE') {
        return json(
          {
            detail: 'A recipe still uses this ingredient; change or merge it there first.',
            used_in: [{ id: 9, display_name: '薑汁燒肉' }],
          },
          409,
        )
      }
      return json([])
    }
    wrap(<DeleteDialog kind="ingredient" id={3} name="薑" onClose={() => {}} onDeleted={() => {}} />)

    // The blocking count is said up front...
    expect(await screen.findByText(/有 1 道食譜直接用到它/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '刪除' }))
    // ...and the refusal names them.
    const link = await screen.findByRole('link', { name: '薑汁燒肉' })
    expect(link.getAttribute('href')).toBe('/recipes/9')
    expect(calls.filter((c) => c.method === 'DELETE')[0].url).toBe(
      '/api/edit/ingredients/3?aliases=0&preservation=0&heating=0&links=0',
    )
  })

  it('asks a plain question for a note, which has no cascade to count', async () => {
    handler = ({ method }) => (method === 'DELETE' ? json(null, 204) : json([]))
    wrap(<DeleteDialog kind="note" id={4} name="刀工" onClose={() => {}} />, '/notes/4')
    fireEvent.click(screen.getByRole('button', { name: '刪除' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/notes'))
    expect(calls.some((c) => c.url.includes('cascade'))).toBe(false)
    expect(calls.find((c) => c.method === 'DELETE').url).toBe('/api/edit/kitchen-notes/4')
  })
})

describe('RecipeForm', () => {
  it('creates the recipe with one target per line, then puts the gallery under the new id', async () => {
    const UPLOADED = { id: 31, url: '/images/a.jpg', thumb_url: '/images/ta.jpg' }
    handler = ({ url, method }) => {
      if (url === '/api/vocabularies/fixed') {
        return json({
          recipe_kinds: [{ value: 'dish', label: '料理' }],
          recipe_statuses: [{ value: 'want_to_try', label: '想試' }],
          source_platforms: [{ value: 'youtube', label: 'YouTube' }],
        })
      }
      if (url.startsWith('/api/ingredients?')) return json([GINGER])
      if (url.startsWith('/api/recipes?')) return json([STOCK])
      if (url === '/api/edit/images' && method === 'POST') return json(UPLOADED, 201)
      if (url === '/api/edit/recipes' && method === 'POST') return json({ id: 42, images: [] }, 201)
      if (url === '/api/edit/recipes/42/images' && method === 'PUT') return json({ id: 42 })
      return json([])
    }
    wrap(<AppRoutes />, '/edit/recipes/new')

    fireEvent.change(await screen.findByLabelText('中文名'), { target: { value: '薑汁燒肉' } })

    // A stub line and a sub-recipe line.
    fireEvent.click(screen.getByRole('button', { name: /加一行材料/ }))
    fireEvent.change(screen.getByRole('combobox', { name: '材料 1' }), { target: { value: '紫蘇' } })
    fireEvent.click(await screen.findByRole('option', { name: /新增.*紫蘇/ }))
    expect(screen.getByText('待補')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /加一行材料/ }))
    fireEvent.change(screen.getByRole('combobox', { name: '材料 2' }), { target: { value: '高湯' } })
    fireEvent.click(await screen.findByRole('option', { name: /雞高湯/ }))

    // Steps pasted with their numbering.
    fireEvent.click(screen.getByRole('button', { name: '貼上多行' }))
    fireEvent.change(screen.getByLabelText(/一行一個步驟/), { target: { value: '1. 醃肉\n2) 煎香' } })
    fireEvent.click(screen.getByRole('button', { name: '加入 2 個步驟' }))

    // One picture.
    const file = new File(['x'], 'a.png', { type: 'image/png' })
    await act(async () => {
      fireEvent.change(screen.getByLabelText('上傳圖片'), { target: { files: [file] } })
    })
    await screen.findByRole('listitem', { name: '圖片 1' })

    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))

    const writes = calls.filter((c) => c.method !== 'GET' && c.url !== '/api/edit/images')
    expect(writes.map((c) => `${c.method} ${c.url}`)).toEqual([
      'POST /api/edit/recipes',
      'PUT /api/edit/recipes/42/images',
    ])
    const body = writes[0].body
    expect(body.name_cn).toBe('薑汁燒肉')
    expect(body.lines).toEqual([
      { section: null, amount: null, note: null, is_optional: false, new_ingredient: { name_cn: '紫蘇' } },
      { section: null, amount: null, note: null, is_optional: false, sub_recipe_id: 7 },
    ])
    expect(body.steps).toEqual([
      { section: null, body: '醃肉' },
      { section: null, body: '煎香' },
    ])
    expect(writes[1].body).toEqual([{ image_id: 31, focus: null }])
  })

  it('shows the server sentence beside the save button and stays on the form', async () => {
    handler = ({ url, method }) =>
      url === '/api/edit/recipes' && method === 'POST'
        ? json({ detail: 'A recipe cannot use itself, directly or through another recipe.' }, 422)
        : json([])
    wrap(<AppRoutes />, '/edit/recipes/new')
    fireEvent.change(await screen.findByLabelText('中文名'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    expect(await screen.findByRole('alert')).toHaveProperty(
      'textContent',
      'A recipe cannot use itself, directly or through another recipe.',
    )
    expect(screen.getByTestId('location').textContent).toBe('/edit/recipes/new')
  })
})
