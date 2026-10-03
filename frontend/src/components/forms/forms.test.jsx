// The form components against a stubbed fetch: the typeahead's keyboard and
// its 「新增」, the delete dialog correcting itself on a 409 and listing what
// blocks a refusal, the recipe form's save - its dish, picked or new or
// preset from ?dish=, one target per line, and a new recipe's gallery PUT only
// after the POST has answered with an id - and the dish form's save.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { useState } from 'react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AppRoutes from '../../routes'
import Dialog from '../ui/Dialog'
import DeleteDialog from './DeleteDialog'
import RowEditor from './RowEditor'
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

function wrap(ui, path = '/', client = new QueryClient({ defaultOptions: { queries: { retry: false } } })) {
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
const STOCK = { id: 7, display_name: '雞高湯', name_cn: '雞高湯', kind: 'sauce' }

// A recipe belongs to a dish: type a name into the 料理 box and pick 「新增」.
// The dish search answers nothing in these tests unless a handler says so.
async function chooseNewDish(name) {
  fireEvent.change(await screen.findByRole('combobox', { name: '料理' }), { target: { value: name } })
  // The name is in a <strong>, which the accessible name pads with spaces.
  fireEvent.click(await screen.findByRole('option', { name: new RegExp(`^新增「\\s*${name}\\s*」`) }))
}

describe('Typeahead', () => {
  it('searches both libraries once the typing settles and picks with the keyboard', async () => {
    handler = ({ url }) =>
      url.startsWith('/api/ingredients?') ? json([GINGER]) : url.startsWith('/api/dishes?') ? json([STOCK]) : json([])
    const onSelect = vi.fn()
    wrap(<Typeahead label="材料" onSelect={onSelect} allowNew />)

    const box = screen.getByRole('combobox', { name: '材料' })
    fireEvent.change(box, { target: { value: '薑' } })
    await screen.findByRole('option', { name: /薑\s*Ginger/ })
    expect(calls.map((c) => c.url)).toEqual(expect.arrayContaining(['/api/ingredients?q=薑', '/api/dishes?q=薑']))
    // A sauce says so.
    expect(screen.getByRole('option', { name: /雞高湯/ }).textContent).toContain('醬料')

    // Down twice: the ingredient, then the dish; Enter picks the dish.
    fireEvent.keyDown(box, { key: 'ArrowDown' })
    fireEvent.keyDown(box, { key: 'ArrowDown' })
    expect(box.getAttribute('aria-activedescendant')).toBeTruthy()
    fireEvent.keyDown(box, { key: 'Enter' })
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ type: 'dish', id: 7 }))
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
    expect(calls.some((c) => c.url.startsWith('/api/dishes'))).toBe(false)

    fireEvent.keyDown(box, { key: 'Escape' })
    expect(screen.queryByRole('listbox')).toBeNull()

    fireEvent.change(box, { target: { value: '薑末 ' } })
    fireEvent.click(await screen.findByRole('option', { name: /新增.*薑末/ }))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ type: 'new', label: '薑末' }))
  })

  // Found driving the app: 「新增」 was offered the moment the typing
  // settled, before the search answered, so a quick Enter made a stub named
  // after an ingredient that already exists.
  it('does not offer 新增 until the search has answered', async () => {
    let answer
    handler = ({ url }) =>
      url.startsWith('/api/ingredients?')
        ? new Promise((resolve) => (answer = () => resolve(json([{ ...GINGER, display_name: '薑母', name_cn: '薑母' }]))))
        : json([])
    wrap(<Typeahead label="材料" sources={['ingredient']} onSelect={() => {}} allowNew />)
    fireEvent.change(screen.getByRole('combobox', { name: '材料' }), { target: { value: '薑' } })
    await waitFor(() => expect(answer).toBeTypeOf('function'))
    expect(screen.queryByRole('option', { name: /新增/ })).toBeNull()
    await act(async () => answer())
    expect(await screen.findByRole('option', { name: /新增.*薑/ })).toBeTruthy()
    expect(screen.getByRole('option', { name: /薑母/ })).toBeTruthy()
  })

  it('tells the caller what is typed and not yet picked, and clears it on a pick', async () => {
    handler = ({ url }) => (url.startsWith('/api/ingredients?') ? json([GINGER]) : json([]))
    const onQueryChange = vi.fn()
    wrap(<Typeahead label="材料" sources={['ingredient']} onSelect={() => {}} onQueryChange={onQueryChange} />)
    const box = screen.getByRole('combobox', { name: '材料' })
    fireEvent.change(box, { target: { value: '薑' } })
    expect(onQueryChange).toHaveBeenLastCalledWith('薑')
    fireEvent.click(await screen.findByRole('option', { name: /薑\s*Ginger/ }))
    expect(onQueryChange).toHaveBeenLastCalledWith('')
  })

  it('filters a list it was handed, in the browser, and offers 新增 with its own words', async () => {
    const AUTHORS = [
      { id: 3, display_name: '阿基師', name_cn: '阿基師', name_en: null },
      { id: 4, display_name: 'Babish', name_cn: null, name_en: 'Babish' },
    ]
    const onSelect = vi.fn()
    wrap(<Typeahead label="作者" items={AUTHORS} onSelect={onSelect} allowNew newHint="（存檔時建立作者）" />)
    const box = screen.getByRole('combobox', { name: '作者' })

    // Case-insensitive, any name slot, and an exact match offers no 新增.
    fireEvent.change(box, { target: { value: 'babish' } })
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual(['Babish'])

    fireEvent.change(box, { target: { value: '阿基' } })
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      '阿基師',
      '新增「阿基」（存檔時建立作者）',
    ])
    fireEvent.click(screen.getByRole('option', { name: '阿基師' }))
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ type: 'item', id: 3, label: '阿基師' }))
    // Nothing was asked of the server.
    expect(calls).toEqual([])
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

describe('RowEditor', () => {
  // jsdom cannot drag, so the handle's keyboard path stands in for it: the
  // same onMove a drop calls, one place at a time.
  function Steps({ onChange }) {
    const [rows, setRows] = useState([
      { _key: 'a', text: '洗' },
      { _key: 'b', text: '切' },
      { _key: 'c', text: '炒' },
    ])
    return (
      <RowEditor
        rows={rows}
        onChange={(next) => {
          onChange(next)
          setRows(next)
        }}
        newRow={() => ({ text: '' })}
        itemLabel="步驟"
      >
        {(row) => <span>{row.text}</span>}
      </RowEditor>
    )
  }

  it('moves a row by its handle, carrying its key, and keeps focus on it', () => {
    const onChange = vi.fn()
    render(<Steps onChange={onChange} />)
    expect(screen.queryByRole('button', { name: /上移|下移/ })).toBeNull()

    fireEvent.keyDown(screen.getByRole('button', { name: '排序 步驟 1' }), { key: 'ArrowUp' })
    expect(onChange).not.toHaveBeenCalled()

    fireEvent.keyDown(screen.getByRole('button', { name: '排序 步驟 3' }), { key: 'ArrowUp' })
    expect(onChange).toHaveBeenLastCalledWith([
      { _key: 'a', text: '洗' },
      { _key: 'c', text: '炒' },
      { _key: 'b', text: '切' },
    ])
    // The moved row is now 步驟 2, and its handle has the focus, so a held
    // key keeps moving the same row.
    expect(document.activeElement).toBe(screen.getByRole('button', { name: '排序 步驟 2' }))
    expect(screen.getByRole('group', { name: '步驟 2' }).textContent).toContain('炒')
  })
})

describe('Dialog', () => {
  function Opener() {
    const [open, setOpen] = useState(false)
    return (
      <>
        <button type="button" onClick={() => setOpen(true)}>
          打開
        </button>
        {open ? (
          <Dialog title="測試" onClose={() => setOpen(false)} footer={<button type="button">最後</button>}>
            <button type="button">第一</button>
          </Dialog>
        ) : null}
      </>
    )
  }

  it('keeps Tab inside itself and gives focus back to its opener on close', () => {
    wrap(<Opener />)
    const opener = screen.getByRole('button', { name: '打開' })
    opener.focus()
    fireEvent.click(opener)
    const first = screen.getByRole('button', { name: '第一' })
    const last = screen.getByRole('button', { name: '最後' })

    last.focus()
    fireEvent.keyDown(last, { key: 'Tab' })
    expect(document.activeElement).toBe(first)
    fireEvent.keyDown(first, { key: 'Tab', shiftKey: true })
    expect(document.activeElement).toBe(last)

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(screen.queryByRole('dialog')).toBeNull()
    expect(document.activeElement).toBe(opener)
  })

  it('is drawn outside the form that opened it', () => {
    wrap(
      <form>
        <Dialog title="測試" onClose={() => {}}>
          <input aria-label="框" />
        </Dialog>
      </form>,
    )
    expect(screen.getByRole('dialog').closest('form')).toBeNull()
  })

  it('ignores Escape and the backdrop while busy', () => {
    const onClose = vi.fn()
    wrap(
      <Dialog title="測試" onClose={onClose} busy>
        <p>x</p>
      </Dialog>,
    )
    fireEvent.keyDown(document, { key: 'Escape' })
    const backdrop = screen.getByRole('dialog').parentElement
    fireEvent.mouseDown(backdrop)
    fireEvent.click(backdrop)
    expect(onClose).not.toHaveBeenCalled()
  })
})

describe('DeleteDialog', () => {
  it('cannot be dismissed while the delete is running', async () => {
    let finish
    handler = ({ url, method }) => {
      if (url === '/api/recipes/5/cascade') return json({ sources: 0, lines: 0, steps: 0 })
      if (method === 'DELETE') return new Promise((resolve) => (finish = () => resolve(json(null, 204))))
      return json([])
    }
    const onClose = vi.fn()
    wrap(<DeleteDialog kind="recipe" id={5} name="x" onClose={onClose} onDeleted={() => {}} />)
    await screen.findByText(/刪除後就找不回來了/)
    fireEvent.click(screen.getByRole('button', { name: '刪除' }))
    await screen.findByRole('button', { name: '刪除中…' })
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onClose).not.toHaveBeenCalled()
    await act(async () => finish())
  })

  it('sends the counts it showed, takes the server number on a stale 409, and confirms again', async () => {
    let stale = true
    handler = ({ url, method }) => {
      if (url === '/api/recipes/5/cascade') return json({ sources: 2, lines: 3, steps: 4 })
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
      '/api/edit/recipes/5?sources=2&lines=3&steps=4',
      '/api/edit/recipes/5?sources=2&lines=5&steps=4',
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
          dish_kinds: [
            { value: 'dish', label: '料理' },
            { value: 'sauce', label: '醬料' },
          ],
        })
      }
      if (url.startsWith('/api/ingredients?')) return json([GINGER])
      if (url.startsWith('/api/dishes?q=高湯')) return json([STOCK])
      if (url === '/api/edit/images' && method === 'POST') return json(UPLOADED, 201)
      if (url === '/api/edit/recipes' && method === 'POST') return json({ id: 42, images: [] }, 201)
      if (url === '/api/edit/recipes/42/images' && method === 'PUT') return json({ id: 42 })
      return json([])
    }
    wrap(<AppRoutes />, '/edit/recipes/new')

    await chooseNewDish('薑汁燒肉')

    // A stub line, a line naming a dish, and a line naming a dish the save
    // makes - a 醬料 unless told.
    fireEvent.click(screen.getByRole('button', { name: /加一行材料/ }))
    fireEvent.change(screen.getByRole('combobox', { name: '材料 1' }), { target: { value: '紫蘇' } })
    fireEvent.click(await screen.findByRole('option', { name: /^新增「\s*紫蘇/ }))
    expect(screen.getByText('待補')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: /加一行材料/ }))
    fireEvent.change(screen.getByRole('combobox', { name: '材料 2' }), { target: { value: '高湯' } })
    fireEvent.click(await screen.findByRole('option', { name: /雞高湯/ }))

    fireEvent.click(screen.getByRole('button', { name: /加一行材料/ }))
    fireEvent.change(screen.getByRole('combobox', { name: '材料 3' }), { target: { value: '照燒醬' } })
    // Both are offered: a new ingredient and a new dish.
    expect(await screen.findByRole('option', { name: /^新增「\s*照燒醬/ })).toBeTruthy()
    fireEvent.click(screen.getByRole('option', { name: /^新增料理「\s*照燒醬/ }))
    expect(within(screen.getByRole('group', { name: '材料 3' })).getByText('新醬料')).toBeTruthy()

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
    expect(body.new_dish).toEqual({ name_cn: '薑汁燒肉', kind: 'dish' })
    expect(body.name).toBeNull()
    for (const gone of ['name_cn', 'kind', 'course_id', 'label_ids', 'aliases', 'variant_of_id']) {
      expect(gone in body).toBe(false)
    }
    expect(body.lines).toEqual([
      { amount: null, note: null, is_optional: false, new_ingredient: { name_cn: '紫蘇' } },
      { amount: null, note: null, is_optional: false, sub_dish_id: 7 },
      { amount: null, note: null, is_optional: false, new_dish: { name_cn: '照燒醬', kind: 'sauce' } },
    ])
    expect(body.line_groups).toEqual([])
    // Pasted steps are ordinary steps.
    expect(body.steps).toEqual([
      { body: '醃肉', kind: 'step' },
      { body: '煎香', kind: 'step' },
    ])
    expect(body.step_groups).toEqual([])
    expect(writes[1].body).toEqual([{ image_id: 31, focus: null }])
  })

  it('starts on the first status, and a new source on the first platform', async () => {
    handler = ({ url, method }) => {
      if (url === '/api/recipe-statuses') {
        return json([
          { id: 8, display_name: '想試', sort_order: 10, usage_count: 0 },
          { id: 3, display_name: '可煮', sort_order: 20, usage_count: 0 },
        ])
      }
      if (url === '/api/source-platforms') {
        return json([
          { id: 12, display_name: 'YouTube', sort_order: 10, usage_count: 0 },
          { id: 11, display_name: '書', sort_order: 20, usage_count: 0 },
        ])
      }
      if (url === '/api/edit/recipes' && method === 'POST') return json({ id: 42, images: [] }, 201)
      return json([])
    }
    wrap(<AppRoutes />, '/edit/recipes/new')
    await chooseNewDish('湯')
    await screen.findByRole('option', { name: '可煮' })
    expect(screen.getByLabelText('狀態').value).toBe('8')

    fireEvent.click(screen.getByRole('button', { name: /加一個來源/ }))
    await screen.findByRole('option', { name: '書' })
    expect(screen.getByLabelText('平台').value).toBe('12')
    fireEvent.change(screen.getByLabelText('來源標題'), { target: { value: '家常菜' } })
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))

    const body = calls.find((c) => c.method === 'POST').body
    expect(body.status_id).toBe(8)
    expect(body.sources).toEqual([{ platform_id: 12, author_id: null, url: null, title: '家常菜' }])
  })

  const AUTHORS = [{ id: 3, display_name: '阿基師', name_cn: '阿基師', name_en: null, sort_order: 0, usage_count: 1 }]
  const withAuthors = ({ url, method }) => {
    if (url === '/api/authors') return json(AUTHORS)
    if (url === '/api/edit/recipes' && method === 'POST') return json({ id: 42, images: [] }, 201)
    return json([])
  }

  it("picks a source's author from the authors list, or makes a new one on save", async () => {
    handler = withAuthors
    wrap(<AppRoutes />, '/edit/recipes/new')
    await chooseNewDish('湯')

    fireEvent.click(screen.getByRole('button', { name: /加一個來源/ }))
    fireEvent.change(screen.getByRole('combobox', { name: '作者 1' }), { target: { value: '阿基' } })
    fireEvent.click(await screen.findByRole('option', { name: '阿基師' }))

    fireEvent.click(screen.getByRole('button', { name: /加一個來源/ }))
    fireEvent.change(screen.getByRole('combobox', { name: '作者 2' }), { target: { value: 'Babish' } })
    fireEvent.click(await screen.findByRole('option', { name: /新增.*Babish/ }))
    expect(screen.getByText('Babish')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))
    expect(calls.find((c) => c.method === 'POST').body.sources).toEqual([
      { platform_id: expect.any(Number), author_id: 3, url: null, title: null },
      { platform_id: expect.any(Number), new_author: { name_en: 'Babish' }, url: null, title: null },
    ])
  })

  it('refuses to save an author that was typed but never picked', async () => {
    handler = withAuthors
    wrap(<AppRoutes />, '/edit/recipes/new')
    await chooseNewDish('湯')
    fireEvent.click(screen.getByRole('button', { name: /加一個來源/ }))
    fireEvent.change(screen.getByRole('combobox', { name: '作者 1' }), { target: { value: '詹姆士' } })
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/第 1 個來源.*詹姆士.*還沒選/)
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('leaves the status to the server when there are no statuses to choose from', async () => {
    handler = ({ url, method }) =>
      url === '/api/edit/recipes' && method === 'POST' ? json({ id: 42, images: [] }, 201) : json([])
    wrap(<AppRoutes />, '/edit/recipes/new')
    await chooseNewDish('湯')
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))
    expect('status_id' in calls.find((c) => c.method === 'POST').body).toBe(false)
  })

  it('refuses to save a line whose name was typed but never picked', async () => {
    wrap(<AppRoutes />, '/edit/recipes/new')
    await chooseNewDish('湯')
    fireEvent.click(screen.getByRole('button', { name: /加一行材料/ }))
    fireEvent.change(screen.getByRole('combobox', { name: '材料 1' }), { target: { value: '紫蘇' } })
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/第 1 行.*紫蘇.*還沒選/)
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('refuses to save without a dish, or with one typed but never picked', async () => {
    wrap(<AppRoutes />, '/edit/recipes/new')
    fireEvent.click(await screen.findByRole('button', { name: '儲存' }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/哪道料理/)
    fireEvent.change(screen.getByRole('combobox', { name: '料理' }), { target: { value: '高湯' } })
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByRole('alert').textContent).toMatch(/料理.*高湯.*還沒/))
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('picks an existing dish, or makes a new one as a 料理 or a 醬料, with an optional name', async () => {
    handler = ({ url, method }) => {
      if (url === '/api/vocabularies/fixed') {
        return json({
          dish_kinds: [
            { value: 'dish', label: '料理' },
            { value: 'sauce', label: '醬料' },
          ],
        })
      }
      if (url.startsWith('/api/dishes?q=照燒')) {
        return json([{ id: 40, display_name: '照燒雞腿排', name_cn: '照燒雞腿排', kind: 'dish' }])
      }
      if (url === '/api/edit/recipes' && method === 'POST') return json({ id: 42, images: [] }, 201)
      return json([])
    }
    wrap(<AppRoutes />, '/edit/recipes/new')

    // A new dish: 料理 by default, switched to 醬料.
    await chooseNewDish('柴魚高湯')
    const kind = await screen.findByRole('group', { name: '新料理的種類' })
    expect(within(kind).getByRole('button', { name: '料理' }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(within(kind).getByRole('button', { name: '醬料' }))
    expect(screen.getByText('新醬料')).toBeTruthy()

    // Changed to an existing dish instead.
    fireEvent.click(screen.getByRole('button', { name: '更換' }))
    fireEvent.change(screen.getByRole('combobox', { name: '料理' }), { target: { value: '照燒' } })
    fireEvent.click(await screen.findByRole('option', { name: /照燒雞腿排/ }))
    expect(screen.queryByRole('group', { name: '新料理的種類' })).toBeNull()
    fireEvent.change(screen.getByLabelText(/^名稱/), { target: { value: '阿基師版' } })

    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))
    const body = calls.find((c) => c.method === 'POST').body
    expect(body.dish_id).toBe(40)
    expect('new_dish' in body).toBe(false)
    expect(body.name).toBe('阿基師版')
  })

  it('starts with the dish ?dish= names, and saves the recipe under it', async () => {
    handler = ({ url, method }) => {
      if (url === '/api/dishes/40') {
        return json({ id: 40, display_name: '照燒雞腿排', name_cn: '照燒雞腿排', kind: 'dish', recipes: [] })
      }
      if (url === '/api/edit/recipes' && method === 'POST') return json({ id: 42, images: [] }, 201)
      return json([])
    }
    wrap(<AppRoutes />, '/edit/recipes/new?dish=40')
    expect(await screen.findByText('照燒雞腿排')).toBeTruthy()
    expect(screen.queryByRole('combobox', { name: '料理' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))
    expect(calls.find((c) => c.method === 'POST').body.dish_id).toBe(40)
  })

  it('drops a blank source row and marks the category counts stale for a 新增 line', async () => {
    handler = ({ url, method }) => {
      if (url === '/api/edit/recipes' && method === 'POST') return json({ id: 42, images: [] }, 201)
      return json([])
    }
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    // The fallback category's count is what a stub line moves.
    client.setQueryData(['/api/ingredient-categories', null], [])
    wrap(<AppRoutes />, '/edit/recipes/new', client)

    await chooseNewDish('湯')
    fireEvent.click(screen.getByRole('button', { name: /加一個來源/ }))
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))

    expect(calls.find((c) => c.method === 'POST').body.sources).toEqual([])
    expect(client.getQueryState(['/api/ingredient-categories', null]).isInvalidated).toBe(true)
  })

  it('shows the server sentence beside the save button and stays on the form', async () => {
    handler = ({ url, method }) =>
      url === '/api/edit/recipes' && method === 'POST'
        ? json({ detail: 'A recipe cannot use itself, directly or through another recipe.' }, 422)
        : json([])
    wrap(<AppRoutes />, '/edit/recipes/new')
    await chooseNewDish('x')
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    expect(await screen.findByRole('alert')).toHaveProperty(
      'textContent',
      'A recipe cannot use itself, directly or through another recipe.',
    )
    expect(screen.getByTestId('location').textContent).toBe('/edit/recipes/new')
  })
})

describe('RecipeForm groups', () => {
  const STEP_GROUPS = [
    { id: 1, display_name: '備料', name_cn: '備料', name_en: null, sort_order: 10, usage_count: 0 },
    { id: 2, display_name: '烹飪', name_cn: '烹飪', name_en: null, sort_order: 20, usage_count: 0 },
  ]
  const LINE_GROUPS = [
    { id: 11, display_name: '主料', name_cn: '主料', name_en: null, sort_order: 10, usage_count: 0 },
    { id: 12, display_name: 'Sauce', name_cn: null, name_en: 'Sauce', sort_order: 20, usage_count: 0 },
  ]
  const groupData = ({ url, method }) => {
    if (url === '/api/step-groups') return json(STEP_GROUPS)
    if (url === '/api/line-groups') return json(LINE_GROUPS)
    if (url.startsWith('/api/ingredients?')) return json([GINGER])
    if (url === '/api/edit/recipes' && method === 'POST') return json({ id: 42, images: [] }, 201)
    if (url === '/api/edit/recipes/5' && method === 'PATCH') return json({ id: 5, images: [] })
    return json([])
  }
  const area = (title) => screen.getByRole('heading', { level: 2, name: title }).closest('section')
  const postBody = () => calls.find((c) => c.method === 'POST' && c.url === '/api/edit/recipes').body

  it('puts steps in groups from 設定 chips and by name, moves them by keyboard, and pastes into a group', async () => {
    handler = groupData
    wrap(<AppRoutes />, '/edit/recipes/new')
    await chooseNewDish('麻婆豆腐')
    const steps = area('步驟')

    // A 設定 value, one tap; then a one-off name.
    fireEvent.click(within(steps).getByRole('button', { name: '＋ 加分組' }))
    fireEvent.click(await within(steps).findByRole('button', { name: '＋ 備料' }))
    fireEvent.click(within(steps).getByRole('button', { name: '＋ 加分組' }))
    // 備料 is used, so only 烹飪 is offered.
    expect(within(steps).queryByRole('button', { name: '＋ 備料' })).toBeNull()
    expect(within(steps).getByRole('button', { name: '＋ 烹飪' })).toBeTruthy()
    fireEvent.change(within(steps).getByLabelText('自訂分組名稱'), { target: { value: '收尾' } })
    fireEvent.click(within(steps).getByRole('button', { name: '加入' }))

    // A row added inside a group belongs to it; rows are numbered through all.
    fireEvent.click(within(steps).getByRole('button', { name: '＋ 加一個步驟' }))
    fireEvent.change(screen.getByRole('textbox', { name: '步驟 1' }), { target: { value: '看' } })
    fireEvent.click(within(steps).getByRole('button', { name: '＋ 加一個步驟到「備料」' }))
    fireEvent.change(screen.getByRole('textbox', { name: '步驟 2' }), { target: { value: '切' } })
    fireEvent.click(within(steps).getByRole('button', { name: '＋ 加一個步驟到「備料」' }))
    fireEvent.change(screen.getByRole('textbox', { name: '步驟 3' }), { target: { value: '醃' } })
    const prep = () => screen.getByRole('region', { name: '步驟分組「備料」' })
    const finish = () => screen.getByRole('region', { name: '步驟分組「收尾」' })
    expect(within(prep()).getAllByRole('group').map((row) => row.getAttribute('aria-label'))).toEqual([
      '步驟 2',
      '步驟 3',
    ])

    // Up from a group's first row crosses into the area above it, and the
    // moved row keeps the focus.
    fireEvent.keyDown(screen.getByRole('button', { name: '排序 步驟 2' }), { key: 'ArrowUp' })
    expect(within(prep()).getAllByRole('textbox').map((box) => box.value)).toEqual(['醃'])
    expect(document.activeElement).toBe(screen.getByRole('button', { name: '排序 步驟 2' }))
    expect(screen.getByRole('textbox', { name: '步驟 2' }).value).toBe('切')
    // Down from a group's last row goes to the start of the group below,
    // empty or not.
    fireEvent.keyDown(screen.getByRole('button', { name: '排序 步驟 3' }), { key: 'ArrowDown' })
    expect(within(prep()).queryAllByRole('textbox')).toEqual([])
    expect(within(finish()).getAllByRole('textbox').map((box) => box.value)).toEqual(['醃'])

    // Groups reorder by their own handle.
    fireEvent.keyDown(screen.getByRole('button', { name: '排序 步驟分組「收尾」' }), { key: 'ArrowUp' })
    expect(within(steps).getAllByRole('region').map((r) => r.getAttribute('aria-label'))).toEqual([
      '步驟分組「收尾」',
      '步驟分組「備料」',
    ])

    // Pasted steps go to the chosen group.
    fireEvent.click(screen.getByRole('button', { name: '貼上多行' }))
    fireEvent.change(screen.getByLabelText(/一行一個步驟/), { target: { value: '1. 擺盤' } })
    const target = screen.getByLabelText('加到')
    expect(target.value).toBe(within(target).getByRole('option', { name: '不分組' }).value)
    fireEvent.change(target, { target: { value: within(target).getByRole('option', { name: '備料' }).value } })
    fireEvent.click(screen.getByRole('button', { name: '加入 1 個步驟' }))

    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))
    const body = postBody()
    expect(body.steps).toEqual([
      { body: '看', kind: 'step' },
      { body: '切', kind: 'step' },
    ])
    expect(body.step_groups).toEqual([
      { name: '收尾', steps: [{ body: '醃', kind: 'step' }] },
      { step_group_id: 1, steps: [{ body: '擺盤', kind: 'step' }] },
    ])
  })

  it('gives each step a kind, numbers only ordinary steps through every group, and saves the kinds', async () => {
    handler = (call) =>
      call.url === '/api/vocabularies/fixed'
        ? json({
            dish_kinds: [{ value: 'dish', label: '料理' }],
            step_kinds: [
              { value: 'step', label: '步驟' },
              { value: 'optional', label: '可省略' },
              { value: 'note', label: '備註' },
            ],
          })
        : groupData(call)
    wrap(<AppRoutes />, '/edit/recipes/new')
    await chooseNewDish('麻婆豆腐')
    const steps = area('步驟')

    fireEvent.click(within(steps).getByRole('button', { name: '＋ 加分組' }))
    fireEvent.click(await within(steps).findByRole('button', { name: '＋ 備料' }))
    fireEvent.click(within(steps).getByRole('button', { name: '＋ 加一個步驟' }))
    fireEvent.change(screen.getByRole('textbox', { name: '步驟 1' }), { target: { value: '看' } })
    fireEvent.click(within(steps).getByRole('button', { name: '＋ 加一個步驟' }))
    fireEvent.change(screen.getByRole('textbox', { name: '步驟 2' }), { target: { value: '可加蔥' } })
    fireEvent.click(within(steps).getByRole('button', { name: '＋ 加一個步驟到「備料」' }))
    fireEvent.change(screen.getByRole('textbox', { name: '步驟 3' }), { target: { value: '小心油' } })
    fireEvent.click(within(steps).getByRole('button', { name: '＋ 加一個步驟到「備料」' }))
    fireEvent.change(screen.getByRole('textbox', { name: '步驟 4' }), { target: { value: '切' } })

    // A new row is an ordinary step.
    const kind = (n) => screen.getByRole('group', { name: `步驟 ${n} 的種類` })
    expect(within(kind(2)).getByRole('button', { name: '步驟' }).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(within(kind(2)).getByRole('button', { name: '可省略' }))
    fireEvent.click(within(kind(3)).getByRole('button', { name: '備註' }))
    expect(within(kind(2)).getByRole('button', { name: '可省略' }).getAttribute('aria-pressed')).toBe('true')

    // The visible number skips the optional step and the note, across the
    // group's edge; the accessible names keep their running index.
    const shown = [1, 2, 3, 4].map(
      (n) => within(screen.getByRole('group', { name: `步驟 ${n}` })).queryByTestId('step-number')?.textContent ?? '',
    )
    expect(shown).toEqual(['1', '', '', '2'])

    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))
    const body = postBody()
    expect(body.steps).toEqual([
      { body: '看', kind: 'step' },
      { body: '可加蔥', kind: 'optional' },
    ])
    expect(body.step_groups).toEqual([
      {
        step_group_id: 1,
        steps: [
          { body: '小心油', kind: 'note' },
          { body: '切', kind: 'step' },
        ],
      },
    ])
  })

  it('takes a typed name that is a 設定 value as that value, and removing a group keeps its rows', async () => {
    handler = groupData
    wrap(<AppRoutes />, '/edit/recipes/new')
    await chooseNewDish('湯')
    const lines = area('材料')

    fireEvent.click(within(lines).getByRole('button', { name: '＋ 加分組' }))
    await within(lines).findByRole('button', { name: '＋ 主料' })
    fireEvent.change(within(lines).getByLabelText('自訂分組名稱'), { target: { value: ' sauce ' } })
    fireEvent.click(within(lines).getByRole('button', { name: '加入' }))
    expect(screen.getByLabelText('材料分組 1 名稱').value).toBe('Sauce')

    fireEvent.click(within(lines).getByRole('button', { name: '＋ 加一行材料到「Sauce」' }))
    fireEvent.change(screen.getByRole('combobox', { name: '材料 1' }), { target: { value: '薑' } })
    fireEvent.click(await screen.findByRole('option', { name: /^薑/ }))

    fireEvent.click(within(lines).getByRole('button', { name: '＋ 加分組' }))
    fireEvent.click(within(lines).getByRole('button', { name: '＋ 主料' }))
    // Renaming the header to a name that is no 設定 value makes it a one-off.
    fireEvent.change(screen.getByLabelText('材料分組 2 名稱'), { target: { value: '主料們' } })

    expect(within(lines).getByText(/移除分組時，裡面的項目會移到最上面的不分組區，不會刪掉/)).toBeTruthy()
    fireEvent.click(within(lines).getByRole('button', { name: '移除材料分組「Sauce」' }))
    expect(screen.queryByRole('region', { name: '材料分組「Sauce」' })).toBeNull()
    expect(within(lines).getByText('薑')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))
    const body = postBody()
    expect(body.lines).toEqual([{ amount: null, note: null, is_optional: false, ingredient_id: 1 }])
    expect(body.line_groups).toEqual([{ name: '主料們', lines: [] }])
  })

  it('loads a saved recipe into its groups and sends them back unchanged', async () => {
    const line = (id, ingredientId) => ({
      id,
      position: id,
      ingredient: { id: ingredientId, display_name: `食材${ingredientId}`, needs_detail: false },
      sub_dish: null,
      amount: null,
      note: null,
      is_optional: false,
    })
    const RECIPE = {
      id: 5,
      display_name: '麻婆豆腐',
      name: null,
      dish: { id: 40, display_name: '麻婆豆腐', kind: 'dish', course: null, region: null, labels: [], serves_as: [] },
      status: { id: 1, display_name: '想試' },
      sources: [],
      lines: [line(0, 1)],
      line_groups: [
        { id: 3, position: 0, group: { id: 11, display_name: '主料' }, name: null, display_name: '主料', lines: [line(1, 2)] },
      ],
      steps: [],
      step_groups: [{ id: 4, position: 0, group: null, name: '收尾', display_name: '收尾', steps: [] }],
      methods: [],
      equipment: [],
      images: [],
      other_recipes: [],
      written_up: true,
    }
    handler = (call) =>
      call.url === '/api/recipes/5' || call.method === 'PATCH' ? json(RECIPE) : groupData(call)
    wrap(<AppRoutes />, '/edit/recipes/5')
    expect(await screen.findByRole('region', { name: '材料分組「主料」' })).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/5'))
    const body = calls.find((c) => c.method === 'PATCH').body
    expect(body.dish_id).toBe(40)
    expect(body.lines).toEqual([{ amount: null, note: null, is_optional: false, ingredient_id: 1 }])
    expect(body.line_groups).toEqual([
      { line_group_id: 11, lines: [{ amount: null, note: null, is_optional: false, ingredient_id: 2 }] },
    ])
    expect(body.steps).toEqual([])
    expect(body.step_groups).toEqual([{ name: '收尾', steps: [] }])
  })
})

describe('RecipeForm 常用食材', () => {
  const COMMON = [
    { ingredient: { id: 1, display_name: '蒜', needs_detail: false }, sort_order: 0 },
    { ingredient: { id: 2, display_name: '薑', needs_detail: true }, sort_order: 1 },
  ]
  const LINE_GROUPS = [
    { id: 11, display_name: '主料', name_cn: '主料', name_en: null, sort_order: 10, usage_count: 0 },
  ]
  const commonData =
    (common) =>
    ({ url, method }) => {
      if (url === '/api/common-ingredients') return json(common)
      if (url === '/api/line-groups') return json(LINE_GROUPS)
      if (url === '/api/edit/recipes' && method === 'POST') return json({ id: 42, images: [] }, 201)
      return json([])
    }
  const area = (title) => screen.getByRole('heading', { level: 2, name: title }).closest('section')
  const chips = () => screen.getByRole('group', { name: '常用食材' })

  it('appends a line for a tapped chip to the ungrouped lines, focused on its amount', async () => {
    handler = commonData(COMMON)
    wrap(<AppRoutes />, '/edit/recipes/new')
    await chooseNewDish('炒青菜')
    const lines = area('材料')

    // A group first, so "ungrouped" is a place a line could miss.
    fireEvent.click(within(lines).getByRole('button', { name: '＋ 加分組' }))
    fireEvent.click(await within(lines).findByRole('button', { name: '＋ 主料' }))

    // In list order.
    const offered = await within(chips()).findAllByRole('button')
    expect(offered.map((chip) => chip.getAttribute('aria-label'))).toEqual(['加一行「蒜」', '加一行「薑」'])

    fireEvent.click(within(chips()).getByRole('button', { name: '加一行「蒜」' }))
    const first = screen.getByRole('group', { name: '材料 1' })
    expect(within(first).getByText('蒜')).toBeTruthy()
    expect(document.activeElement).toBe(within(first).getByLabelText('份量'))
    fireEvent.change(document.activeElement, { target: { value: '3 瓣' } })

    // Used now, and still tappable: the same ingredient may be on two lines.
    const used = within(chips()).getByRole('button', { name: '加一行「蒜」（已在材料中）' })
    expect(used.getAttribute('data-used')).toBe('true')
    expect(within(chips()).getByRole('button', { name: '加一行「薑」' }).getAttribute('data-used')).toBeNull()
    fireEvent.click(used)
    const second = screen.getByRole('group', { name: '材料 2' })
    expect(document.activeElement).toBe(within(second).getByLabelText('份量'))

    // A stub chip makes a line that shows 待補.
    fireEvent.click(within(chips()).getByRole('button', { name: '加一行「薑」' }))
    expect(within(screen.getByRole('group', { name: '材料 3' })).getByText('待補')).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/recipes/42'))
    const body = calls.find((c) => c.method === 'POST' && c.url === '/api/edit/recipes').body
    expect(body.lines).toEqual([
      { amount: '3 瓣', note: null, is_optional: false, ingredient_id: 1 },
      { amount: null, note: null, is_optional: false, ingredient_id: 1 },
      { amount: null, note: null, is_optional: false, ingredient_id: 2 },
    ])
    expect(body.line_groups).toEqual([{ line_group_id: 11, lines: [] }])
  })

  it('marks a chip used when its ingredient is on a line inside a group', async () => {
    const RECIPE = {
      id: 5,
      display_name: '薑母鴨',
      name: null,
      dish: { id: 41, display_name: '薑母鴨', kind: 'dish', course: null, region: null, labels: [], serves_as: [] },
      status: { id: 1, display_name: '想試' },
      sources: [],
      lines: [],
      line_groups: [
        {
          id: 3,
          position: 0,
          group: { id: 11, display_name: '主料' },
          name: null,
          display_name: '主料',
          lines: [
            {
              id: 1,
              position: 0,
              ingredient: { id: 2, display_name: '薑', needs_detail: true },
              sub_dish: null,
              amount: '1 塊',
              note: null,
              is_optional: false,
            },
          ],
        },
      ],
      steps: [],
      step_groups: [],
      methods: [],
      equipment: [],
      images: [],
      other_recipes: [],
      written_up: true,
    }
    const data = commonData(COMMON)
    handler = (call) => (call.url === '/api/recipes/5' ? json(RECIPE) : data(call))
    wrap(<AppRoutes />, '/edit/recipes/5')
    expect(await within(await screen.findByRole('group', { name: '常用食材' })).findByRole('button', {
      name: '加一行「薑」（已在材料中）',
    })).toBeTruthy()
    expect(within(chips()).getByRole('button', { name: '加一行「蒜」' })).toBeTruthy()
  })

  it('shows no chip row at all while the list is empty', async () => {
    handler = commonData([])
    wrap(<AppRoutes />, '/edit/recipes/new')
    await screen.findByRole('combobox', { name: '料理' })
    await waitFor(() => expect(calls.some((c) => c.url === '/api/common-ingredients')).toBe(true))
    // Give the read a chance to answer before asserting absence.
    await act(async () => {})
    expect(screen.queryByRole('group', { name: '常用食材' })).toBeNull()
    expect(within(area('材料')).queryByText(/常用/)).toBeNull()
  })
})

describe('DishForm', () => {
  const FIXED = {
    dish_kinds: [
      { value: 'dish', label: '料理' },
      { value: 'sauce', label: '醬料' },
    ],
  }
  const data = ({ url, method }) => {
    if (url === '/api/vocabularies/fixed') return json(FIXED)
    if (url === '/api/recipe-courses') {
      return json([
        { id: 1, display_name: '主菜', sort_order: 10, usage_count: 0 },
        { id: 2, display_name: '湯', sort_order: 20, usage_count: 0 },
      ])
    }
    if (url === '/api/regions') return json([{ id: 3, display_name: '日式', sort_order: 30, usage_count: 0 }])
    if (url === '/api/labels') return json([{ id: 9, display_name: '下飯', dish_count: 0, usage_count: 0 }])
    if (url === '/api/edit/dishes' && method === 'POST') return json({ id: 42, images: [] }, 201)
    return json([])
  }

  it('saves the names, kind, course, region, serves-as, labels, description and aliases', async () => {
    handler = data
    wrap(<AppRoutes />, '/edit/dishes/new')
    fireEvent.change(await screen.findByLabelText('中文名'), { target: { value: '照燒醬' } })
    fireEvent.change(screen.getByLabelText('英文名'), { target: { value: 'teriyaki sauce' } })
    const kind = screen.getByRole('group', { name: '種類' })
    expect((await within(kind).findByRole('button', { name: '料理' })).getAttribute('aria-pressed')).toBe('true')
    fireEvent.click(within(kind).getByRole('button', { name: '醬料' }))
    await screen.findByRole('option', { name: '主菜' })
    fireEvent.change(screen.getByLabelText('類別'), { target: { value: '1' } })
    await screen.findByRole('option', { name: '日式' })
    fireEvent.change(screen.getByLabelText('地區'), { target: { value: '3' } })
    // The dish's own course is not offered as a serves-as.
    const servesAs = screen.getByRole('group', { name: '也可以當作' })
    expect(within(servesAs).queryByRole('button', { name: /主菜/ })).toBeNull()
    fireEvent.click(within(servesAs).getByRole('button', { name: /湯/ }))
    fireEvent.click(within(screen.getByRole('group', { name: '標籤' })).getByRole('button', { name: /下飯/ }))
    fireEvent.change(screen.getByLabelText('簡介'), { target: { value: '甜鹹' } })
    fireEvent.change(screen.getByLabelText(/別名/), { target: { value: '照燒、teriyaki' } })

    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/dishes/42'))
    const post = calls.find((c) => c.method === 'POST')
    expect(post.url).toBe('/api/edit/dishes')
    expect(post.body).toEqual({
      name_cn: '照燒醬',
      name_en: 'teriyaki sauce',
      name_alt: null,
      kind: 'sauce',
      course_id: 1,
      region_id: 3,
      serves_as_ids: [2],
      label_ids: [9],
      description: '甜鹹',
      aliases: ['照燒', 'teriyaki'],
    })
  })
})

describe('IngredientForm', () => {
  const TREE = [{ id: 1, display_name: '預設', is_fallback: true, children: [] }]

  it('refuses to save a parent that was typed but never picked', async () => {
    handler = ({ url }) => (url === '/api/ingredient-categories' ? json(TREE) : json([]))
    wrap(<AppRoutes />, '/edit/ingredients/new')
    fireEvent.change(await screen.findByLabelText('中文名'), { target: { value: '三星蔥' } })
    fireEvent.change(screen.getByRole('combobox', { name: '是哪種食材的品種' }), { target: { value: '青蔥' } })
    await waitFor(() => expect(screen.getByRole('button', { name: '儲存' }).disabled).toBe(false))
    fireEvent.click(screen.getByRole('button', { name: '儲存' }))
    expect((await screen.findByRole('alert')).textContent).toMatch(/品種.*青蔥/)
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('holds the save button until the categories it must choose from have loaded', async () => {
    let release
    handler = ({ url }) =>
      url === '/api/ingredient-categories'
        ? new Promise((resolve) => (release = () => resolve(json(TREE))))
        : json([])
    wrap(<AppRoutes />, '/edit/ingredients/new')
    const save = await screen.findByRole('button', { name: /儲存|載入中/ })
    expect(save.disabled).toBe(true)
    await act(async () => release())
    await waitFor(() => expect(screen.getByRole('button', { name: '儲存' }).disabled).toBe(false))
  })
})
