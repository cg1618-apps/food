// Frontend: add or edit an ingredient, /edit/ingredients/new and
// /edit/ingredients/:id.
//
// In the order the page reads: names and where it is filed (category, the
// ingredient it is a variety of, rating, labels, aliases); the prose -
// what it is, picking one, where to get it, keeping it; storage rows (state,
// method, a min-max range in days, notes); heating rows (method, °C with the
// °F beside it, duration, preheat, flip, notes); links; the 待補 flag; the
// gallery. Every list is the shared RowEditor; every closed list comes from
// the backend (useFixedVocabularies), not a copy.
//
// Saving goes to the ingredient's page.
import { useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import ChipPicker from '../../components/forms/ChipPicker'
import DeleteDialog from '../../components/forms/DeleteDialog'
import FormActions from '../../components/forms/FormActions'
import GalleryPicker from '../../components/forms/GalleryPicker'
import RowEditor from '../../components/forms/RowEditor'
import Typeahead, { Picked } from '../../components/forms/Typeahead'
import { Field, Input, Section, Select, TextArea } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { useOwnerSave } from '../../hooks/useOwnerSave'
import { galleryChanged, galleryFromImages } from '../../lib/gallery'
import { blankToNull, integerOrNull, keyed, splitAliases } from '../../lib/rowList'
import { toFahrenheit } from '../../lib/temperature'
import { flatten } from '../../lib/tree'
import { reconcileMinDays } from './storageDuration'

// An ingredient save moves more than the ingredient's own reads: category and
// label counts, cooking-method usage (heating rows), the recipes whose lines
// name it, the image library's usage counts, and 常用食材 (a renamed
// ingredient is a renamed chip).
const INVALIDATE = [
  endpoints.ingredients.list(),
  endpoints.commonIngredients.list(),
  endpoints.categories.tree(),
  endpoints.labels.list(),
  endpoints.methods.list(),
  endpoints.recipes.list(),
  endpoints.images.list(),
]

const EMPTY = {
  name_cn: '',
  name_en: '',
  name_alt: '',
  category_id: '',
  parent: null,
  rating: '',
  label_ids: [],
  aliases: '',
  description: '',
  selection_notes: '',
  sourcing_notes: '',
  preservation_notes: '',
  needs_detail: false,
  preservation: [],
  heating: [],
  links: [],
  gallery: [],
}

const text = (value) => (value === null || value === undefined ? '' : String(value))

// A storage row keeps the range it was loaded with, so the shortest time can
// follow the longest while nobody has touched it (storageDuration.js).
function storageRow(entry = {}) {
  return keyed({
    state: entry.state ?? 'unused',
    method: entry.method ?? '',
    min: text(entry.duration_min_days),
    max: text(entry.duration_max_days),
    loadedMin: entry.duration_min_days ?? null,
    loadedMax: entry.duration_max_days ?? null,
    minTouched: false,
    notes: entry.notes ?? '',
  })
}

function heatingRow(entry = {}) {
  return keyed({
    method_id: entry.method ? String(entry.method.id) : '',
    temperature_c: text(entry.temperature_c),
    duration: entry.duration ?? '',
    preheat: Boolean(entry.preheat),
    flip: Boolean(entry.flip),
    notes: entry.notes ?? '',
  })
}

const linkRow = (entry = {}) => keyed({ url: entry.url ?? '', title: entry.title ?? '' })

function fromIngredient(row) {
  return {
    name_cn: row.name_cn ?? '',
    name_en: row.name_en ?? '',
    name_alt: row.name_alt ?? '',
    category_id: row.category ? String(row.category.id) : '',
    parent: row.parent ? { id: row.parent.id, label: row.parent.display_name } : null,
    rating: row.rating ?? '',
    label_ids: (row.labels ?? []).map((label) => label.id),
    aliases: (row.aliases ?? []).join('、'),
    description: row.description ?? '',
    selection_notes: row.selection_notes ?? '',
    sourcing_notes: row.sourcing_notes ?? '',
    preservation_notes: row.preservation_notes ?? '',
    needs_detail: Boolean(row.needs_detail),
    preservation: (row.preservation ?? []).map(storageRow),
    heating: (row.heating ?? []).map(heatingRow),
    links: (row.links ?? []).map(linkRow),
    gallery: galleryFromImages(row.images),
  }
}

export default function IngredientForm() {
  const { id } = useParams()
  const isNew = id === undefined
  const navigate = useNavigate()

  const existing = useApiQuery(endpoints.ingredients.detail(id), null, { enabled: !isNew })
  const categories = useApiQuery(endpoints.categories.tree())
  const labels = useApiQuery(endpoints.labels.list())
  const methods = useApiQuery(endpoints.methods.list())
  const fixed = useFixedVocabularies()
  const { save, saving } = useOwnerSave({ group: endpoints.ingredients, invalidate: INVALIDATE })

  const [form, setForm] = useState(EMPTY)
  const [loaded, setLoaded] = useState(null)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(false)
  // Typed into the parent box and not picked: refused on save, never dropped.
  const [parentTyped, setParentTyped] = useState('')
  // The category select is required and the storage and heating rows' selects
  // are drawn from these lists: Save waits for them.
  const vocabulariesReady = Boolean(categories.data && fixed.data && methods.data)

  const flatCategories = useMemo(() => flatten(categories.data ?? []), [categories.data])
  // A new ingredient is filed in the fallback category until told otherwise,
  // so adding one never opens with a taxonomy question.
  const fallbackId = flatCategories.find((node) => node.is_fallback)?.id
  const categoryValue = form.category_id || (isNew && fallbackId ? String(fallbackId) : '')

  // Adjusting state to the loaded row during render, keyed on the id so a
  // background refetch never throws away what is being typed.
  if (!isNew && existing.data && loaded?.id !== existing.data.id) {
    setLoaded(existing.data)
    setForm(fromIngredient(existing.data))
  }

  const setField = (field, value) => setForm((previous) => ({ ...previous, [field]: value }))
  const set = (field) => (event) => setField(field, event.target.value)

  function payload() {
    return {
      name_cn: blankToNull(form.name_cn),
      name_en: blankToNull(form.name_en),
      name_alt: blankToNull(form.name_alt),
      category_id: Number(categoryValue),
      parent_id: form.parent?.id ?? null,
      rating: form.rating || null,
      label_ids: form.label_ids,
      aliases: splitAliases(form.aliases),
      description: blankToNull(form.description),
      selection_notes: blankToNull(form.selection_notes),
      sourcing_notes: blankToNull(form.sourcing_notes),
      preservation_notes: blankToNull(form.preservation_notes),
      needs_detail: form.needs_detail,
      preservation: form.preservation.map((row, index) => ({
        state: row.state,
        method: row.method,
        // An empty box is "unknown", which is null - not 0, which the CHECK
        // refuses with a 422 about a field deliberately left blank.
        duration_min_days: integerOrNull(row.min),
        duration_max_days: integerOrNull(row.max),
        notes: blankToNull(row.notes),
        sort_order: index,
      })),
      heating: form.heating.map((row) => ({
        method_id: Number(row.method_id),
        temperature_c: integerOrNull(row.temperature_c),
        duration: blankToNull(row.duration),
        preheat: row.preheat,
        flip: row.flip,
        notes: blankToNull(row.notes),
      })),
      links: form.links.map((row) => ({ url: row.url.trim(), title: blankToNull(row.title) })),
    }
  }

  async function submit(event) {
    event.preventDefault()
    setError(null)
    if (!form.parent && parentTyped.trim()) {
      setError(
        new Error(`「是哪種食材的品種」打了「${parentTyped.trim()}」，但還沒從清單選：選一個，或把文字清掉。`),
      )
      return
    }
    try {
      const saved = await save({
        id,
        body: payload(),
        gallery: form.gallery,
        galleryDirty: galleryChanged(galleryFromImages(loaded?.images), form.gallery),
      })
      navigate(`/ingredients/${saved.id}`)
    } catch (caught) {
      setError(caught)
    }
  }

  const options = (list) =>
    (list ?? []).map((entry) => (
      <option key={entry.value} value={entry.value}>
        {entry.label}
      </option>
    ))

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl font-bold">{isNew ? '新增食材' : '編輯食材'}</h1>
        {!isNew && existing.data ? (
          <p className="text-sm text-text-muted">{existing.data.display_name}</p>
        ) : null}
      </header>

      {!isNew && existing.isPending ? <Loading /> : null}
      {!isNew && existing.error ? <ErrorNote error={existing.error} /> : null}
      {categories.error ? (
        <ErrorNote error={categories.error}>分類載入失敗，暫時不能儲存：{categories.error.message}</ErrorNote>
      ) : null}

      {isNew || existing.data ? (
        <>
          <Section title="名稱與分類">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="中文名">
                <Input value={form.name_cn} onChange={set('name_cn')} />
              </Field>
              <Field label="英文名">
                <Input value={form.name_en} onChange={set('name_en')} />
              </Field>
              <Field label="其他名稱" hint="正式的另一個名字，會顯示">
                <Input value={form.name_alt} onChange={set('name_alt')} />
              </Field>
              <Field label="分類">
                <Select value={categoryValue} onChange={set('category_id')} required>
                  {categoryValue ? null : <option value="">—</option>}
                  {flatCategories.map((node) => (
                    <option key={node.id} value={node.id}>
                      {'　'.repeat(node.depth)}
                      {node.display_name}
                    </option>
                  ))}
                </Select>
              </Field>
              <div className="space-y-1 sm:col-span-2">
                <span className="text-sm font-medium text-text-muted">是哪種食材的品種</span>
                {form.parent ? (
                  <Picked
                    label={form.parent.label}
                    onClear={() => {
                      setField('parent', null)
                      setParentTyped('')
                    }}
                    clearLabel="移除"
                  />
                ) : (
                  <Typeahead
                    sources={['ingredient']}
                    label="是哪種食材的品種"
                    placeholder="不是品種就留空"
                    exclude={{ ingredient: id ? [Number(id)] : [] }}
                    onSelect={(option) => setField('parent', { id: option.id, label: option.label })}
                    onQueryChange={setParentTyped}
                  />
                )}
              </div>
              <Field label="評等">
                <Select value={form.rating} onChange={set('rating')}>
                  <option value="">—</option>
                  {options(fixed.data?.ratings)}
                </Select>
              </Field>
              <Field label="別名" className="sm:col-span-2" hint="用逗號或頓號分開。搜尋得到，但不顯示。">
                <Input value={form.aliases} onChange={set('aliases')} />
              </Field>
            </div>
            <div className="space-y-1">
              <span className="text-sm font-medium text-text-muted">標籤</span>
              <ChipPicker
                label="標籤"
                options={labels.data}
                value={form.label_ids}
                onChange={(label_ids) => setField('label_ids', label_ids)}
                empty="還沒有標籤，可以在設定裡新增。"
              />
            </div>
          </Section>

          <Section title="說明">
            <Field label="是什麼">
              <TextArea value={form.description} onChange={set('description')} />
            </Field>
            <Field label="挑選">
              <TextArea value={form.selection_notes} onChange={set('selection_notes')} />
            </Field>
            <Field label="哪裡買">
              <TextArea rows={3} value={form.sourcing_notes} onChange={set('sourcing_notes')} />
            </Field>
          </Section>

          <Section title="保存">
            <RowEditor
              rows={form.preservation}
              onChange={(rows) => setField('preservation', rows)}
              newRow={() => storageRow()}
              addLabel="加一種保存方式"
              itemLabel="保存方式"
            >
              {(row, { update }) => (
                <div className="grid gap-2 sm:grid-cols-6">
                  <Select
                    aria-label="狀態"
                    value={row.state}
                    onChange={(event) => update({ state: event.target.value })}
                    className="sm:col-span-2"
                  >
                    {options(fixed.data?.preservation_states)}
                  </Select>
                  <Select
                    aria-label="方式"
                    value={row.method}
                    required
                    onChange={(event) => update({ method: event.target.value })}
                    className="sm:col-span-2"
                  >
                    <option value="">方式…</option>
                    {options(fixed.data?.preservation_methods)}
                  </Select>
                  <Input
                    aria-label="最短天數"
                    type="number"
                    min="1"
                    placeholder="最短天"
                    value={row.min}
                    onChange={(event) => update({ min: event.target.value, minTouched: true })}
                  />
                  <Input
                    aria-label="最長天數"
                    type="number"
                    min="1"
                    placeholder="最長天"
                    value={row.max}
                    onChange={(event) => {
                      const patch = { max: event.target.value }
                      // A range stored as one number (min = max) follows the
                      // longest time until the shortest is edited itself.
                      if (!row.minTouched && row.loadedMin !== null) {
                        patch.min = text(
                          reconcileMinDays({
                            loadedMin: row.loadedMin,
                            loadedMax: row.loadedMax,
                            editedMax: event.target.value,
                          }),
                        )
                      }
                      update(patch)
                    }}
                  />
                  <Input
                    aria-label="保存備註"
                    placeholder="備註，例如切開後要包好"
                    value={row.notes}
                    onChange={(event) => update({ notes: event.target.value })}
                    className="sm:col-span-6"
                  />
                </div>
              )}
            </RowEditor>
            <Field label="保存的整體說明">
              <TextArea rows={3} value={form.preservation_notes} onChange={set('preservation_notes')} />
            </Field>
          </Section>

          <Section title="加熱">
            <RowEditor
              rows={form.heating}
              onChange={(rows) => setField('heating', rows)}
              newRow={() => heatingRow()}
              addLabel="加一種加熱方式"
              itemLabel="加熱方式"
            >
              {(row, { update }) => {
                const fahrenheit = toFahrenheit(row.temperature_c)
                return (
                  <div className="grid gap-2 sm:grid-cols-6">
                    <Select
                      aria-label="做法"
                      value={row.method_id}
                      required
                      onChange={(event) => update({ method_id: event.target.value })}
                      className="sm:col-span-2"
                    >
                      <option value="">做法…</option>
                      {(methods.data ?? []).map((method) => (
                        <option key={method.id} value={method.id}>
                          {method.display_name}
                        </option>
                      ))}
                    </Select>
                    <div className="flex items-center gap-1.5 sm:col-span-2">
                      <Input
                        aria-label="溫度（°C）"
                        type="number"
                        min="1"
                        step="1"
                        placeholder="°C"
                        value={row.temperature_c}
                        onChange={(event) => update({ temperature_c: event.target.value })}
                      />
                      <span className="shrink-0 text-xs tabular-nums text-text-faint" aria-live="polite">
                        {fahrenheit === null ? '°F' : `${fahrenheit}°F`}
                      </span>
                    </div>
                    <Input
                      aria-label="時間"
                      placeholder="時間，例如 12 分鐘"
                      value={row.duration}
                      onChange={(event) => update({ duration: event.target.value })}
                      className="sm:col-span-2"
                    />
                    <label className="flex items-center gap-1.5 text-sm">
                      <input
                        type="checkbox"
                        checked={row.preheat}
                        onChange={(event) => update({ preheat: event.target.checked })}
                      />
                      預熱
                    </label>
                    <label className="flex items-center gap-1.5 text-sm">
                      <input
                        type="checkbox"
                        checked={row.flip}
                        onChange={(event) => update({ flip: event.target.checked })}
                      />
                      翻面
                    </label>
                    <Input
                      aria-label="加熱備註"
                      placeholder="備註"
                      value={row.notes}
                      onChange={(event) => update({ notes: event.target.value })}
                      className="sm:col-span-4"
                    />
                  </div>
                )
              }}
            </RowEditor>
          </Section>

          <Section title="連結">
            <RowEditor
              rows={form.links}
              onChange={(rows) => setField('links', rows)}
              newRow={() => linkRow()}
              addLabel="加一個連結"
              itemLabel="連結"
            >
              {(row, { update }) => (
                <div className="grid gap-2 sm:grid-cols-2">
                  <Input
                    aria-label="網址"
                    type="url"
                    required
                    placeholder="https://"
                    value={row.url}
                    onChange={(event) => update({ url: event.target.value })}
                  />
                  <Input
                    aria-label="標題"
                    placeholder="標題（可留空）"
                    value={row.title}
                    onChange={(event) => update({ title: event.target.value })}
                  />
                </div>
              )}
            </RowEditor>
          </Section>

          <Section title="圖片">
            <GalleryPicker value={form.gallery} onChange={(gallery) => setField('gallery', gallery)} />
          </Section>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={form.needs_detail}
              onChange={(event) => setField('needs_detail', event.target.checked)}
            />
            還有細節待補（顯示 待補）
          </label>

          <FormActions
            saving={saving}
            ready={vocabulariesReady}
            error={error}
            onCancel={() => navigate(isNew ? '/ingredients' : `/ingredients/${id}`)}
            onDelete={isNew ? null : () => setDeleting(true)}
          />
        </>
      ) : null}

      {deleting ? (
        <DeleteDialog
          kind="ingredient"
          id={id}
          name={existing.data?.display_name}
          onClose={() => setDeleting(false)}
        />
      ) : null}
    </form>
  )
}
