// Frontend: one value on 設定 - a label, a course, a method, a piece of
// equipment or a category - with everything that can be done to it in place.
//
// Rename is inline: 改名 turns the row into its two name slots, Enter saves,
// Escape puts the row back. Reordering is ▲ / ▼ (上移 / 下移), media's
// buttons rather than a drag, as on every form. Delete asks first, in the
// shared ConfirmModal, and a refusal is explained IN THE ROW - the place the
// eye already is - with the server's count rather than a page-level banner
// that does not say which value it means.
//
//   item          { id, display_name, name_cn, name_en }
//   meta          the count line beside the name ("用在 3 個地方")
//   badge         an extra chip after the name (the fallback category's 預設)
//   depth         indentation, for the category tree
//   onRename      async ({ name_cn, name_en, ...extra }) => void
//   renameExtra   (draft, setDraft) => more controls in rename mode (parent)
//   initialExtra  extra draft fields rename mode starts from
//   onMove        async (delta) => void, or absent when the list has no order
//   canMoveUp / canMoveDown
//   onDelete      async () => void, or absent when the row cannot be deleted
//   confirmText   what the delete question says
//   refusal       (error) => the inline sentence for a failed delete
//   children      extra row actions (新增子分類)
import { useState } from 'react'

import { cx } from '../../lib/cx'
import ConfirmModal from '../modals/ConfirmModal'
import { Button, Input } from '../ui/primitives'

export default function NameRow({
  item,
  meta,
  badge,
  depth = 0,
  onRename,
  renameExtra,
  initialExtra,
  onMove,
  canMoveUp = false,
  canMoveDown = false,
  onDelete,
  confirmText,
  refusal = (error) => error?.message,
  children,
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

  return (
    <li
      aria-label={name}
      className="rounded-md border border-border bg-surface px-2 py-1.5"
      style={depth ? { marginLeft: `${depth * 1.25}rem` } : undefined}
    >
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
          {onMove ? (
            <div className="flex shrink-0 flex-col">
              <MoveButton
                label={`上移「${name}」`}
                disabled={!canMoveUp || busy}
                onClick={() => attempt(() => onMove(-1))}
              >
                ▲
              </MoveButton>
              <MoveButton
                label={`下移「${name}」`}
                disabled={!canMoveDown || busy}
                onClick={() => attempt(() => onMove(1))}
              >
                ▼
              </MoveButton>
            </div>
          ) : null}
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
        <p role="alert" className={cx('mt-1 text-sm text-danger', onMove && !draft ? 'pl-6' : null)}>
          {error}
        </p>
      ) : null}

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
    </li>
  )
}

function MoveButton({ label, disabled, onClick, children }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      disabled={disabled}
      onClick={onClick}
      className="rounded-sm px-1 text-[10px] leading-4 text-text-faint hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-25"
    >
      {children}
    </button>
  )
}
