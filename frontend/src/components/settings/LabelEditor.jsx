// Frontend: 設定 › 標籤 - the labels, one section per library they belong to.
//
// Every label belongs to exactly one library (`scope`: ingredient, dish or
// note - a recipe shows its dish's). So the tab is three sections, in the
// order the API serves the scopes (食材, 料理, 筆記), each with its labels and
// its own add line; a label is added inside the library it is for, and two
// libraries wanting 辣 have a 辣 each.
//
// A row is a NameRow - 改名 and 刪除 as every vocabulary's - plus 「移到」,
// which moves the label to another library. **Only an unused label moves**:
// one in use would leave its owners carrying another library's label, and the
// server refuses that with a 409 carrying `usage_count`. The select is off
// while the label is in use and the row says why; the server's refusal (the
// count changed since the page read it) is said in the row too.
//
// One read of every label, grouped here, rather than a read per section: the
// three sections are one tab, and a move takes a row from one to another.
import { useState } from 'react'

import { endpoints } from '../../api/endpoints'
import { useApiMutation, useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { Section, Select } from '../ui/primitives'
import { Empty, ErrorNote, Loading } from '../ui/states'
import AddNameForm from './AddNameForm'
import NameRow from './NameRow'

// The count a label's own library fills: only that one can be non-zero.
const COUNT_FIELD = { ingredient: 'ingredient_count', dish: 'dish_count', note: 'note_count' }

// A label change shows wherever labels are shown: the list itself, the three
// owners, and the recipes that show their dish's.
const INVALIDATE = [
  endpoints.labels.list(),
  endpoints.ingredients.list(),
  endpoints.dishes.list(),
  endpoints.recipes.list(),
  endpoints.notes.list(),
]

function MoveSelect({ row, scopes, onMove }) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const others = scopes.filter((scope) => scope.value !== row.scope)

  async function move(event) {
    const scope = event.target.value
    if (!scope) return
    setBusy(true)
    setError(null)
    try {
      await onMove(scope)
    } catch (caught) {
      setError(caught?.message || '移動失敗。')
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <Select
        aria-label={`把「${row.display_name}」移到`}
        className="w-auto py-1 text-xs"
        value=""
        onChange={move}
        disabled={busy || row.usage_count > 0}
      >
        <option value="">移到…</option>
        {others.map((scope) => (
          <option key={scope.value} value={scope.value}>
            {scope.label}標籤
          </option>
        ))}
      </Select>
      {error ? (
        <p role="alert" className="w-full text-sm text-danger">
          {error}
        </p>
      ) : null}
    </>
  )
}

function ScopeSection({ scope, scopes, rows, create, update, remove }) {
  const title = `${scope.label}標籤`
  const count = (row) => row[COUNT_FIELD[scope.value]] ?? row.usage_count

  return (
    <Section title={title} as="h3">
      {rows.length === 0 ? <Empty>還沒有任何{title}。</Empty> : null}
      {rows.length ? (
        <ul className="space-y-1" aria-label={title}>
          {rows.map((row) => (
            <NameRow
              key={row.id}
              item={row}
              meta={
                row.usage_count
                  ? `貼在 ${count(row)} 個${scope.label}上 · 要先拿掉才能移到別的標籤分類`
                  : '沒有使用'
              }
              onRename={(names) => update.mutateAsync({ url: endpoints.labels.update(row.id), body: names })}
              onDelete={() => remove.mutateAsync({ url: endpoints.labels.remove(row.id) })}
              confirmText={
                row.usage_count
                  ? `它會從 ${row.usage_count} 個${scope.label}上拿掉；那些${scope.label}本身不受影響。`
                  : `沒有任何${scope.label}貼著它。`
              }
            >
              <MoveSelect
                row={row}
                scopes={scopes}
                onMove={(next) =>
                  update.mutateAsync({ url: endpoints.labels.update(row.id), body: { scope: next } })
                }
              />
            </NameRow>
          ))}
        </ul>
      ) : null}
      <AddNameForm
        label={`新增${title}`}
        onAdd={(names) =>
          create.mutateAsync({ url: endpoints.labels.create(), body: { ...names, scope: scope.value } })
        }
      />
    </Section>
  )
}

export default function LabelEditor() {
  const list = useApiQuery(endpoints.labels.list())
  const fixed = useFixedVocabularies()
  const create = useApiMutation({ method: 'POST', invalidate: INVALIDATE })
  const update = useApiMutation({ method: 'PATCH', invalidate: INVALIDATE })
  const remove = useApiMutation({ method: 'DELETE', invalidate: INVALIDATE })
  const scopes = fixed.data?.label_scopes ?? []

  return (
    <Section title="標籤">
      <p className="text-sm text-text-muted">
        跨分類的標記。每個標籤屬於一個地方：食材、料理或筆記，表單和篩選只列出那裡的標籤；食譜顯示它的料理的標籤。依名稱排列。
      </p>

      {list.isPending || fixed.isPending ? <Loading /> : null}
      {list.isError ? <ErrorNote error={list.error} /> : null}
      {fixed.isError ? <ErrorNote error={fixed.error} /> : null}

      {list.isSuccess && fixed.isSuccess
        ? scopes.map((scope) => (
            <ScopeSection
              key={scope.value}
              scope={scope}
              scopes={scopes}
              rows={list.data.filter((row) => row.scope === scope.value)}
              create={create}
              update={update}
              remove={remove}
            />
          ))
        : null}
    </Section>
  )
}
