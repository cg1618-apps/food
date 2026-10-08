// Frontend: one value on 設定 - a label, a course, a method, a piece of
// equipment or a category - with everything that can be done to it in place.
//
// Rename is inline: 改名 turns the row into its two name slots, Enter saves,
// Escape puts the row back. Reordering is a drag handle, as on every form:
// a sortable row must sit in a SortableList (components/ui/Sortable.jsx),
// which the editor draws and which owns the move. Delete asks first, in the
// shared ConfirmModal, and a refusal is explained IN THE ROW - the place the
// eye already is - with the server's count rather than a page-level banner
// that does not say which value it means.
//
//   item          { id, display_name, name_cn, name_en }
//   meta          the count line beside the name ("用在 3 個地方")
//   badge         an extra chip after the name (the fallback category's 預設)
//   onRename      async ({ name_cn, name_en, ...extra }) => void
//   renameExtra   (draft, setDraft) => more controls in rename mode (parent)
//   initialExtra  extra draft fields rename mode starts from
//   sortable      whether the row has a drag handle (its id is `item.id`)
//   onDelete      async () => void, or absent when the row cannot be deleted
//   confirmText   what the delete question says
//   refusal       (error) => the inline sentence for a failed delete
//   children      extra row actions (新增子分類, a label's 移到)
//   nested        drawn under the row, inside it - the category tree's
//                 children, which a drag carries along with their parent
import { useState } from 'react'

import { cx } from '../../lib/cx'
import ConfirmModal from '../modals/ConfirmModal'
import { Button, Input } from '../ui/primitives'
import { DragHandle, SortableItem } from '../ui/Sortable'

export default function NameRow({
  item,
  meta,
  badge,
  onRename,
  renameExtra,
  initialExtra,
  sortable = false,
  onDelete,
  confirmText,
  refusal = (error) => error?.message,
  children,
  nested,
}) {
  const [draft, setDraft] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function attempt(action, explain = (caught) => caught?.message) {
    setBusy(true)
    setError(null)
    try {
      await action()
      return true
    } catch (caught) {
      setError(explain(caught) || '出了點問題，請再試一次。')
      return false
    } finally {
      setBusy(false)
    }
  }

  function startRename() {
    setError(null)
    setDraft({ name_cn: item.name_cn ?? '', name_en: item.name_en ?? '', ...initialExtra })
  }

  async function saveRename(event) {
    event.preventDefault()
    const done = await attempt(() => onRename(draft))
    if (done) setDraft(null)
  }

  async function confirmDelete() {
    setConfirming(false)
    await attempt(onDelete, refusal)
  }

  const name = item.display_name
  const Row = sortable ? SortableItem : 'li'
  const rowProps = sortable ? { id: item.id, as: 'li' } : {}

  return (
    <Row {...rowProps} aria-label={name}>
      <div className="rounded-md border border-border bg-surface px-2 py-1.5">
        {draft ? (
          <form
            onSubmit={saveRename}
            onKeyDown={(event) => {
              if (event.key === 'Escape') setDraft(null)
            }}
            className="flex flex-wrap items-center gap-2"
          >
            <Input
              aria-label={`${name} 的中文名`}
              placeholder="中文名"
              value={draft.name_cn}
              onChange={(e) => setDraft({ ...draft, name_cn: e.target.value })}
              className="w-36 flex-1"
              autoFocus
            />
            <Input
              aria-label={`${name} 的英文名`}
              placeholder="English"
              value={draft.name_en}
              onChange={(e) => setDraft({ ...draft, name_en: e.target.value })}
              className="w-36 flex-1"
            />
            {renameExtra ? renameExtra(draft, setDraft) : null}
            <div className="flex gap-1">
              <Button type="submit" kind="primary" size="sm" disabled={busy}>
                儲存
              </Button>
              <Button size="sm" onClick={() => setDraft(null)} disabled={busy}>
                取消
              </Button>
            </div>
          </form>
        ) : (
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            {sortable ? <DragHandle label={`「${name}」`} /> : null}
            <span className="min-w-0 flex-1">
              <span className="font-medium text-text">{name}</span>
              {item.name_cn && item.name_en ? (
                <span className="pl-2 text-xs text-text-faint">{item.name_en}</span>
              ) : null}
              {badge ? <span className="pl-2">{badge}</span> : null}
              {meta ? <span className="block text-xs text-text-muted sm:inline sm:pl-2">{meta}</span> : null}
            </span>
            <div className="flex shrink-0 flex-wrap gap-1">
              {children}
              <Button kind="ghost" size="sm" onClick={startRename} disabled={busy} aria-label={`改名「${name}」`}>
                改名
              </Button>
              {onDelete ? (
                <Button
                  kind="ghost"
                  size="sm"
                  className="hover:text-danger"
                  onClick={() => setConfirming(true)}
                  disabled={busy}
                  aria-label={`刪除「${name}」`}
                >
                  刪除
                </Button>
              ) : null}
            </div>
          </div>
        )}

        {error ? (
          <p role="alert" className={cx('mt-1 text-sm text-danger', sortable && !draft ? 'pl-6' : null)}>
            {error}
          </p>
        ) : null}
      </div>

      {nested}

      {confirming ? (
        <ConfirmModal
          title={`刪除「${name}」？`}
          confirmLabel="刪除"
          danger
          busy={busy}
          onConfirm={confirmDelete}
          onCancel={() => setConfirming(false)}
        >
          {confirmText}
        </ConfirmModal>
      ) : null}
    </Row>
  )
}
