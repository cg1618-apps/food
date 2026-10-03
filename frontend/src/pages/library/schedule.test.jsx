// 排程: /schedule shows two weeks from a Saturday as the sheet's table and as
// phone cards, moves a week at a time, and marks today; /edit/schedule edits
// each day in a card and saves it whole with one PUT.
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
const RECIPE = { id: 9, display_name: '日式咖哩', dish: CURRY }

function emptyDay(date) {
  const weekday = (new Date(`${date}T00:00:00Z`).getUTCDay() + 6) % 7
  return {
    date,
    weekday,
    to_buy: null,
    thaw_morning: null,
    thaw_noon: null,
    thaw_evening: null,
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

// Monday 10/5 is filled in; the rest of the fortnight is empty.
function schedule(start, days) {
  return range(start, days).map((day) =>
    day.date === '2026-10-05'
      ? {
          ...day,
          to_buy: '雞腿',
          fruit: '芭樂',
          meals: { ...day.meals, dinner: { text: '配白飯', dish: CURRY, recipe: RECIPE } },
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
  if (url.pathname === '/api/dishes') return json([CURRY])
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

describe('the schedule page', () => {
  it('asks for two weeks from this week’s Saturday and shows them', async () => {
    renderAt('/schedule')
    const tables = await screen.findAllByRole('table')
    expect(scheduleReads()[0].url).toBe('/api/schedule?start=2026-10-03&days=14')
    expect(tables.map((t) => t.getAttribute('aria-label'))).toEqual(['10/3 – 10/9', '10/10 – 10/16'])
    expect(screen.getByText('10/3 – 10/16（六–五）')).toBeTruthy()
  })

  it('draws the sheet’s columns in the sheet’s order, with meal links', async () => {
    renderAt('/schedule')
    const [week] = await screen.findAllByRole('table')
    const headers = within(week).getAllByRole('columnheader').map((th) => th.textContent)
    expect(headers).toEqual(['星期幾', '要買?', '早退冰?', '中退冰?', '早', '中', '下午', '晚', '晚退冰?', '水果', '備註'])
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
    const monday = rows[2]
    const cells = within(monday).getAllByRole('cell').map((td) => td.textContent)
    expect(cells[0]).toBe('雞腿')
    expect(cells[6]).toContain('配白飯')
    expect(cells[8]).toBe('芭樂')
    expect(within(monday).getByRole('link', { name: '咖哩' }).getAttribute('href')).toBe('/dishes/4')
    expect(within(monday).getByRole('link', { name: '食譜：日式咖哩' }).getAttribute('href')).toBe('/recipes/9')
  })

  it('marks today', async () => {
    renderAt('/schedule')
    const [week] = await screen.findAllByRole('table')
    const today = within(week)
      .getAllByRole('row')
      .filter((row) => row.getAttribute('aria-current') === 'date')
    expect(today.map((row) => within(row).getByRole('rowheader').textContent)).toEqual(['星期三 10/7'])
  })

  it('shows a phone card listing only the filled fields', async () => {
    renderAt('/schedule')
    const [week] = await screen.findAllByRole('list', { name: '10/3 – 10/9' })
    const monday = within(week).getByRole('listitem', { name: '星期一 10/5' })
    const terms = within(monday).getAllByRole('term').map((dt) => dt.textContent)
    expect(terms).toEqual(['要買?', '晚', '水果'])
    const sunday = within(week).getByRole('listitem', { name: '星期日 10/4' })
    expect(within(sunday).queryAllByRole('term')).toEqual([])
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

  it('fills each day from what is stored', async () => {
    renderAt('/edit/schedule')
    const monday = await card('星期一 10/5')
    expect(within(monday).getByRole('textbox', { name: '要買?' }).value).toBe('雞腿')
    const dinner = within(monday).getByRole('group', { name: '晚' })
    expect(within(dinner).getByRole('textbox', { name: '晚 內容' }).value).toBe('配白飯')
    expect(within(dinner).getByText('咖哩')).toBeTruthy()
    await waitFor(() => expect(within(dinner).getByRole('combobox', { name: '晚 食譜' }).value).toBe('9'))
    expect(
      within(within(dinner).getByRole('combobox', { name: '晚 食譜' }))
        .getAllByRole('option')
        .map((option) => option.textContent),
    ).toEqual(['不指定食譜', '日式咖哩', '印度咖哩'])
  })

  it('saves a day whole, with one PUT, and says it saved', async () => {
    handler = (call) => (call.method === 'PUT' ? json(emptyDay('2026-10-05')) : null)
    renderAt('/edit/schedule')
    const monday = await card('星期一 10/5')
    fireEvent.change(within(monday).getByRole('textbox', { name: '水果' }), { target: { value: ' ' } })
    fireEvent.change(within(monday).getByRole('textbox', { name: '早 內容' }), { target: { value: '吐司' } })
    const dinner = within(monday).getByRole('group', { name: '晚' })
    await waitFor(() => expect(within(dinner).getAllByRole('option')).toHaveLength(3))
    fireEvent.change(within(dinner).getByRole('combobox', { name: '晚 食譜' }), { target: { value: '10' } })
    expect(within(monday).getByText('未儲存')).toBeTruthy()
    // The week cannot be left while a day is unsaved.
    expect(screen.getByRole('button', { name: '下週 →' }).disabled).toBe(true)

    fireEvent.click(within(monday).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(calls.filter((c) => c.method === 'PUT')).toHaveLength(1))
    expect(calls.find((c) => c.method === 'PUT')).toEqual({
      url: '/api/edit/schedule/2026-10-05',
      method: 'PUT',
      body: {
        to_buy: '雞腿',
        thaw_morning: null,
        thaw_noon: null,
        thaw_evening: null,
        fruit: null,
        note: null,
        meals: {
          breakfast: { text: '吐司', dish_id: null, recipe_id: null },
          lunch: null,
          afternoon: null,
          dinner: { text: '配白飯', dish_id: 4, recipe_id: 10 },
        },
      },
    })
    expect(await within(monday).findByText('已儲存')).toBeTruthy()
    expect(screen.getByRole('link', { name: '下週 →' })).toBeTruthy()
  })

  it('picks a dish from the library for a meal', async () => {
    handler = (call) => (call.method === 'PUT' ? json(emptyDay('2026-10-04')) : null)
    renderAt('/edit/schedule')
    const sunday = await card('星期日 10/4')
    const lunch = within(sunday).getByRole('group', { name: '中' })
    fireEvent.change(within(lunch).getByRole('combobox', { name: '中 料理' }), { target: { value: '咖' } })
    fireEvent.click(await within(lunch).findByRole('option', { name: /咖哩/ }))
    fireEvent.click(within(sunday).getByRole('button', { name: '儲存' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PUT')).toBe(true))
    expect(calls.find((c) => c.method === 'PUT').body.meals.lunch).toEqual({
      text: null,
      dish_id: 4,
      recipe_id: null,
    })
  })

  it('refuses to save a dish typed but not picked, and sends nothing', async () => {
    renderAt('/edit/schedule')
    const sunday = await card('星期日 10/4')
    fireEvent.change(within(sunday).getByRole('combobox', { name: '中 料理' }), { target: { value: '咖' } })
    fireEvent.click(within(sunday).getByRole('button', { name: '儲存' }))
    expect(await within(sunday).findByRole('alert')).toBeTruthy()
    expect(calls.some((c) => c.method === 'PUT')).toBe(false)
  })

  it('shows the server’s refusal on the day and keeps what was typed', async () => {
    handler = (call) =>
      call.method === 'PUT' ? json({ detail: 'The 晚 recipe is not a recipe of that meal’s dish.' }, 422) : null
    renderAt('/edit/schedule')
    const monday = await card('星期一 10/5')
    fireEvent.change(within(monday).getByRole('textbox', { name: '備註' }), { target: { value: '外食' } })
    fireEvent.click(within(monday).getByRole('button', { name: '儲存' }))
    expect((await within(monday).findByRole('alert')).textContent).toContain('not a recipe of that meal')
    expect(within(monday).getByRole('textbox', { name: '備註' }).value).toBe('外食')
    expect(within(monday).getByText('未儲存')).toBeTruthy()
  })
})
