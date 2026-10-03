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

// The day's plain fields, in the sheet's column order around the meals:
// 要買? 早退冰? 中退冰? | 早 中 下午 晚 | 晚退冰? 水果 備註.
export const BEFORE_MEALS = [
  { key: 'to_buy', label: '要買?' },
  { key: 'thaw_morning', label: '早退冰?' },
  { key: 'thaw_noon', label: '中退冰?' },
]
export const AFTER_MEALS = [
  { key: 'thaw_evening', label: '晚退冰?' },
  { key: 'fruit', label: '水果' },
  { key: 'note', label: '備註' },
]
export const DAY_FIELDS = [...BEFORE_MEALS, ...AFTER_MEALS]

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
  return Boolean(meal && (meal.text || meal.dish || meal.recipe))
}

/** The day's fields that hold something, in column order, for the phone card. */
export function filledFields(day, slots) {
  return [
    ...BEFORE_MEALS.filter(({ key }) => day[key]).map((field) => ({ ...field, value: day[field.key] })),
    ...slots
      .filter(({ value }) => mealFilled(day.meals?.[value]))
      .map(({ value, label }) => ({ key: value, label, meal: day.meals[value] })),
    ...AFTER_MEALS.filter(({ key }) => day[key]).map((field) => ({ ...field, value: day[field.key] })),
  ]
}

/** A day from the API as the edit card's state: every field a string, every
 * meal { text, dish, recipeId }. */
export function dayForm(day, slots) {
  return {
    fields: Object.fromEntries(DAY_FIELDS.map(({ key }) => [key, day?.[key] ?? ''])),
    meals: Object.fromEntries(
      slots.map(({ value }) => {
        const meal = day?.meals?.[value]
        return [
          value,
          {
            text: meal?.text ?? '',
            dish: meal?.dish ?? null,
            recipeId: meal?.recipe?.id ?? null,
          },
        ]
      }),
    ),
  }
}

/**
 * The edit card's state as the PUT body, which replaces the whole day: blank
 * text is null, and a meal with nothing in it is null rather than sent empty.
 */
export function dayPayload(form) {
  const body = Object.fromEntries(DAY_FIELDS.map(({ key }) => [key, blankToNull(form.fields[key])]))
  body.meals = Object.fromEntries(
    Object.entries(form.meals).map(([slot, meal]) => {
      const text = blankToNull(meal.text)
      const dishId = meal.dish?.id ?? null
      const recipeId = dishId === null ? null : (meal.recipeId ?? null)
      const empty = text === null && dishId === null && recipeId === null
      return [slot, empty ? null : { text, dish_id: dishId, recipe_id: recipeId }]
    }),
  )
  return body
}
