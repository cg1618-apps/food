import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import {
  Button,
  Card,
  ErrorNote,
  Field,
  Input,
  Loading,
  Select,
  TextArea,
} from '../../components/ui'
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import { flatten } from '../../lib/tree'
import DeleteIngredientDialog from './DeleteIngredientDialog'

const METHODS = ['常溫', '冷藏', '冷凍', '乾燥', '醃漬', '油封', '真空']

const EMPTY = {
  name_cn: '',
  name_en: '',
  name_alt: '',
  category_id: '',
  parent_id: '',
  description: '',
  selection_notes: '',
  sourcing_notes: '',
  preservation_notes: '',
  needs_detail: false,
  aliases: '',
  preservation: [],
  label_ids: [],
}

export default function IngredientForm() {
  const { id } = useParams()
  const isNew = id === undefined
  const navigate = useNavigate()

  const existing = useApiQuery(endpoints.ingredients.detail(id), null, { enabled: !isNew })
  const categories = useApiQuery(endpoints.categories.tree())
  const labels = useApiQuery(endpoints.labels.list())
  const allIngredients = useApiQuery(endpoints.ingredients.list())

  const [form, setForm] = useState(EMPTY)
  const [loadedFor, setLoadedFor] = useState(null)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(false)

  const flatCategories = useMemo(() => flatten(categories.data ?? []), [categories.data])

  // The fallback category is what a new ingredient defaults to, so adding one
  // never opens with a taxonomy question. Derived at render rather than
  // written into state by an effect: it depends only on data already here.
  const fallbackId = flatCategories.find((node) => node.is_fallback)?.id
  const categoryValue = form.category_id || (isNew && fallbackId ? String(fallbackId) : '')

  // Adjusting state when the loaded row changes, during render - the pattern
  // React documents for exactly this, and the reason there is no effect here.
  // An effect would render once with the empty form, then again with the real
  // one, which is a visible flash on a slow connection and an extra render on
  // every keystroke-free load.
  if (!isNew && existing.data && loadedFor !== existing.data.id) {
    const row = existing.data
    setLoadedFor(row.id)
    setForm({
      name_cn: row.name_cn ?? '',
      name_en: row.name_en ?? '',
      name_alt: row.name_alt ?? '',
      category_id: String(row.category?.id ?? ''),
      parent_id: row.parent ? String(row.parent.id) : '',
      description: row.description ?? '',
      selection_notes: row.selection_notes ?? '',
      sourcing_notes: row.sourcing_notes ?? '',
      preservation_notes: row.preservation_notes ?? '',
      needs_detail: row.needs_detail,
      aliases: row.aliases.join(', '),
      preservation: row.preservation.map((entry) => ({
        method: entry.method,
        duration_days: entry.duration_days ?? '',
        notes: entry.notes ?? '',
        sort_order: entry.sort_order ?? 0,
      })),
      label_ids: row.labels.map((label) => label.id),
    })
  }

  const create = useApiMutation({ method: 'POST', invalidate: [endpoints.ingredients.list()] })
  const update = useApiMutation({ method: 'PATCH', invalidate: [endpoints.ingredients.list()] })

  const set = (field) => (event) =>
    setForm((previous) => ({ ...previous, [field]: event.target.value }))

  const setEntry = (index, patch) =>
    setForm((previous) => {
      const next = [...previous.preservation]
      next[index] = { ...next[index], ...patch }
      return { ...previous, preservation: next }
    })

  function payload() {
    return {
      name_cn: form.name_cn || null,
      name_en: form.name_en || null,
      name_alt: form.name_alt || null,
      category_id: Number(categoryValue),
      parent_id: form.parent_id ? Number(form.parent_id) : null,
      description: form.description || null,
      selection_notes: form.selection_notes || null,
      sourcing_notes: form.sourcing_notes || null,
      preservation_notes: form.preservation_notes || null,
      needs_detail: form.needs_detail,
      aliases: form.aliases
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean),
      preservation: form.preservation
        .filter((entry) => entry.method)
        .map((entry) => ({
          method: entry.method,
          // An empty number input means "unknown", which is null - not 0,
          // which the CHECK constraint refuses and which would surface as a
          // confusing 422 about a field deliberately left blank.
          duration_days: entry.duration_days === '' ? null : Number(entry.duration_days),
          notes: entry.notes || null,
          sort_order: entry.sort_order ?? 0,
        })),
      label_ids: form.label_ids,
    }
  }

  async function submit(event) {
    event.preventDefault()
    setError(null)
    try {
      const body = payload()
      const saved = isNew
        ? await create.mutateAsync({ url: endpoints.ingredients.create(), body })
        : await update.mutateAsync({ url: endpoints.ingredients.update(id), body })
      navigate(`/ingredient/${saved.id}`)
    } catch (caught) {
      setError(caught)
    }
  }

  if (!isNew && existing.isPending) return <Loading />

  return (
    <form onSubmit={submit} className="space-y-4">
      <h1 className="text-xl font-semibold">
        {isNew ? 'Add an ingredient' : `Edit ${existing.data?.display_name ?? ''}`}
      </h1>

      {error ? <ErrorNote error={error} /> : null}

      <Card className="grid gap-3 sm:grid-cols-3">
        <Field label="中文名">
          <Input value={form.name_cn} onChange={set('name_cn')} />
        </Field>
        <Field label="English">
          <Input value={form.name_en} onChange={set('name_en')} />
        </Field>
        <Field label="Other name" hint="A formal alternative, shown on the page">
          <Input value={form.name_alt} onChange={set('name_alt')} />
        </Field>
      </Card>

      <Card className="grid gap-3 sm:grid-cols-2">
        <Field label="Category">
          <Select value={categoryValue} onChange={set('category_id')} required>
            {flatCategories.map((node) => (
              <option key={node.id} value={node.id}>
                {'— '.repeat(node.depth)}
                {node.display_name}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="A kind of" hint="Leave empty unless this is a specific sort of something">
          <Select value={form.parent_id} onChange={set('parent_id')}>
            <option value="">—</option>
            {(allIngredients.data ?? [])
              .filter((row) => String(row.id) !== String(id))
              .map((row) => (
                <option key={row.id} value={row.id}>
                  {row.display_name}
                </option>
              ))}
          </Select>
        </Field>
        <Field label="Aliases" hint="Comma separated. What you might type to find it.">
          <Input value={form.aliases} onChange={set('aliases')} />
        </Field>
        <Field label="Labels">
          <div className="flex flex-wrap gap-2 pt-1">
            {(labels.data ?? []).map((label) => (
              <label key={label.id} className="flex items-center gap-1 text-sm">
                <input
                  type="checkbox"
                  checked={form.label_ids.includes(label.id)}
                  onChange={(event) =>
                    setForm((previous) => ({
                      ...previous,
                      label_ids: event.target.checked
                        ? [...previous.label_ids, label.id]
                        : previous.label_ids.filter((value) => value !== label.id),
                    }))
                  }
                />
                {label.display_name}
              </label>
            ))}
          </div>
        </Field>
      </Card>

      <Card className="space-y-3">
        <h2 className="text-sm font-semibold text-text-muted">Keeping it</h2>
        {form.preservation.map((entry, index) => (
          <div key={index} className="grid gap-2 sm:grid-cols-4">
            <Select
              value={entry.method}
              onChange={(event) => setEntry(index, { method: event.target.value })}
            >
              <option value="">—</option>
              {METHODS.map((method) => (
                <option key={method} value={method}>
                  {method}
                </option>
              ))}
            </Select>
            <Input
              type="number"
              min="1"
              placeholder="days"
              value={entry.duration_days}
              onChange={(event) => setEntry(index, { duration_days: event.target.value })}
            />
            <Input
              className="sm:col-span-2"
              placeholder="3–5 天, less once cut"
              value={entry.notes}
              onChange={(event) => setEntry(index, { notes: event.target.value })}
            />
          </div>
        ))}
        <Button
          type="button"
          onClick={() =>
            setForm((previous) => ({
              ...previous,
              preservation: [
                ...previous.preservation,
                {
                  method: '',
                  duration_days: '',
                  notes: '',
                  sort_order: previous.preservation.length,
                },
              ],
            }))
          }
        >
          Add a way
        </Button>
      </Card>

      <Card className="space-y-3">
        <Field label="What it is">
          <TextArea value={form.description} onChange={set('description')} />
        </Field>
        <Field label="Picking a good one">
          <TextArea value={form.selection_notes} onChange={set('selection_notes')} />
        </Field>
        <Field label="Where to get it">
          <TextArea value={form.sourcing_notes} onChange={set('sourcing_notes')} />
        </Field>
        <Field label="Keeping it — general">
          <TextArea value={form.preservation_notes} onChange={set('preservation_notes')} />
        </Field>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.needs_detail}
            onChange={(event) =>
              setForm((previous) => ({ ...previous, needs_detail: event.target.checked }))
            }
          />
          Still needs detail
        </label>
      </Card>

      <div className="flex flex-wrap gap-2">
        <Button type="submit" variant="primary">
          Save
        </Button>
        <Button type="button" onClick={() => navigate(-1)}>
          Cancel
        </Button>
        {!isNew ? (
          <Button type="button" variant="danger" onClick={() => setDeleting(true)}>
            Delete
          </Button>
        ) : null}
      </div>

      {deleting ? (
        <DeleteIngredientDialog
          id={id}
          name={existing.data?.display_name}
          onClose={() => setDeleting(false)}
          onDeleted={() => navigate('/library/ingredient')}
        />
      ) : null}
    </form>
  )
}
