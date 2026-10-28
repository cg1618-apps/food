// Frontend: 「轉成食材」 - the ingredient being saved has a category's name.
//
// A name is a category or an ingredient, never both. The save answered 409
// with `category_clash`, a preview computed by the same function the
// conversion runs; this dialog says it in words, item by item:
//
//   - which category goes, and where its ingredients are re-filed - its
//     parent, or, for a top-level category, the category picked here
//     (default 未分類; the category itself and anything below it are not
//     offered, the server refuses them);
//   - whether this ingredient is re-filed too (its own category is the one
//     going);
//   - which ingredients become its varieties, which keep the parent they
//     have, and which stay top-level because they sit above it;
//   - which child categories move up, and where;
//   - whether the category's notes become its 說明 or are dropped.
//
// A child category whose name is already taken one level up blocks the
// conversion: the dialog says which, and 轉換 stays off.
//
// 轉換 resends the same save with `convert_category`; if the plan changed
// since the preview, the server answers 409 with the fresh one, which
// replaces this one and asks again, as the merge dialog does. 取消 closes the
// dialog and leaves the form as it was, unsaved.
import { useState } from 'react'

import { flatten, subtreeIds } from '../../lib/tree'
import Dialog from '../ui/Dialog'
import { Button, Field, Select } from '../ui/primitives'
import { ErrorNote } from '../ui/states'

const names = (refs) => refs.map((ref) => `「${ref.display_name}」`).join('、')

export default function CategoryClashDialog({ preview: initial, ingredientName, categories, onConfirm, onClose }) {
  const [fresh, setFresh] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const preview = fresh ?? initial

  const flat = flatten(categories ?? [])
  const node = flat.find((entry) => entry.id === preview.category.id)
  const excluded = new Set(node ? subtreeIds(node) : [preview.category.id])
  const choices = flat.filter((entry) => !excluded.has(entry.id))
  const fallbackId = flat.find((entry) => entry.is_fallback)?.id
  const [chosen, setChosen] = useState(fallbackId ? String(fallbackId) : '')

  const target = preview.choose_target
    ? choices.find((entry) => String(entry.id) === chosen)
    : preview.target
  const blocked = preview.blocked_by.length > 0
  const category = preview.category.display_name

  async function confirm() {
    setBusy(true)
    setError(null)
    try {
      await onConfirm({
        category_id: preview.category.id,
        target_category_id: preview.choose_target ? Number(chosen) : null,
        fingerprint: preview.fingerprint,
      })
    } catch (caught) {
      if (caught.status === 409 && caught.body?.category_clash) {
        setFresh(caught.body.category_clash)
      } else {
        setError(caught)
      }
    } finally {
      setBusy(false)
    }
  }

  const where = target ? `「${target.display_name}」` : '選的分類'

  return (
    <Dialog
      title={`「${category}」是分類`}
      size="md"
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            取消
          </Button>
          <Button
            kind="primary"
            onClick={confirm}
            disabled={busy || blocked || (preview.choose_target && !chosen)}
          >
            {busy ? '轉換中…' : fresh ? '確認轉換' : '轉成食材'}
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-text">
        <p>
          一個名字只能是分類或食材其中之一。可以把分類「{category}」轉成食材「{ingredientName}」，和這次的儲存一起完成：
        </p>

        {fresh ? (
          <p role="status" className="rounded-md border border-warn/50 px-3 py-2 text-warn">
            預覽之後這個分類或它底下的東西有人改過，下面是現在的轉換內容，請再確認一次。
          </p>
        ) : null}

        {preview.choose_target ? (
          <Field label="它的食材移到哪個分類" hint={`「${category}」是最上層的分類，沒有上層可以接手。`}>
            <Select value={chosen} onChange={(event) => setChosen(event.target.value)}>
              {chosen ? null : <option value="">—</option>}
              {choices.map((entry) => (
                <option key={entry.id} value={entry.id}>
                  {'　'.repeat(entry.depth)}
                  {entry.display_name}
                </option>
              ))}
            </Select>
          </Field>
        ) : null}

        <ul className="list-disc space-y-1 pl-5">
          <li>刪除分類「{category}」</li>
          {preview.takes_target ? <li>這個食材改放在{where}</li> : null}
          {preview.adopted.length ? (
            <li>
              {names(preview.adopted)} 移到{where}，成為「{ingredientName}」的品種
            </li>
          ) : null}
          {preview.varieties.length ? (
            <li>{names(preview.varieties)} 移到{where}，仍是原本那個食材的品種</li>
          ) : null}
          {preview.kept_top_level.length ? (
            <li>
              {names(preview.kept_top_level)} 移到{where}，但不會變成品種：它在「{ingredientName}」的上層
            </li>
          ) : null}
          {preview.child_categories.length ? (
            <li>
              子分類 {names(preview.child_categories)} 移上一層，到
              {preview.child_parent ? `「${preview.child_parent.display_name}」底下` : '最上層'}
              ，裡面的食材不動
            </li>
          ) : null}
          {preview.description === 'moved' ? <li>分類的說明變成這個食材的「是什麼」</li> : null}
        </ul>

        {preview.description === 'dropped' ? (
          <p className="rounded-md bg-warn-soft px-3 py-2 text-warn">
            這個食材已經有自己的「是什麼」，分類的說明會捨棄。
          </p>
        ) : null}

        {blocked ? (
          <div role="alert" className="space-y-1 rounded-md border border-danger/50 px-3 py-2 text-danger">
            <p>不能轉換：這些子分類移上去會和同一層的分類同名，請先到未來固定設定改名。</p>
            <ul className="list-disc pl-5">
              {preview.blocked_by.map((pair) => (
                <li key={pair.category.id}>「{pair.category.display_name}」</li>
              ))}
            </ul>
          </div>
        ) : null}

        {error ? <ErrorNote error={error} /> : null}
      </div>
    </Dialog>
  )
}
