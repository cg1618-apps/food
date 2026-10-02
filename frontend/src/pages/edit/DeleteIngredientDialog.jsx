import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { buildUrl, fetchJson } from '../../api/client'
import { endpoints } from '../../api/endpoints'
import { Button, Card } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { invalidateResources, useApiQuery } from '../../hooks/useApi'

// Deliberately not window.confirm: this dialog has to show counts, and it has
// to be able to CORRECT itself when the server says they have moved.
//
// The counts are echoed back to the server as required parameters. If either
// has changed since this opened - another tab, or this one left open while the
// ingredient was edited elsewhere - the server answers 409 with `expected` and
// `actual` on the body, and we update in place and re-offer the button.
//
// That last part is why the error carries data rather than only a sentence.
// With prose alone the only possible recovery is a full page reload, which is
// what media's equivalent message has to ask for.
export default function DeleteIngredientDialog({ id, name, onClose, onDeleted }) {
  const counts = useApiQuery(endpoints.ingredients.cascade(id))
  const queryClient = useQueryClient()
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const [confirmed, setConfirmed] = useState(null)

  const live = confirmed ?? counts.data

  async function remove() {
    setBusy(true)
    setError(null)
    try {
      await fetchJson(
        buildUrl(endpoints.ingredients.remove(id), {
          aliases: live.aliases,
          preservation: live.preservation,
          heating: live.heating,
          links: live.links,
        }),
        { method: 'DELETE' },
      )
      // The deleted row must leave the list, and the counts it was in move.
      // Marked stale, not refetched: this dialog's own cascade read would
      // refetch and 404 before the page navigates away.
      invalidateResources(
        queryClient,
        [endpoints.ingredients.list(), endpoints.categories.tree(), endpoints.labels.list()],
        { refetchType: 'none' },
      )
      onDeleted()
    } catch (caught) {
      if (caught.status === 409 && caught.body?.actual !== undefined) {
        // The numbers moved. Take the server's, say so, and let them confirm
        // again - no reload, and nothing lost from the page behind this.
        setConfirmed({ ...live, ...inferCounts(caught.body) })
      }
      setError(caught)
    } finally {
      setBusy(false)
    }
  }

  if (counts.isPending) return <Loading />
  if (counts.error) return <ErrorNote error={counts.error} />

  return (
    <Card className="space-y-3 border-danger">
      <h2 className="font-semibold">Delete {name}?</h2>

      {live.children > 0 ? (
        <p className="text-sm">
          This has {live.children} more specific {live.children === 1 ? 'kind' : 'kinds'} under
          it, so it cannot be deleted. Move or delete those first.
        </p>
      ) : (
        <p className="text-sm">
          This also removes {live.aliases} {live.aliases === 1 ? 'alias' : 'aliases'} and{' '}
          {live.preservation} preservation{' '}
          {live.preservation === 1 ? 'note' : 'notes'}. The notes written on it go too.
        </p>
      )}

      {error ? <ErrorNote error={error} /> : null}

      <div className="flex gap-2">
        <Button kind="danger" onClick={remove} disabled={busy || live.children > 0}>
          {busy ? 'Deleting…' : 'Delete it'}
        </Button>
        <Button onClick={onClose}>Keep it</Button>
      </div>
    </Card>
  )
}

// The 409 names the count that moved in `field`, using the same names as the
// delete's query parameters. Matching on the number instead is ambiguous when
// two counts are equal, and the dialog would correct the wrong one forever.
function inferCounts(body) {
  return body.field ? { [body.field]: body.actual } : {}
}
