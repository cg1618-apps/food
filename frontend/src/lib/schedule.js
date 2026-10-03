// Frontend: the weekly schedule's dates, columns and save payload.
//
// A week runs Saturday to Friday, as the owner's sheet does, and a page shows
// two of them - this week and next. Dates travel as 'YYYY-MM-DD' strings, the
// API's own form, and are calendar dates with no time: the arithmetic here is
// done in UTC so a daylight-saving change can never move a day, and only
// `todayIso` reads the local clock - the browser's date is the owner's.
import { blankToNull } from './rowList'

export const WEEK_DAYS = 7
export const SHOWN_DAYS = 14 // this week and next, as the sheet
const SATURDAY = 6 // Date#getUTCDay(): Sunday 0 ... Saturday 6

// The day's plain fields, in the page's column order after the four meals:
// 水果, the four marks, 備註. A mark is true or false and is shown only when
// true - a ✓ in the table, a chip on the phone card, `chip` its word there.
// The order is the owner's, and differs from the sheet's on purpose
// (docs/notes/decisions.md, "The weekly schedule").
export const DAY_FIELDS = [
  { key: 'fruit', label: '水果', kind: 'text' },
  { key: 'to_buy', label: '要買?', kind: 'mark', chip: '要買' },
  { key: 'thaw_morning', label: '早退冰?', kind: 'mark', chip: '早退冰' },
  { key: 'thaw_noon', label: '中退冰?', kind: 'mark', chip: '中退冰' },
  { key: 'thaw_evening', label: '晚退冰?', kind: 'mark', chip: '晚退冰' },
  { key: 'note', label: '備註', kind: 'text' },
]
export const MARKS = DAY_FIELDS.filter((field) => field.kind === 'mark')

// By the API's `weekday`: Monday 0 ... Sunday 6, as Python's date.weekday().
const WEEKDAY_NAMES = ['星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']
const WEEKDAY_SHORT = ['一', '二', '三', '四', '五', '六', '日']

const ISO_DATE = /^(\d{4})-(\d{2})-(\d{2})$/

function toUtc(iso) {
  const match = ISO_DATE.exec(iso ?? '')
  if (!match) return null
  const [, y, m, d] = match.map(Number)
  const date = new Date(Date.UTC(y, m - 1, d))
  // Refuses 2026-02-30 rather than rolling it into March.
  return date.getUTCMonth() === m - 1 && date.getUTCDate() === d ? date : null
}

function fromUtc(date) {
  return date.toISOString().slice(0, 10)
}

/** Whether `text` is a real 'YYYY-MM-DD' date. */
export function isIsoDate(text) {
  return toUtc(text) !== null
}

/** `iso` moved by `days` (negative goes back). */
export function addDays(iso, days) {
  const date = toUtc(iso)
  date.setUTCDate(date.getUTCDate() + days)
  return fromUtc(date)
}

/** The Saturday on or before `iso` - the first day of its week. */
export function weekStart(iso) {
  const date = toUtc(iso)
  return addDays(iso, -((date.getUTCDay() - SATURDAY + 7) % 7))
}

/** Today in the browser's own calendar, as 'YYYY-MM-DD'. */
export function todayIso(now = new Date()) {
  const pad = (n) => String(n).padStart(2, '0')
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`
}

/**
 * The Saturday a page shows from: `?week=` when it is a real date (moved to
 * its week's Saturday, so a hand-typed Tuesday still lands on a week), else
 * this week's.
 */
export function shownWeek(param, today) {
  return weekStart(isIsoDate(param) ? param : today)
}

/** '10/3' - a date as the page heads things with it. */
export function shortDate(iso) {
  const date = toUtc(iso)
  return `${date.getUTCMonth() + 1}/${date.getUTCDate()}`
}

/** '10/3 – 10/9': the range `days` long from `start`. */
export function rangeLabel(start, days = WEEK_DAYS) {
  return `${shortDate(start)} – ${shortDate(addDays(start, days - 1))}`
}

export function weekdayName(weekday) {
  return WEEKDAY_NAMES[weekday]
}

export function weekdayShort(weekday) {
  return WEEKDAY_SHORT[weekday]
}

/** Whether a meal from the API holds anything. */
export function mealFilled(meal) {
  return Boolean(meal && (meal.text || meal.items?.length))
}

/**
 * What the phone card lists, in column order: the filled meals, 水果, one
 * `marks` entry holding the chip words of the true marks (left out when none
 * is), and 備註.
 */
export function filledFields(day, slots) {
  const meals = slots
    .filter(({ value }) => mealFilled(day.meals?.[value]))
    .map(({ value, label }) => ({ key: value, label, meal: day.meals[value] }))
  const rest = []
  const marks = MARKS.filter(({ key }) => day[key]).map(({ chip }) => chip)
  for (const field of DAY_FIELDS) {
    if (field.kind === 'text' && day[field.key]) rest.push({ ...field, value: day[field.key] })
    // The marks sit where the first of them is, as their columns do.
    if (field === MARKS[0] && marks.length) rest.push({ key: 'marks', marks })
  }
  return [...meals, ...rest]
}

let nextItemKey = 0

/** A new item for the edit card: a dish (or none yet, while 更換 searches)
 * and one of its recipes, with a key of its own for React. */
export function newItem(dish = null, recipeId = null) {
  nextItemKey += 1
  return { key: nextItemKey, dish, recipeId }
}

/** A day from the API as the edit card's state: a text field a string, a
 * mark a boolean, every meal { text, items: [{ key, dish, recipeId }] }. */
export function dayForm(day, slots) {
  return {
    fields: Object.fromEntries(
      DAY_FIELDS.map(({ key, kind }) => [
        key,
        kind === 'mark' ? Boolean(day?.[key]) : (day?.[key] ?? ''),
      ]),
    ),
    meals: Object.fromEntries(
      slots.map(({ value }) => {
        const meal = day?.meals?.[value]
        return [
          value,
          {
            text: meal?.text ?? '',
            items: (meal?.items ?? []).map((item) => newItem(item.dish, item.recipe?.id ?? null)),
          },
        ]
      }),
    ),
  }
}

/**
 * The edit card's state as the PUT body, which replaces the whole day: a mark
 * is true or false, blank text is null, an item with no dish (更換 pressed
 * and nothing picked) is left out, and a meal with nothing in it is null
 * rather than sent empty.
 */
export function dayPayload(form) {
  const body = Object.fromEntries(
    DAY_FIELDS.map(({ key, kind }) => [
      key,
      kind === 'mark' ? Boolean(form.fields[key]) : blankToNull(form.fields[key]),
    ]),
  )
  body.meals = Object.fromEntries(
    Object.entries(form.meals).map(([slot, meal]) => {
      const text = blankToNull(meal.text)
      const items = meal.items
        .filter((item) => item.dish)
        .map((item) => ({ dish_id: item.dish.id, recipe_id: item.recipeId ?? null }))
      return [slot, text === null && !items.length ? null : { text, items }]
    }),
  )
  return body
}
