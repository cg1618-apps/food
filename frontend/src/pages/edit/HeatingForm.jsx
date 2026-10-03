// Frontend: 加熱's edit page, /edit/heating - the same list as /heating,
// editable in place, with TBD's edit page (pages/edit/TbdForm.jsx) as its
// pattern.
//
// Every note is a card: a name, how to heat it, and its own 儲存 and 刪除. A
// card is saved on its own, so editing one note never touches another.
// 「＋ 新增」 puts an unsaved card at the end; its 儲存 creates it (POST), and
// its 取消 drops it without asking, since nothing has been stored.
//
// Notes are reordered by their drag handle and the order is saved at once:
// the new order is shown immediately, the list is frozen until the PUT has
// landed and the list has been read again, and a refusal puts the stored
// order back with the server's sentence. Unsaved cards have no handle.
import { arrayMove } from '@dnd-kit/sortable'
import { useState } from 'react'

import { endpoints } from '../../api/endpoints'
import ConfirmModal from '../../components/modals/ConfirmModal'
import { Button, Field, Input, LinkButton, TextArea } from '../../components/ui/primitives'
import { DragHandle, SortableItem, SortableList } from '../../components/ui/Sortable'
import { Empty, ErrorNote, Loading } from '../../components/ui/states'
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import { blankToNull, nextKey } from '../../lib/rowList'

const TITLE = '加熱'
const INVALIDATE = [endpoints.heating.list()]
const NEEDS_NAME = '要填名稱。'

export default function HeatingForm() {
  const list = useApiQuery(endpoints.heating.list())
  const reorder = useApiMutation({ method: 'PUT', invalidate: INVALIDATE })
  const [pending, setPending] = useState(null)
  const [orderError, setOrderError] = useState(null)
  const [fresh, setFresh] = useState([])

  const stored = list.data ?? []
  const shown = pending
    ? pending.map((id) => stored.find((note) => note.id === id)).filter(Boolean)
    : stored
  const moving = pending !== null
  const ids = shown.map((note) => note.id)

  async function move(from, to) {
    if (moving) return
    const next = arrayMove(ids, from, to)
    setPending(next)
    setOrderError(null)
    try {
      await reorder.mutateAsync({ url: endpoints.heating.order(), body: { ids: next } })
    } catch (caught) {
      setOrderError(caught)
    } finally {
      setPending(null)
    }
  }

  const drop = (key) => setFresh((keys) => keys.filter((k) => k !== key))

  let body
  if (list.isPending) body = <Loading />
  else if (list.error) body = <ErrorNote error={list.error} />
  else
    body = (
      <>
        {shown.length === 0 && fresh.length === 0 ? <Empty>還沒有任何加熱筆記。</Empty> : null}
        {/* Outside the <ul>, as on every sortable list here: dnd-kit draws its
            hidden screen-reader text beside its children, and a <ul> holds
            only <li>. */}
        <SortableList ids={ids} onMove={move} disabled={moving}>
          <ul aria-label={TITLE} className="space-y-3">
            {shown.map((note) => (
              <NoteCard key={note.id} note={note} />
            ))}
            {fresh.map((key) => (
              <NoteCard key={key} onCreated={() => drop(key)} onDiscard={() => drop(key)} />
            ))}
          </ul>
        </SortableList>
        <Button onClick={() => setFresh((keys) => [...keys, nextKey()])}>＋ 新增</Button>
      </>
    )

  return (
    <div className="mx-auto max-w-3xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-3xl font-bold">編輯{TITLE}</h1>
        <LinkButton to="/heating" size="sm">
          完成
        </LinkButton>
      </div>
      {orderError ? <ErrorNote error={orderError} /> : null}
      {body}
    </div>
  )
}

// One note. `note` is the stored row; without one the card is new and
// unsaved. The card keeps what is typed in its own state, so a refetch after
// another card's save never throws it away.
function NoteCard({ note, onCreated, onDiscard }) {
  const isNew = !note
  const label = isNew ? '新項目' : note.name
  const [name, setName] = useState(note?.name ?? '')
  const [text, setText] = useState(note?.body ?? '')
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [confirming, setConfirming] = useState(false)

  const save = useApiMutation({ method: isNew ? 'POST' : 'PATCH', invalidate: INVALIDATE })
  const remove = useApiMutation({ method: 'DELETE', invalidate: INVALIDATE })
  const busy = save.isPending || remove.isPending

  const edit = (setter) => (event) => {
    setter(event.target.value)
    setSaved(false)
  }

  async function submit() {
    const payload = { name: blankToNull(name), body: blankToNull(text) }
    if (payload.name === null) {
      setError(new Error(NEEDS_NAME))
      return
    }
    setError(null)
    try {
      await save.mutateAsync({
        url: isNew ? endpoints.heating.create() : endpoints.heating.update(note.id),
        body: payload,
      })
      if (isNew) onCreated()
      else setSaved(true)
    } catch (caught) {
      setError(caught)
    }
  }

  async function confirmDelete() {
    try {
      await remove.mutateAsync({ url: endpoints.heating.remove(note.id) })
    } catch (caught) {
      setConfirming(false)
      setError(caught)
    }
  }

  const Item = isNew ? 'li' : SortableItem
  const itemProps = isNew ? {} : { id: note.id, as: 'li' }

  return (
    <Item {...itemProps} aria-label={label} className="space-y-3 rounded-lg border border-border bg-surface p-3">
      <div className="flex items-end gap-2">
        {isNew ? null : <DragHandle label={`「${label}」`} className="mb-1.5" />}
        <Field label="名稱" className="min-w-0 flex-1">
          <Input value={name} onChange={edit(setName)} placeholder="例：冷凍吐司" />
        </Field>
      </div>

      <Field label="怎麼加熱">
        <TextArea value={text} onChange={edit(setText)} rows={3} placeholder="例：烤箱 180 度 5 分鐘" />
      </Field>

      {error ? <ErrorNote error={error} /> : null}

      <div className="flex flex-wrap items-center gap-2">
        <Button kind="primary" size="sm" onClick={submit} disabled={busy}>
          {save.isPending ? '儲存中…' : '儲存'}
        </Button>
        {saved ? <span className="text-xs text-text-faint">已儲存</span> : null}
        {isNew ? (
          <Button size="sm" className="ml-auto" onClick={onDiscard} disabled={busy}>
            取消
          </Button>
        ) : (
          <Button kind="danger" size="sm" className="ml-auto" onClick={() => setConfirming(true)} disabled={busy}>
            刪除
          </Button>
        )}
      </div>

      {confirming ? (
        <ConfirmModal
          title="刪除這一項？"
          confirmLabel="刪除"
          danger
          busy={remove.isPending}
          onConfirm={confirmDelete}
          onCancel={() => setConfirming(false)}
        >
          {`「${note.name}」會被刪除。`}
        </ConfirmModal>
      ) : null}
    </Item>
  )
}
