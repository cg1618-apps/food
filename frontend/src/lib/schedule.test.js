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

describe('the phone card', () => {
  it('lists only the filled fields, in the sheet order', () => {
    const day = {
      to_buy: '雞腿',
      thaw_morning: null,
      thaw_noon: null,
      thaw_evening: '豬肉',
      fruit: null,
      note: null,
      meals: { breakfast: null, lunch: { text: null, dish: DISH, recipe: null }, afternoon: null, dinner: null },
    }
    expect(filledFields(day, SLOTS).map((field) => field.label)).toEqual(['要買?', '中', '晚退冰?'])
  })
})

describe('dayPayload', () => {
  it('sends blanks as null, empty meals as null, and a picked recipe with its dish', () => {
    const form = dayForm(
      {
        to_buy: '雞腿',
        meals: { dinner: { text: '配飯', dish: DISH, recipe: { id: 9, display_name: 'A', dish: DISH } } },
      },
      SLOTS,
    )
    form.fields.fruit = '  '
    form.meals.lunch.text = ' 麵 '
    expect(dayPayload(form)).toEqual({
      to_buy: '雞腿',
      thaw_morning: null,
      thaw_noon: null,
      thaw_evening: null,
      fruit: null,
      note: null,
      meals: {
        breakfast: null,
        lunch: { text: '麵', dish_id: null, recipe_id: null },
        afternoon: null,
        dinner: { text: '配飯', dish_id: 4, recipe_id: 9 },
      },
    })
  })

  it('drops a recipe whose dish was cleared', () => {
    const form = dayForm({ meals: { lunch: { text: null, dish: DISH, recipe: { id: 9 } } } }, SLOTS)
    form.meals.lunch.dish = null
    expect(dayPayload(form).meals.lunch).toBeNull()
  })
})
