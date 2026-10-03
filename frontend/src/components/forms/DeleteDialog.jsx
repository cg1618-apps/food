// Frontend: the one delete dialog, for every kind of row.
//
// Deliberately not window.confirm: a delete here has to show what goes with
// the row, and has to be able to CORRECT itself when the server says that has
// changed. The shape is module 1's ingredient dialog, generalised:
//
//   1. fetch the row's `cascade` counts and show them;
//   2. send them back as the delete's required query parameters;
//   3. on a 409 carrying `field` / `actual` (StaleCountError), take the
//      server's number, say so, and re-offer the button - no reload;
//   4. a blocking count (a dish with recipes or used by others, an
//      ingredient with varieties or recipe lines) is said up front, in
//      words, but the button stays: the server is the one that decides, and
//      its refusal is what carries the list;
//   5. on a 409 refusing the delete outright, show what blocks it: the
//      recipes in `recipes` (a dish's own) and `used_in` (the ones using
//      it), with links; the dates in `meals` (a dish on the schedule), each
//      linked to its week; or the server's sentence (an
//      ingredient's child varieties are refused by the foreign key, whose
//      409 carries only a sentence - the cascade's `children` count says how
//      many).
//
// A kitchen note has no cascade to count, so it is a plain question in the
// same chrome.
//
// Use:  <DeleteDialog kind="recipe" id={id} name={name} onClose={...} />
// `onDeleted` defaults to going to the kind's library; pass one to go
// elsewhere.
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { buildUrl, fetchJson } from '../../api/client'
import { invalidateResources, useApiQuery } from '../../hooks/useApi'
import { DELETE_TARGETS } from '../../lib/deleteTargets'
import { shortDate, weekStart } from '../../lib/schedule'
import Dialog from '../ui/Dialog'
import { Button } from '../ui/primitives'
import { ErrorNote, Loading } from '../ui/states'

// The lists of recipes a 409 may carry, and how each is introduced.
const REFUSAL_LISTS = [
  ['recipes', '它的食譜：'],
  ['used_in', '用到它的食譜：'],
]

export default function DeleteDialog({ kind, id, name, onClose, onDeleted }) {
  const target = DELETE_TARGETS[kind]
  if (!target) throw new Error(`DeleteDialog: unknown kind ${kind}`)
  const hasCascade = Boolean(target.group.cascade)

  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const cascade = useApiQuery(hasCascade ? target.group.cascade(id) : null, null, {
    enabled: hasCascade,
    // Always fresh: the whole point is that these numbers are true now.
    staleTime: 0,
  })
  const [corrected, setCorrected] = useState({})
  const [error, setError] = useState(null)
  // The recipes a refusal names, by what they are to the row.
  const [refusedBy, setRefusedBy] = useState([])
  // The dates of the meals a refusal names - a dish on the schedule.
  const [mealDates, setMealDates] = useState([])
  const [busy, setBusy] = useState(false)

  const counts = hasCascade && cascade.data ? { ...cascade.data, ...corrected } : {}
  const shown = target.counts.filter(([key]) => counts[key] > 0)
  const blocking = target.blockers.filter(([key]) => counts[key] > 0)

  async function remove() {
    setBusy(true)
    setError(null)
    try {
      const params = Object.fromEntries(target.counts.map(([key]) => [key, counts[key] ?? 0]))
      await fetchJson(buildUrl(target.group.remove(id), params), { method: 'DELETE' })
      // Marked stale, not refetched: this dialog's own cascade read and the
      // page's detail read would refetch and 404 before the page navigates.
      invalidateResources(queryClient, target.invalidate, { refetchType: 'none' })
      if (onDeleted) onDeleted()
      else navigate(target.library)
    } catch (caught) {
      if (caught.status === 409 && caught.body?.field && caught.body.actual !== undefined) {
        // The numbers moved. Named by `field`, never matched by value: two
        // counts can be equal, and correcting the wrong one would loop.
        setCorrected((previous) => ({ ...previous, [caught.body.field]: caught.body.actual }))
      }
      if (caught.status === 409) {
        setRefusedBy(
          REFUSAL_LISTS.map(([key, heading]) => [key, heading, caught.body?.[key]]).filter(
            ([, , rows]) => Array.isArray(rows) && rows.length,
          ),
        )
        setMealDates(Array.isArray(caught.body?.meals) ? caught.body.meals : [])
      }
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  const ready = !hasCascade || Boolean(cascade.data)

  return (
    <Dialog
      title={`刪除${target.noun}「${name ?? ''}」？`}
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            保留
          </Button>
          <Button kind="danger" onClick={remove} disabled={busy || !ready}>
            {busy ? '刪除中…' : error?.body?.field ? '確認刪除' : '刪除'}
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-text">
        {hasCascade && cascade.isPending ? <Loading>計算會一起刪掉的東西…</Loading> : null}
        {hasCascade && cascade.error ? <ErrorNote error={cascade.error} /> : null}

        {ready ? (
          shown.length ? (
            <p>
              會一起刪掉：
              {shown.map(([key, words], index) => (
                <span key={key}>
                  {index ? '、' : ''}
                  <strong className="tabular-nums">{counts[key]}</strong> {words}
                </span>
              ))}
              。圖片會留在圖庫裡。
            </p>
          ) : (
            <p>刪除後就找不回來了。圖片會留在圖庫裡。</p>
          )
        ) : null}

        {blocking.map(([key, sentence]) => (
          <p key={key} className="rounded-md bg-warn-soft px-3 py-2 text-warn">
            {sentence(counts[key])}
          </p>
        ))}

        {error ? <ErrorNote error={error} /> : null}

        {refusedBy.map(([key, heading, rows]) => (
          <div key={key} className="space-y-1">
            <p className="text-text-muted">{heading}</p>
            <ul className="list-disc space-y-0.5 pl-5">
              {rows.map((recipe) => (
                <li key={recipe.id}>
                  <Link to={`/recipes/${recipe.id}`} className="text-brand hover:underline">
                    {recipe.display_name}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ))}

        {mealDates.length ? (
          <div className="space-y-1">
            <p className="text-text-muted">排了它的日子：</p>
            <ul className="flex flex-wrap gap-x-3 gap-y-0.5">
              {mealDates.map((date) => (
                <li key={date}>
                  <Link to={`/schedule?week=${weekStart(date)}`} className="text-brand hover:underline">
                    {shortDate(date)}
                  </Link>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </Dialog>
  )
}
