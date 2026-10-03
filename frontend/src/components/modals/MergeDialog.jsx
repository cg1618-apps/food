// Frontend: 「合併到…」 - fold one ingredient into another.
//
// Three steps in one dialog:
//
//   1. pick the target with the Typeahead (ingredients only, never itself);
//      typed text that matches nothing picked is said, not merged;
//   2. read the preview - GET .../merge-preview?into=, computed by the same
//      function the merge runs - in words (lib/mergePreview.js): what moves,
//      which names become aliases, which storage rows the target already has
//      and so drops, which notes move or are dropped;
//   3. merge, sending the preview's `fingerprint`. If the plan changed since
//      the preview (someone edited either ingredient), the server answers 409
//      with the fresh preview on the body: it replaces the one shown, the
//      dialog says it changed, and the button asks again. On success the
//      source no longer exists, so the page goes to the target.
//
// A merge into one of the source's own descendants is the server's 422; its
// sentence is shown where the preview would be.
import { useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import { fetchJson, jsonBody } from '../../api/client'
import { invalidateResources, useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { describeMerge } from '../../lib/mergePreview'
import Typeahead, { Picked } from '../forms/Typeahead'
import Dialog from '../ui/Dialog'
import { Button } from '../ui/primitives'
import { ErrorNote, Loading } from '../ui/states'

// A merge moves recipe lines, varieties, labels, pictures and heating rows
// onto the target and deletes the source: every read those touch is stale,
// 常用食材 among them (the source's chip moves to the target, or goes), and
// the recipe templates (their lines naming the source now name the target).
const INVALIDATE = [
  endpoints.ingredients.list(),
  endpoints.commonIngredients.list(),
  endpoints.templates.list(),
  endpoints.categories.tree(),
  endpoints.labels.list(),
  endpoints.recipes.list(),
  endpoints.methods.list(),
  endpoints.images.list(),
]

function PreviewWords({ preview, states }) {
  const words = describeMerge(preview, states)
  const nothing =
    !words.moves.length &&
    !words.aliases.length &&
    !words.dropped.length &&
    !words.proseMoved.length &&
    !words.proseDropped.length
  return (
    <div className="space-y-2">
      <p>
        「{preview.source.display_name}」會併進「{preview.target.display_name}」，然後刪除。
      </p>
      {nothing ? <p className="text-text-muted">它沒有任何東西要搬過去。</p> : null}
      <ul className="list-disc space-y-1 pl-5">
        {words.moves.length ? (
          <li>
            搬過去：
            {words.moves.map((move, index) => (
              <span key={move.key}>
                {index ? '、' : ''}
                <strong className="tabular-nums">{move.count}</strong> {move.words}
              </span>
            ))}
          </li>
        ) : null}
        {words.aliases.length ? <li>成為別名：{words.aliases.join('、')}</li> : null}
        {words.proseMoved.length ? <li>筆記搬過去：{words.proseMoved.join('、')}</li> : null}
      </ul>
      {words.dropped.length || words.proseDropped.length ? (
        <div className="space-y-1 rounded-md bg-warn-soft px-3 py-2 text-warn">
          <p>目標已經有自己的，這些會捨棄：</p>
          <ul className="list-disc pl-5">
            {words.dropped.map((text) => (
              <li key={text}>保存 {text}</li>
            ))}
            {words.proseDropped.length ? <li>筆記 {words.proseDropped.join('、')}</li> : null}
          </ul>
        </div>
      ) : null}
    </div>
  )
}

export default function MergeDialog({ ingredient, onClose }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const fixed = useFixedVocabularies()
  const [target, setTarget] = useState(null)
  // What is typed in the picker and not yet picked: 合併 stays off until a
  // target is chosen, so say why rather than leave a dead button.
  const [typed, setTyped] = useState('')
  // The preview the server sent with a 409, which replaces the fetched one.
  const [fresh, setFresh] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const previewQuery = useApiQuery(
    target ? endpoints.ingredients.mergePreview(ingredient.id) : null,
    target ? { into: target.id } : null,
    { enabled: Boolean(target), staleTime: 0, gcTime: 0 },
  )
  const preview = fresh ?? previewQuery.data
  const changed = Boolean(fresh)

  function choose(option) {
    setTarget(option)
    setTyped('')
    setFresh(null)
    setError(null)
  }

  async function merge() {
    setBusy(true)
    setError(null)
    try {
      await fetchJson(endpoints.ingredients.merge(ingredient.id), {
        method: 'POST',
        ...jsonBody({ into: target.id, fingerprint: preview.fingerprint }),
      })
      // Marked stale, not refetched: the source's own detail read would
      // refetch and 404 before the page leaves it.
      invalidateResources(queryClient, INVALIDATE, { refetchType: 'none' })
      onClose()
      navigate(`/ingredients/${target.id}`)
    } catch (caught) {
      if (caught.status === 409 && caught.body?.preview) {
        setFresh(caught.body.preview)
      } else {
        setError(caught)
      }
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog
      title={`把「${ingredient.display_name}」合併到…`}
      size="md"
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            取消
          </Button>
          <Button kind="primary" onClick={merge} disabled={busy || !preview}>
            {busy ? '合併中…' : changed ? '確認合併' : '合併'}
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-text">
        {target ? (
          <Picked label={target.label} stub={target.needsDetail} onClear={() => choose(null)} />
        ) : (
          // Room for the result list: the dialog body scrolls, so an
          // absolutely placed list would otherwise be clipped inside it.
          <div className="min-h-72">
            <Typeahead
              sources={['ingredient']}
              exclude={{ ingredient: [ingredient.id] }}
              onSelect={choose}
              onQueryChange={setTyped}
              label="合併到哪個食材"
              placeholder="搜尋要保留的食材…"
              autoFocus
            />
            {typed.trim() ? (
              <p className="mt-2 text-text-muted">打了「{typed.trim()}」：從清單選一個要保留的食材，才能合併。</p>
            ) : null}
          </div>
        )}

        {target && !fresh && previewQuery.isPending ? <Loading>計算合併內容…</Loading> : null}
        {target && !fresh && previewQuery.error ? <ErrorNote error={previewQuery.error} /> : null}

        {changed ? (
          <p role="status" className="rounded-md border border-warn/50 px-3 py-2 text-warn">
            預覽之後這兩個食材有人改過，下面是現在的合併內容，請再確認一次。
          </p>
        ) : null}

        {preview ? <PreviewWords preview={preview} states={fixed.data?.preservation_states} /> : null}

        {error ? <ErrorNote error={error} /> : null}
      </div>
    </Dialog>
  )
}
