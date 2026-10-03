// Frontend: 排程, /schedule - the weekly schedule, two weeks at a time.
//
// The owner's sheet, as a page: a week runs Saturday to Friday, and this week
// and next are shown together. `?week=YYYY-MM-DD` names the Saturday shown
// first (lib/schedule.js shownWeek); 上週 / 本週 / 下週 move it. Today's row
// is marked.
//
// On a desktop each week is a table with the sheet's columns in the sheet's
// order; on a phone each day is a card listing only what is filled in, since
// eleven columns do not fit a phone and most cells are empty. Both are in the
// page, shown by width. A meal shows its text, its dish and its recipe, each
// linked.
import { Link } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import WeekNav from '../../components/layout/WeekNav'
import { LinkButton, Section } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { useShownWeeks } from '../../hooks/useShownWeeks'
import { cx } from '../../lib/cx'
import {
  addDays,
  AFTER_MEALS,
  BEFORE_MEALS,
  filledFields,
  rangeLabel,
  SHOWN_DAYS,
  shortDate,
  WEEK_DAYS,
  weekdayName,
  weekdayShort,
} from '../../lib/schedule'

const TITLE = '排程'

function MealCell({ meal }) {
  if (!meal) return null
  return (
    <div className="space-y-0.5">
      {meal.text ? <p>{meal.text}</p> : null}
      {meal.dish ? (
        <p>
          <Link to={`/dishes/${meal.dish.id}`} className="text-brand hover:underline">
            {meal.dish.display_name}
          </Link>
        </p>
      ) : null}
      {meal.recipe ? (
        <p className="text-xs">
          <Link to={`/recipes/${meal.recipe.id}`} className="text-text-muted hover:text-brand hover:underline">
            食譜：{meal.recipe.display_name}
          </Link>
        </p>
      ) : null}
    </div>
  )
}

function dayHeading(day) {
  return `${weekdayName(day.weekday)} ${shortDate(day.date)}`
}

function WeekTable({ label, days, slots, today }) {
  const cell = 'border-b border-border px-2 py-2 align-top'
  return (
    <div className="hidden overflow-x-auto md:block">
      <table aria-label={label} className="w-full min-w-[56rem] border-collapse text-sm">
        <thead>
          <tr className="text-left text-xs text-text-muted">
            <th scope="col" className={cx(cell, 'font-medium')}>
              星期幾
            </th>
            {BEFORE_MEALS.map((field) => (
              <th key={field.key} scope="col" className={cx(cell, 'font-medium')}>
                {field.label}
              </th>
            ))}
            {slots.map((slot) => (
              <th key={slot.value} scope="col" className={cx(cell, 'font-medium')}>
                {slot.label}
              </th>
            ))}
            {AFTER_MEALS.map((field) => (
              <th key={field.key} scope="col" className={cx(cell, 'font-medium')}>
                {field.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {days.map((day) => {
            const isToday = day.date === today
            return (
              <tr
                key={day.date}
                aria-current={isToday ? 'date' : undefined}
                className={cx('text-text', isToday && 'bg-brand-soft')}
              >
                <th scope="row" className={cx(cell, 'whitespace-nowrap text-left font-medium')}>
                  {dayHeading(day)}
                </th>
                {BEFORE_MEALS.map((field) => (
                  <td key={field.key} className={cell}>
                    {day[field.key]}
                  </td>
                ))}
                {slots.map((slot) => (
                  <td key={slot.value} className={cell}>
                    <MealCell meal={day.meals[slot.value]} />
                  </td>
                ))}
                {AFTER_MEALS.map((field) => (
                  <td key={field.key} className={cell}>
                    {day[field.key]}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

function DayCards({ label, days, slots, today }) {
  return (
    <ul aria-label={label} className="space-y-2 md:hidden">
      {days.map((day) => {
        const isToday = day.date === today
        const fields = filledFields(day, slots)
        return (
          <li
            key={day.date}
            aria-label={dayHeading(day)}
            aria-current={isToday ? 'date' : undefined}
            className={cx(
              'rounded-lg border bg-surface px-3 py-2',
              isToday ? 'border-brand bg-brand-soft' : 'border-border',
            )}
          >
            <p className="font-medium text-text">
              {dayHeading(day)}
              {isToday ? <span className="ml-2 text-xs text-brand">今天</span> : null}
            </p>
            {fields.length ? (
              <dl className="mt-1 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 text-sm">
                {fields.map((field) => (
                  <div key={field.key} className="contents">
                    <dt className="text-text-muted">{field.label}</dt>
                    <dd className="text-text">
                      {field.meal ? <MealCell meal={field.meal} /> : field.value}
                    </dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="text-sm text-text-faint">－</p>
            )}
          </li>
        )
      })}
    </ul>
  )
}

export default function Schedule() {
  const { start, today } = useShownWeeks()
  const query = useApiQuery(endpoints.schedule.list(), { start, days: SHOWN_DAYS })
  const fixed = useFixedVocabularies()
  const slots = fixed.data?.meal_slots ?? []

  let body
  if (query.isPending || fixed.isPending) body = <Loading />
  else if (query.error || fixed.error) body = <ErrorNote error={query.error ?? fixed.error} />
  else
    body = [0, 1].map((week) => {
      const first = addDays(start, week * WEEK_DAYS)
      const days = query.data.slice(week * WEEK_DAYS, (week + 1) * WEEK_DAYS)
      const label = rangeLabel(first)
      return (
        <Section key={first} title={label}>
          <WeekTable label={label} days={days} slots={slots} today={today} />
          <DayCards label={label} days={days} slots={slots} today={today} />
        </Section>
      )
    })

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">{TITLE}</h1>
          <p className="text-sm text-text-muted">
            {rangeLabel(start, SHOWN_DAYS)}（{weekdayShort(5)}–{weekdayShort(4)}）
          </p>
        </div>
        <LinkButton to={`/edit/schedule?week=${start}`} size="sm">
          編輯
        </LinkButton>
      </div>
      <WeekNav base="/schedule" start={start} today={today} />
      {body}
    </div>
  )
}
