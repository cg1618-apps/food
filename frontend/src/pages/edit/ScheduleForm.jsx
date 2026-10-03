// Frontend: the schedule's edit page, /edit/schedule - the same two weeks as
// /schedule, every day a card edited in place.
//
// A card holds the day's plain fields and its four meals; each meal is free
// text, a dish picked from the library, and optionally one of that dish's
// recipes. The recipe is a select of the chosen dish's own recipes (read from
// the dish) rather than a second search: the API refuses a recipe of another
// dish, and a list that only offers the dish's recipes cannot make that
// mistake, nor leave the dish and the recipe disagreeing on screen.
//
// A card saves on its own 儲存, one PUT that replaces the whole day - so
// emptying every field removes the day. Saving is explicit rather than on
// blur: a phone does not reliably blur a field when the thumb taps elsewhere,
// and a save that silently did not happen is the one outcome this page must
// not have. So a card with changes says 未儲存 until it is saved, the page
// counts them, the week buttons are disabled and 完成 says 放棄修改 while any
// is unsaved, and closing the tab with any unsaved asks first. A
// dish typed into the search but not picked refuses the save with a
// sentence, rather than being dropped.
import { useEffect, useState } from 'react'

import { endpoints } from '../../api/endpoints'
import Typeahead, { Picked } from '../../components/forms/Typeahead'
import WeekNav from '../../components/layout/WeekNav'
import { Button, Field, Input, LinkButton, Select, Section } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { useApiMutation, useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { useShownWeeks } from '../../hooks/useShownWeeks'
import { cx } from '../../lib/cx'
import {
  addDays,
  dayForm,
  dayPayload,
  DAY_FIELDS,
  rangeLabel,
  SHOWN_DAYS,
  shortDate,
  WEEK_DAYS,
  weekdayName,
} from '../../lib/schedule'

const TITLE = '編輯排程'
const UNPICKED = '有料理只打了字、沒從清單選，請選一個或清掉再儲存。'

export default function ScheduleForm() {
  const { start, today } = useShownWeeks()
  const query = useApiQuery(endpoints.schedule.list(), { start, days: SHOWN_DAYS })
  const fixed = useFixedVocabularies()
  const slots = fixed.data?.meal_slots ?? []
  const [dirty, setDirty] = useState({})

  const unsaved = Object.values(dirty).filter(Boolean).length
  useEffect(() => {
    if (!unsaved) return undefined
    const warn = (event) => {
      event.preventDefault()
      event.returnValue = ''
    }
    window.addEventListener('beforeunload', warn)
    return () => window.removeEventListener('beforeunload', warn)
  }, [unsaved])

  let body
  if (query.isPending || fixed.isPending) body = <Loading />
  else if (query.error || fixed.error) body = <ErrorNote error={query.error ?? fixed.error} />
  else
    body = [0, 1].map((week) => {
      const first = addDays(start, week * WEEK_DAYS)
      const days = query.data.slice(week * WEEK_DAYS, (week + 1) * WEEK_DAYS)
      return (
        <Section key={first} title={rangeLabel(first)}>
          <ul aria-label={rangeLabel(first)} className="grid gap-3 lg:grid-cols-2">
            {days.map((day) => (
              <DayCard
                key={day.date}
                day={day}
                slots={slots}
                isToday={day.date === today}
                onDirty={(value) => setDirty((all) => ({ ...all, [day.date]: value }))}
              />
            ))}
          </ul>
        </Section>
      )
    })

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold">{TITLE}</h1>
          <p className="text-sm text-text-muted">{rangeLabel(start, SHOWN_DAYS)}</p>
        </div>
        <div className="flex items-center gap-2">
          {unsaved ? <span className="text-xs text-warn">{unsaved} 天未儲存</span> : null}
          <LinkButton to={`/schedule?week=${start}`} size="sm">
            {unsaved ? '放棄修改' : '完成'}
          </LinkButton>
        </div>
      </div>
      <WeekNav base="/edit/schedule" start={start} today={today} locked={unsaved > 0} />
      {body}
    </div>
  )
}

// One day. The card keeps what is typed in its own state, so a refetch after
// another card's save never throws it away.
function DayCard({ day, slots, isToday, onDirty }) {
  const heading = `${weekdayName(day.weekday)} ${shortDate(day.date)}`
  const [form, setForm] = useState(() => dayForm(day, slots))
  const [typing, setTyping] = useState({})
  const [changed, setChanged] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)
  const save = useApiMutation({ method: 'PUT', invalidate: [endpoints.schedule.list()] })

  function touch(next) {
    setForm(next)
    setChanged(true)
    setSaved(false)
    onDirty(true)
  }

  const setField = (key, value) => touch({ ...form, fields: { ...form.fields, [key]: value } })
  const setMeal = (slot, patch) =>
    touch({ ...form, meals: { ...form.meals, [slot]: { ...form.meals[slot], ...patch } } })

  async function submit() {
    if (Object.values(typing).some((text) => text.trim() !== '')) {
      setError(new Error(UNPICKED))
      return
    }
    setError(null)
    try {
      await save.mutateAsync({ url: endpoints.schedule.update(day.date), body: dayPayload(form) })
      setChanged(false)
      setSaved(true)
      onDirty(false)
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <li
      aria-label={heading}
      aria-current={isToday ? 'date' : undefined}
      className={cx(
        'space-y-3 rounded-lg border bg-surface p-3',
        isToday ? 'border-brand' : 'border-border',
      )}
    >
      <div className="flex items-baseline justify-between gap-2">
        <p className="font-medium text-text">
          {heading}
          {isToday ? <span className="ml-2 text-xs text-brand">今天</span> : null}
        </p>
        {changed ? <span className="text-xs text-warn">未儲存</span> : null}
        {saved ? <span className="text-xs text-text-faint">已儲存</span> : null}
      </div>

      <div className="grid gap-2 sm:grid-cols-2">
        {slots.map((slot) => (
          <MealEditor
            key={slot.value}
            label={slot.label}
            meal={form.meals[slot.value]}
            onChange={(patch) => setMeal(slot.value, patch)}
            onTyping={(text) => setTyping((all) => ({ ...all, [slot.value]: text }))}
          />
        ))}
      </div>

      <div className="grid gap-2 sm:grid-cols-3">
        {DAY_FIELDS.map((field) => (
          <Field key={field.key} label={field.label}>
            <Input
              value={form.fields[field.key]}
              onChange={(event) => setField(field.key, event.target.value)}
            />
          </Field>
        ))}
      </div>

      {error ? <ErrorNote error={error} /> : null}

      <Button kind="primary" size="sm" onClick={submit} disabled={save.isPending}>
        {save.isPending ? '儲存中…' : '儲存'}
      </Button>
    </li>
  )
}

// One meal: text, a dish, and one of that dish's recipes.
function MealEditor({ label, meal, onChange, onTyping }) {
  const dish = useApiQuery(meal.dish ? endpoints.dishes.detail(meal.dish.id) : null, null, {
    enabled: Boolean(meal.dish),
  })
  const recipes = dish.data?.recipes ?? []

  return (
    <fieldset aria-label={label} className="space-y-1.5 rounded-md border border-border p-2">
      <legend className="px-1 text-sm font-medium text-text-muted">{label}</legend>
      <Input
        aria-label={`${label} 內容`}
        placeholder="內容"
        value={meal.text}
        onChange={(event) => onChange({ text: event.target.value })}
      />
      {meal.dish ? (
        <Picked
          label={meal.dish.display_name}
          tag="料理"
          onClear={() => onChange({ dish: null, recipeId: null })}
        />
      ) : (
        <Typeahead
          sources={['dish']}
          label={`${label} 料理`}
          placeholder="搜尋料理…"
          onQueryChange={onTyping}
          onSelect={(option) =>
            onChange({ dish: { id: option.id, display_name: option.label }, recipeId: null })
          }
        />
      )}
      {meal.dish ? (
        <Select
          aria-label={`${label} 食譜`}
          value={meal.recipeId ?? ''}
          onChange={(event) =>
            onChange({ recipeId: event.target.value === '' ? null : Number(event.target.value) })
          }
        >
          <option value="">不指定食譜</option>
          {recipes.map((recipe) => (
            <option key={recipe.id} value={recipe.id}>
              {recipe.display_name}
            </option>
          ))}
          {/* The saved recipe before the dish has been read, so the select
              never shows a stored choice as 不指定 while it loads. */}
          {meal.recipeId && !recipes.some((recipe) => recipe.id === meal.recipeId) ? (
            <option value={meal.recipeId}>（載入中…）</option>
          ) : null}
        </Select>
      ) : null}
    </fieldset>
  )
}
