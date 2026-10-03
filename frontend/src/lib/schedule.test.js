import { describe, expect, it } from 'vitest'

import {
  addDays,
  dayForm,
  dayPayload,
  filledFields,
  isIsoDate,
  rangeLabel,
  shownWeek,
  todayIso,
  weekStart,
} from './schedule'

const SLOTS = [
  { value: 'breakfast', label: '早' },
  { value: 'lunch', label: '中' },
  { value: 'afternoon', label: '下午' },
  { value: 'dinner', label: '晚' },
]

describe('weekStart', () => {
  it.each([
    ['2026-10-03', '2026-10-03'], // a Saturday is its own week's start
    ['2026-10-04', '2026-10-03'], // Sunday
    ['2026-10-09', '2026-10-03'], // Friday, the week's last day
    ['2026-10-10', '2026-10-10'], // the next Saturday
    ['2027-01-01', '2026-12-26'], // across a year
    ['2028-03-01', '2028-02-26'], // across a leap day
  ])('%s is in the week of %s', (day, saturday) => {
    expect(weekStart(day)).toBe(saturday)
  })
})

describe('dates', () => {
  it('moves by days across months and years', () => {
    expect(addDays('2026-10-03', 14)).toBe('2026-10-17')
    expect(addDays('2026-10-03', -7)).toBe('2026-09-26')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
  })

  it('knows a real date from a malformed or impossible one', () => {
    expect(isIsoDate('2026-10-03')).toBe(true)
    expect(isIsoDate('2026-02-30')).toBe(false)
    expect(isIsoDate('2026-10-3')).toBe(false)
    expect(isIsoDate(null)).toBe(false)
  })

  it('reads today from the local calendar', () => {
    expect(todayIso(new Date(2026, 9, 3, 23, 59))).toBe('2026-10-03')
  })

  it('shows the week of ?week=, or this week when it is missing or not a date', () => {
    expect(shownWeek('2026-10-14', '2026-10-03')).toBe('2026-10-10')
    expect(shownWeek(null, '2026-10-07')).toBe('2026-10-03')
    expect(shownWeek('soon', '2026-10-07')).toBe('2026-10-03')
  })

  it('labels a range by its first and last day', () => {
    expect(rangeLabel('2026-10-03')).toBe('10/3 – 10/9')
    expect(rangeLabel('2026-10-03', 14)).toBe('10/3 – 10/16')
  })
})

const DISH = { id: 4, display_name: '咖哩', kind: 'dish' }
const RICE = { id: 5, display_name: '白飯', kind: 'dish' }

describe('the phone card', () => {
  it('lists the filled meals, 水果, the true marks and 備註, in the columns’ order', () => {
    const day = {
      to_buy: true,
      thaw_morning: false,
      thaw_noon: false,
      thaw_evening: true,
      fruit: '芭樂',
      note: '外食',
      meals: {
        breakfast: null,
        lunch: { text: null, items: [{ dish: DISH, recipe: null }] },
        afternoon: { text: null, items: [] },
        dinner: null,
      },
    }
    const fields = filledFields(day, SLOTS)
    expect(fields.map((field) => field.key)).toEqual(['lunch', 'fruit', 'marks', 'note'])
    expect(fields[2].marks).toEqual(['要買', '晚退冰'])
  })

  it('leaves the marks out when none is true', () => {
    const day = { to_buy: false, thaw_morning: false, thaw_noon: false, thaw_evening: false, meals: {} }
    expect(filledFields(day, SLOTS)).toEqual([])
  })
})

describe('dayPayload', () => {
  it('sends marks as booleans, blanks as null, empty meals as null, and items in order', () => {
    const form = dayForm(
      {
        to_buy: true,
        meals: {
          dinner: {
            text: '配飯',
            items: [
              { dish: DISH, recipe: { id: 9, display_name: 'A', dish: DISH } },
              { dish: RICE, recipe: null },
            ],
          },
        },
      },
      SLOTS,
    )
    form.fields.fruit = '  '
    form.fields.thaw_noon = true
    form.meals.lunch.text = ' 麵 '
    expect(dayPayload(form)).toEqual({
      to_buy: true,
      thaw_morning: false,
      thaw_noon: true,
      thaw_evening: false,
      fruit: null,
      note: null,
      meals: {
        breakfast: null,
        lunch: { text: '麵', items: [] },
        afternoon: null,
        dinner: {
          text: '配飯',
          items: [
            { dish_id: 4, recipe_id: 9 },
            { dish_id: 5, recipe_id: null },
          ],
        },
      },
    })
  })

  it('gives every item its own key, and starts a stored day’s marks from what is stored', () => {
    const form = dayForm({ thaw_evening: true, meals: { lunch: { text: null, items: [{ dish: DISH }, { dish: RICE }] } } }, SLOTS)
    const [a, b] = form.meals.lunch.items
    expect(a.key).not.toBe(b.key)
    expect(form.fields.thaw_evening).toBe(true)
    expect(form.fields.to_buy).toBe(false)
    expect(form.fields.fruit).toBe('')
  })

  it('drops an item whose dish was cleared, and a meal left with nothing', () => {
    const form = dayForm({ meals: { lunch: { text: null, items: [{ dish: DISH, recipe: { id: 9 } }] } } }, SLOTS)
    form.meals.lunch.items[0].dish = null
    expect(dayPayload(form).meals.lunch).toBeNull()
  })
})
