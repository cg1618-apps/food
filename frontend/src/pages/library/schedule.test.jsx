// 排程: /schedule shows two weeks from a Saturday as a table and as phone
// cards, moves a week at a time, and marks today; /edit/schedule edits each
// day in a card and saves it whole with one PUT.
//
// Today is pinned to Wednesday 2026-10-07, so this week starts on Saturday
// 2026-10-03. Only Date is faked: the fetches still resolve.
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import AppRoutes from '../../routes'

const SLOTS = [
  { value: 'breakfast', label: '早' },
  { value: 'lunch', label: '中' },
  { value: 'afternoon', label: '下午' },
  { value: 'dinner', label: '晚' },
]
const CURRY = { id: 4, display_name: '咖哩', kind: 'dish' }
const RICE = { id: 5, display_name: '白飯', kind: 'dish' }
const RECIPE = { id: 9, display_name: '日式咖哩', dish: CURRY }

// The columns after 星期幾, in the page's order.
const COLUMNS = ['早', '中', '下午', '晚', '水果', '要買?', '早退冰?', '中退冰?', '晚退冰?', '備註']

function emptyDay(date) {
  const weekday = (new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7
  return {
    date,
    weekday,
    to_buy: false,
    thaw_morning: false,
    thaw_noon: false,
    thaw_evening: false,
    fruit: null,
    note: null,
    meals: { breakfast: null, lunch: null, afternoon: null, dinner: null },
  }
}

function range(start, days) {
  const first = new Date(`${start}T00:00:00Z`)
  return Array.from({ length: days }, (_, i) => {
    const date = new Date(first)
    date.setUTCDate(first.getUTCDate() + i)
    return emptyDay(date.toISOString().slice(0, 10))
  })
}

// Monday 10/5 is filled in - two marks true, two false, and a dinner of text
// and two items; the rest of the fortnight is empty.
function schedule(start, days) {
  return range(start, days).map((day) =>
    day.date === '2026-10-05'
      ? {
          ...day,
          to_buy: true,
          thaw_evening: true,
          fruit: '芭樂',
          meals: {
            ...day.meals,
            dinner: {
              text: '配白飯',
              items: [
                { dish: CURRY, recipe: RECIPE },
                { dish: RICE, recipe: null },
              ],
            },
          },
        }
      : day,
  )
}

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

function read(call) {
  const url = new URL(call.url, 'http://x')
  if (call.method === 'GET' && url.pathname === '/api/schedule') {
    return json(schedule(url.searchParams.get('start'), Number(url.searchParams.get('days'))))
  }
  if (url.pathname === '/api/vocabularies/fixed') return json({ meal_slots: SLOTS })
  if (url.pathname === '/api/edit/session') return new Response(null, { status: 204 })
  if (url.pathname === '/api/dishes/4') return json({ ...CURRY, recipes: [RECIPE, { id: 10, display_name: '印度咖哩' }] })
  if (url.pathname === '/api/dishes/5') return json({ ...RICE, recipes: [] })
  if (url.pathname === '/api/dishes') {
    const q = url.searchParams.get('q') ?? ''
    return json([CURRY, RICE].filter((dish) => dish.display_name.includes(q)))
  }
  return null
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['Date'] })
  vi.setSystemTime(new Date(2026, 9, 7, 12, 0))
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
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

const scheduleReads = () => calls.filter((c) => c.method === 'GET' && c.url.startsWith('/api/schedule'))
const location = () => screen.getByTestId('location').textContent
const puts = () => calls.filter((c) => c.method === 'PUT')

describe('the schedule page', () => {
  it('asks for two weeks from this week’s Saturday and shows them', async () => {
    renderAt('/schedule')
    const tables = await screen.findAllByRole('table')
    expect(scheduleReads()[0].url).toBe('/api/schedule?start=2026-10-03&days=14')
    expect(tables.map((t) => t.getAttribute('aria-label'))).toEqual(['10/3 – 10/9', '10/10 – 10/16'])
    expect(screen.getByText('10/3 – 10/16（六–五）')).toBeTruthy()
  })

  it('draws the columns meals first, then 水果, the marks and 備註', async () => {
    renderAt('/schedule')
    const [week] = await screen.findAllByRole('table')
    const headers = within(week).getAllByRole('columnheader').map((th) => th.textContent)
    expect(headers).toEqual(['星期幾', ...COLUMNS])
    const rows = within(week).getAllByRole('row').slice(1)
    expect(rows.map((row) => within(row).getByRole('rowheader').textContent)).toEqual([
      '星期六 10/3',
      '星期日 10/4',
      '星期一 10/5',
      '星期二 10/6',
      '星期三 10/7',
      '星期四 10/8',
      '星期五 10/9',
    ])
  })

  it('ticks a true mark and leaves a false one empty', async () => {
    renderAt('/schedule')
    const [week] = await screen.findAllByRole('table')
    const monday = within(week).getAllByRole('row')[3]
    const cells = Object.fromEntries(
      within(monday)
        .getAllByRole('cell')
        .map((td, i) => [COLUMNS[i], td.textContent]),
    )
    expect(cells['水果']).toBe('芭樂')
    expect(cells['要買?']).toBe('✓')
    expect(cells['早退冰?']).toBe('')
    expect(cells['中退冰?']).toBe('')
    expect(cells['晚退冰?']).toBe('✓')
    // An empty day ticks nothing.
    const sunday = within(week).getAllByRole('row')[2]
    expect(within(sunday).queryByText('✓')).toBeNull()
  })

  it('shows a meal’s text, then each item on its own line, linked', async () => {
    renderAt('/schedule')
    const [week] = await screen.findAllByRole('table')
    const monday = within(week).getAllByRole('row')[3]
    const dinner = within(monday).getAllByRole('cell')[COLUMNS.indexOf('晚')]
    const lines = Array.from(dinner.querySelectorAll('p')).map((p) => p.textContent)
    expect(lines).toEqual(['配白飯', '咖哩 · 日式咖哩', '白飯'])
    expect(within(dinner).getByRole('link', { name: '咖哩' }).getAttribute('href')).toBe('/dishes/4')
    expect(within(dinner).getByRole('link', { name: '日式咖哩' }).getAttribute('href')).toBe('/recipes/9')
    expect(within(dinner).getByRole('link', { name: '白飯' }).getAttribute('href')).toBe('/dishes/5')
  })

  it('marks today', async () => {
    renderAt('/schedule')
    const [week] = await screen.findAllByRole('table')
    const today = within(week)
      .getAllByRole('row')
      .filter((row) => row.getAttribute('aria-current') === 'date')
    expect(today.map((row) => within(row).getByRole('rowheader').textContent)).toEqual(['星期三 10/7'])
  })

  it('shows a phone card listing only what is filled, a chip per true mark', async () => {
    renderAt('/schedule')
    const [week] = await screen.findAllByRole('list', { name: '10/3 – 10/9' })
    const monday = within(week).getByRole('listitem', { name: '星期一 10/5' })
    const terms = within(monday).getAllByRole('term').map((dt) => dt.textContent)
    expect(terms).toEqual(['晚', '水果'])
    const chips = within(within(monday).getByRole('list', { name: '標記' }))
      .getAllByRole('listitem')
      .map((li) => li.textContent)
    expect(chips).toEqual(['要買', '晚退冰'])
    // The chips sit after 水果, as the columns do.
    const fruit = within(monday).getByText('水果')
    const marks = within(monday).getByRole('list', { name: '標記' })
    expect(fruit.compareDocumentPosition(marks) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()

    const sunday = within(week).getByRole('listitem', { name: '星期日 10/4' })
    expect(within(sunday).queryAllByRole('term')).toEqual([])
    expect(within(sunday).queryByRole('list', { name: '標記' })).toBeNull()
  })

  it('moves a week at a time, by the Saturday in ?week=', async () => {
    renderAt('/schedule?week=2026-10-14')
    await screen.findAllByRole('table')
    // A Wednesday in the URL is read as its week's Saturday.
    expect(scheduleReads()[0].url).toBe('/api/schedule?start=2026-10-10&days=14')
    expect(screen.getByRole('link', { name: '← 上週' }).getAttribute('href')).toBe('/schedule?week=2026-10-03')
    expect(screen.getByRole('link', { name: '下週 →' }).getAttribute('href')).toBe('/schedule?week=2026-10-17')
    expect(screen.getByRole('link', { name: '本週' }).getAttribute('href')).toBe('/schedule')
    expect(screen.getByRole('link', { name: '編輯' }).getAttribute('href')).toBe('/edit/schedule?week=2026-10-10')

    fireEvent.click(screen.getByRole('link', { name: '下週 →' }))
    await waitFor(() => expect(scheduleReads().at(-1).url).toBe('/api/schedule?start=2026-10-17&days=14'))
    expect(location()).toBe('/schedule?week=2026-10-17')
  })
})

describe('the schedule edit page', () => {
  const card = async (name) => screen.findByRole('listitem', { name })

  it('lays a day out in the columns’ order', async () => {
    renderAt('/edit/schedule')
    const monday = await card('星期一 10/5')
    const groups = within(monday)
      .getAllByRole('group')
      .map((group) => group.getAttribute('aria-label'))
    expect(groups).toEqual(['早', '中', '下午', '晚', '其他'])
    const others = within(monday).getByRole('group', { name: '其他' })
    const controls = Array.from(others.querySelectorAll('input')).map((input) => input.getAttribute('aria-label'))
    expect(controls).toEqual(['水果', '要買?', '早退冰?', '中退冰?', '晚退冰?', '備註'])
  })

  it('fills each day from what is stored, marks as checkboxes', async () => {
    renderAt('/edit/schedule')
    const monday = await card('星期一 10/5')
    expect(within(monday).getByRole('checkbox', { name: '要買?' }).checked).toBe(true)
    expect(within(monday).getByRole('checkbox', { name: '早退冰?' }).checked).toBe(false)
    expect(within(monday).getByRole('checkbox', { name: '晚退冰?' }).checked).toBe(true)
    expect(within(monday).getByRole('textbox', { name: '水果' }).value).toBe('芭樂')
    const dinner = within(monday).getByRole('group', { name: '晚' })
    expect(within(dinner).getByRole('textbox', { name: '晚 內容' }).value).toBe('配白飯')
    expect(within(dinner).getByText('咖哩')).toBeTruthy()
    expect(within(dinner).getByText('白飯')).toBeTruthy()
    const first = within(dinner).getByRole('combobox', { name: '晚 料理 1 食譜' })
    await waitFor(() => expect(first.value).toBe('9'))
    expect(within(first).getAllByRole('option').map((option) => option.textContent)).toEqual([
      '不指定食譜',
      '日式咖哩',
      '印度咖哩',
    ])
    expect(within(dinner).getByRole('combobox', { name: '晚 料理 2 食譜' }).value).toBe('')
  })

  it('saves a day whole, with one PUT, and says it saved', async () => {
    handler = (call) => (call.method === 'PUT' ? json(emptyDay('2026-10-05')) : null)
    renderAt('/edit/schedule')
    const monday = await card('星期一 10/5')
    fireEvent.change(within(monday).getByRole('textbox', { name: '水果' }), { target: { value: ' ' } })
    fireEvent.click(within(monday).getByRole('checkbox', { name: '要買?' }))
    fireEvent.click(within(monday).getByRole('checkbox', { name: '早退冰?' }))
    fireEvent.change(within(monday).getByRole('textbox', { name: '早 內容' }), { target: { value: '吐司' } })
    const dinner = within(monday).getByRole('group', { name: '晚' })
    const first = within(dinner).getByRole('combobox', { name: '晚 料理 1 食譜' })
    await waitFor(() => expect(within(first).getAllByRole('option')).toHaveLength(3))
    fireEvent.change(first, { target: { value: '10' } })
    expect(within(monday).getByText('未儲存')).toBeTruthy()
    // The week cannot be left while a day is unsaved.
    expect(screen.getByRole('button', { name: '下週 →' }).disabled).toBe(true)

    fireEvent.click(within(monday).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(puts()[0]).toEqual({
      url: '/api/edit/schedule/2026-10-05',
      method: 'PUT',
      body: {
        to_buy: false,
        thaw_morning: true,
        thaw_noon: false,
        thaw_evening: true,
        fruit: null,
        note: null,
        meals: {
          breakfast: { text: '吐司', items: [] },
          lunch: null,
          afternoon: null,
          dinner: {
            text: '配白飯',
            items: [
              { dish_id: 4, recipe_id: 10 },
              { dish_id: 5, recipe_id: null },
            ],
          },
        },
      },
    })
    expect(await within(monday).findByText('已儲存')).toBeTruthy()
    expect(screen.getByRole('link', { name: '下週 →' })).toBeTruthy()
  })

  it('removes an item, and adds dishes one after another', async () => {
    handler = (call) => (call.method === 'PUT' ? json(emptyDay('2026-10-05')) : null)
    renderAt('/edit/schedule')
    const monday = await card('星期一 10/5')
    const dinner = within(monday).getByRole('group', { name: '晚' })
    fireEvent.click(within(dinner).getByRole('button', { name: '移除 晚 料理 1' }))
    expect(within(dinner).queryByText('咖哩')).toBeNull()

    const add = within(dinner).getByRole('combobox', { name: '晚 加料理' })
    fireEvent.change(add, { target: { value: '咖' } })
    fireEvent.click(await within(dinner).findByRole('option', { name: /咖哩/ }))
    // The box clears and stays, for the next dish.
    expect(within(dinner).getByRole('combobox', { name: '晚 加料理' }).value).toBe('')
    const recipe = within(dinner).getByRole('combobox', { name: '晚 料理 2 食譜' })
    await waitFor(() => expect(within(recipe).getAllByRole('option')).toHaveLength(3))
    fireEvent.change(recipe, { target: { value: '9' } })

    fireEvent.click(within(monday).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(puts()[0].body.meals.dinner).toEqual({
      text: '配白飯',
      items: [
        { dish_id: 5, recipe_id: null },
        { dish_id: 4, recipe_id: 9 },
      ],
    })
  })

  it('picks a dish from the library for an empty meal', async () => {
    handler = (call) => (call.method === 'PUT' ? json(emptyDay('2026-10-04')) : null)
    renderAt('/edit/schedule')
    const sunday = await card('星期日 10/4')
    const lunch = within(sunday).getByRole('group', { name: '中' })
    fireEvent.change(within(lunch).getByRole('combobox', { name: '中 加料理' }), { target: { value: '咖' } })
    fireEvent.click(await within(lunch).findByRole('option', { name: /咖哩/ }))
    fireEvent.click(within(sunday).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(puts()).toHaveLength(1))
    expect(puts()[0].body.meals.lunch).toEqual({ text: null, items: [{ dish_id: 4, recipe_id: null }] })
  })

  it('changes an item’s dish in place with 更換', async () => {
    handler = (call) => (call.method === 'PUT' ? json(emptyDay('2026-10-05')) : null)
    renderAt('/edit/schedule')
    const monday = await card('星期一 10/5')
    const dinner = within(monday).getByRole('group', { name: '晚' })
    fireEvent.click(within(dinner).getAllByRole('button', { name: '更換' })[0])
    fireEvent.change(within(dinner).getByRole('combobox', { name: '晚 料理 1' }), { target: { value: '白' } })
    fireEvent.click(await within(dinner).findByRole('option', { name: /白飯/ }))
    fireEvent.click(within(monday).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(puts()).toHaveLength(1))
    // The new dish keeps the item's place, and the old dish's recipe goes.
    expect(puts()[0].body.meals.dinner.items).toEqual([
      { dish_id: 5, recipe_id: null },
      { dish_id: 5, recipe_id: null },
    ])
  })

  it('refuses to save a dish typed but not picked, and sends nothing', async () => {
    renderAt('/edit/schedule')
    const sunday = await card('星期日 10/4')
    fireEvent.change(within(sunday).getByRole('combobox', { name: '中 加料理' }), { target: { value: '咖' } })
    fireEvent.click(within(sunday).getByRole('button', { name: '儲存' }))
    expect(await within(sunday).findByRole('alert')).toBeTruthy()
    expect(puts()).toHaveLength(0)
  })

  it('shows the server’s refusal on the day and keeps what was typed', async () => {
    handler = (call) =>
      call.method === 'PUT' ? json({ detail: 'The 晚 meal names the same dish and recipe twice.' }, 422) : null
    renderAt('/edit/schedule')
    const monday = await card('星期一 10/5')
    fireEvent.change(within(monday).getByRole('textbox', { name: '備註' }), { target: { value: '外食' } })
    fireEvent.click(within(monday).getByRole('button', { name: '儲存' }))
    expect((await within(monday).findByRole('alert')).textContent).toContain('the same dish and recipe twice')
    expect(within(monday).getByRole('textbox', { name: '備註' }).value).toBe('外食')
    expect(within(monday).getByText('未儲存')).toBeTruthy()
  })
})
