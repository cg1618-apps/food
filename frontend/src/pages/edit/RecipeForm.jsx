// Frontend: add or edit a recipe, /edit/recipes/new and /edit/recipes/:id.
//
// A new recipe asks first how to start (NewRecipeChooser): 空白, 從範本 or
// 複製另一份食譜. The answer is in the URL (lib/newRecipe.js) - ?blank=1,
// ?template=<id>, ?from=<recipe id> - and the form opens on it:
//   - from a template: servings, time, the lines and steps in their groups
//     (steps keeping their kinds), methods and equipment. A reference the
//     template still holds to something since deleted is left out by the
//     server, and the form says how many (「範本裡有 n 個項目已不存在，已略過」).
//   - from another recipe: all of that, and its storage notes and notes, with
//     its dish chosen unless ?dish= names another. Not its name, sources,
//     status or pictures - and the form says which recipe it was copied from.
// Nothing is saved until 儲存, and what is saved is a new recipe.
//
// In the order the page reads: the dish this is a recipe of, and the
// recipe's own optional name; status, servings, time; sources; ingredient
// lines; steps; methods, equipment; storage and notes; the gallery. What is
// true of the dish whoever cooks it - names, kind, course, region, labels,
// serves-as, a description - is the dish's form's, not this one's.
//
// The dish is picked with the Typeahead, searching the dish library. When
// nothing matches, 「新增」 names a dish the save creates, as a 料理 or a 醬料
// (料理 unless switched); a name the server already knows is reused instead.
// `?dish=<id>` - the dish page's 「＋ 新增食譜」 - starts a new recipe with that
// dish chosen, whichever start is chosen.
//
// 材料, 步驟 and 做法、器材 are the sections the template form shares
// (components/forms/RecipeLinesSection.jsx, RecipeStepsSection.jsx,
// RecipeMethodsSection.jsx): the 常用 chips, the groups, the line typeahead
// with its 「新增」 and 「新增料理」 - a stub ingredient or a 醬料 made by the
// save, folded into an existing row when the server already knows the name -
// the step kinds and numbering, and 「貼上多行」.
// A source's author is picked from the authors list, which is small enough to
// fetch once and filter in the browser; 「新增」 there makes the author on
// save, and a name the server already knows is reused.
//
// POST takes the whole recipe and PATCH replaces each list wholesale, so the
// form always sends every list - lines with line_groups, steps with
// step_groups, the pairs the server replaces together. Saving goes to the
// recipe's page.
import { useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import DeleteDialog from '../../components/forms/DeleteDialog'
import FormActions from '../../components/forms/FormActions'
import GalleryPicker from '../../components/forms/GalleryPicker'
import RecipeLinesSection from '../../components/forms/RecipeLinesSection'
import RecipeMethodsSection from '../../components/forms/RecipeMethodsSection'
import RecipeStepsSection from '../../components/forms/RecipeStepsSection'
import RowEditor from '../../components/forms/RowEditor'
import Typeahead, { Picked } from '../../components/forms/Typeahead'
import { Field, Input, LinkButton, Section, Select, TextArea, Toggle } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { fixedLabel, useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { useOwnerSave } from '../../hooks/useOwnerSave'
import { galleryChanged, galleryFromImages } from '../../lib/gallery'
import { newRecipeStart } from '../../lib/newRecipe'
import { DISH, newNames, targetFromOption } from '../../lib/recipeLines'
import { authorFromOption, sourceRow, sourcesPayload } from '../../lib/recipeSources'
import { emptyStructure, structureFromResponse, structurePayload } from '../../lib/recipeStructure'
import { blankToNull } from '../../lib/rowList'
import NewRecipeChooser from './NewRecipeChooser'

// A recipe save moves its own reads, the dish library (its dish's recipe
// count, cover and "used in"; a 新增 dish is a new row), the authors list, the
// ingredient library (a 新增 line makes a stub; used-in counts move), the
// category tree (the stub is filed in the fallback category, whose count
// moves), and the usage counts of every vocabulary and picture it names.
const INVALIDATE = [
  endpoints.dishes.list(),
  endpoints.recipes.list(),
  endpoints.authors.list(),
  endpoints.ingredients.list(),
  endpoints.categories.tree(),
  endpoints.statuses.list(),
  endpoints.platforms.list(),
  endpoints.methods.list(),
  endpoints.equipment.list(),
  endpoints.lineGroups.list(),
  endpoints.stepGroups.list(),
  endpoints.images.list(),
]

const empty = () => ({
  // { type: 'dish', id, label, kind } or { type: 'new-dish', label, kind }.
  dish: null,
  name: '',
  // '' until chosen: the first status is shown, and sent, in its place.
  status_id: '',
  // servings, time, lines, steps, method_ids, equipment_ids.
  ...emptyStructure(),
  sources: [],
  storage_notes: '',
  notes: '',
  gallery: [],
})

const dishPick = (dish) => ({ type: 'dish', id: dish.id, label: dish.display_name, kind: dish.kind })

// The recipe's own dish from a typeahead pick: a new one is a 料理 unless the
// form's switch says 醬料 - a line's new dish is the other way round.
const dishFromOption = (option) =>
  option.type === 'new-dish'
    ? { ...targetFromOption(option), kind: DISH }
    : { type: 'dish', id: option.id, label: option.label, kind: option.kind }

function fromRecipe(row) {
  return {
    dish: row.dish ? dishPick(row.dish) : null,
    name: row.name ?? '',
    status_id: row.status ? String(row.status.id) : '',
    ...structureFromResponse(row),
    sources: (row.sources ?? []).map(sourceRow),
    storage_notes: row.storage_notes ?? '',
    notes: row.notes ?? '',
    gallery: galleryFromImages(row.images),
  }
}

// What a copy of another recipe carries: its structure and its two notes.
// Not its name, sources, status or pictures - those are what make it that
// recipe rather than this one.
const copiedFrom = (row) => ({
  ...structureFromResponse(row),
  storage_notes: row.storage_notes ?? '',
  notes: row.notes ?? '',
})

export default function RecipeForm() {
  const { id } = useParams()
  const [searchParams] = useSearchParams()
  const start = id === undefined ? newRecipeStart(searchParams) : null
  if (start && !start.chosen) return <NewRecipeChooser />
  // Keyed by the start, so choosing again from the chooser opens a fresh form.
  return <RecipeEditor key={`${id ?? 'new'}:${start?.template}:${start?.from}`} id={id} start={start} />
}

function RecipeEditor({ id, start }) {
  const isNew = id === undefined
  const navigate = useNavigate()
  // ?dish=<id>: the dish page's 「＋ 新增食譜」. Only a new recipe reads it.
  const presetId = start?.dish ?? null
  const templateId = start?.template ?? null
  const fromId = start?.from ?? null

  const existing = useApiQuery(endpoints.recipes.detail(id), null, { enabled: !isNew })
  const preset = useApiQuery(endpoints.dishes.detail(presetId), null, { enabled: presetId !== null })
  const template = useApiQuery(endpoints.templates.detail(templateId), null, { enabled: templateId !== null })
  const source = useApiQuery(endpoints.recipes.detail(fromId), null, { enabled: fromId !== null })
  const statuses = useApiQuery(endpoints.statuses.list())
  const platforms = useApiQuery(endpoints.platforms.list())
  const authors = useApiQuery(endpoints.authors.list())
  const fixed = useFixedVocabularies()
  const { save, saving } = useOwnerSave({ group: endpoints.recipes, invalidate: INVALIDATE })

  const [form, setForm] = useState(empty)
  const [loaded, setLoaded] = useState(null)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(false)
  // Typed into the dish box and not picked: refused on save, never dropped
  // (Typeahead's onQueryChange).
  const [dishTyped, setDishTyped] = useState('')
  const [presetApplied, setPresetApplied] = useState(false)
  const [prefilled, setPrefilled] = useState(false)

  // Adjusting state to the loaded row during render, keyed on the id so a
  // background refetch never throws away what is being typed.
  if (!isNew && existing.data && loaded?.id !== existing.data.id) {
    setLoaded(existing.data)
    setForm(fromRecipe(existing.data))
  }
  // The preset dish, once, the first time it answers - and never over a dish
  // chosen in the meantime.
  if (isNew && preset.data && !presetApplied) {
    setPresetApplied(true)
    setForm((previous) => (previous.dish ? previous : { ...previous, dish: dishPick(preset.data) }))
  }
  // The start, once, the first time it answers. The form is not drawn until
  // then, so it never lands on top of something already typed.
  if (isNew && !prefilled && template.data) {
    setPrefilled(true)
    setForm((previous) => ({ ...previous, ...structureFromResponse(template.data.body) }))
  }
  if (isNew && !prefilled && source.data) {
    setPrefilled(true)
    setForm((previous) => ({
      ...previous,
      ...copiedFrom(source.data),
      // The copied recipe's dish, unless ?dish= named one.
      dish: presetId !== null || previous.dish ? previous.dish : dishPick(source.data.dish),
    }))
  }
  const starting = templateId !== null ? template : fromId !== null ? source : null

  const setField = (field, value) => setForm((previous) => ({ ...previous, [field]: value }))
  const set = (field) => (event) => setField(field, event.target.value)
  // A section's setter: a value, or (previous) => value from the latest state.
  const setter = (field) => (next) =>
    setForm((previous) => ({ ...previous, [field]: typeof next === 'function' ? next(previous[field]) : next }))

  // A source's typed-but-unpicked author, by the row's key and from the latest
  // state: a pick calls onSelect and then reports '' in the same tick, and
  // RowEditor's update() would build the second change from the rows the
  // first had not yet replaced.
  const setSourcePending = (key, pendingAuthor) =>
    setForm((previous) => ({
      ...previous,
      sources: previous.sources.map((row) => (row._key === key ? { ...row, pendingAuthor } : row)),
    }))
  const firstId = (query) => (query.data?.length ? String(query.data[0].id) : '')
  const statusId = form.status_id || firstId(statuses)
  const platformOf = (row) => row.platform_id || firstId(platforms)

  function payload() {
    return {
      ...(form.dish.type === 'dish'
        ? { dish_id: form.dish.id }
        : { new_dish: { ...newNames(form.dish.label), kind: form.dish.kind } }),
      name: blankToNull(form.name),
      // Left out when there is no status to choose: the server then gives
      // the first one, or says there is none.
      ...(statusId ? { status_id: Number(statusId) } : {}),
      sources: sourcesPayload(form.sources, platformOf),
      ...structurePayload(form),
      storage_notes: blankToNull(form.storage_notes),
      notes: blankToNull(form.notes),
    }
  }

  async function submit(event) {
    event.preventDefault()
    setError(null)
    if (!form.dish) {
      setError(
        new Error(
          dishTyped.trim()
            ? `「料理」打了「${dishTyped.trim()}」，但還沒從清單選：選一道，或選「新增」。`
            : '這份食譜是哪道料理？先選一道，或打名字新增。',
        ),
      )
      return
    }
    try {
      // Inside the try: payload() refuses a line or an author typed and
      // never picked, and that sentence is shown like the server's.
      const saved = await save({
        id,
        body: payload(),
        gallery: form.gallery,
        galleryDirty: galleryChanged(galleryFromImages(loaded?.images), form.gallery),
      })
      navigate(`/recipes/${saved.id}`)
    } catch (caught) {
      setError(caught)
    }
  }

  const dishKinds = fixed.data?.dish_kinds ?? []
  const kindWord = (kind) => fixedLabel(dishKinds, kind)
  const ownDish = form.dish?.type === 'dish' ? [form.dish.id] : []
  const vocabularyOptions = (rows) =>
    (rows ?? []).map((row) => (
      <option key={row.id} value={row.id}>
        {row.display_name}
      </option>
    ))
  // A new recipe's form waits for the start it was opened on; an existing
  // one for the recipe.
  const ready = isNew ? !starting || prefilled : Boolean(existing.data)
  const chooseAgain = `/edit/recipes/new${presetId !== null ? `?dish=${presetId}` : ''}`

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl font-bold">{isNew ? '新增食譜' : '編輯食譜'}</h1>
        {!isNew && existing.data ? (
          <p className="text-sm text-text-muted">{existing.data.display_name}</p>
        ) : null}
        {isNew && template.data ? (
          <div role="status" className="space-y-0.5 text-sm text-text-muted">
            <p>從範本「{template.data.name}」開始。</p>
            {template.data.dropped ? (
              <p className="text-danger">範本裡有 {template.data.dropped} 個項目已不存在，已略過。</p>
            ) : null}
          </div>
        ) : null}
        {isNew && source.data ? (
          <p role="status" className="text-sm text-text-muted">
            複製自「
            <Link to={`/recipes/${source.data.id}`} className="text-brand hover:underline">
              {source.data.display_name}
            </Link>
            」。名稱、來源、狀態和圖片沒有複製。
          </p>
        ) : null}
      </header>

      {!isNew && existing.isPending ? <Loading /> : null}
      {!isNew && existing.error ? <ErrorNote error={existing.error} /> : null}
      {starting?.isPending ? <Loading /> : null}
      {starting?.error ? (
        <div className="space-y-2">
          <ErrorNote error={starting.error}>
            {templateId !== null ? '讀不到這個範本：' : '讀不到要複製的食譜：'}
            {starting.error.message}
          </ErrorNote>
          <LinkButton to={chooseAgain} size="sm">
            重新選擇
          </LinkButton>
        </div>
      ) : null}

      {ready ? (
        <>
          <Section title="料理">
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="space-y-1">
                <span className="text-sm font-medium text-text-muted">料理</span>
                {form.dish ? (
                  <Picked
                    label={form.dish.label}
                    tag={form.dish.type === 'new-dish' ? `新${kindWord(form.dish.kind)}` : kindWord(form.dish.kind)}
                    onClear={() => {
                      setField('dish', null)
                      setDishTyped('')
                    }}
                  />
                ) : (
                  <Typeahead
                    sources={['dish']}
                    allowNewDish
                    newDishHint="（存檔時建立料理）"
                    label="料理"
                    placeholder="這是哪道料理的食譜…"
                    onSelect={(option) => setField('dish', dishFromOption(option))}
                    onQueryChange={setDishTyped}
                  />
                )}
                {form.dish?.type === 'new-dish' && dishKinds.length ? (
                  <Toggle
                    label="新料理的種類"
                    options={dishKinds}
                    value={form.dish.kind}
                    onChange={(kind) => setField('dish', { ...form.dish, kind })}
                  />
                ) : null}
              </div>
              <Field label="名稱" hint="同一道料理有好幾份食譜時用來分辨，例如作者或做法。留空就用料理的名字。">
                <Input value={form.name} onChange={set('name')} />
              </Field>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="狀態">
                <Select value={statusId} onChange={set('status_id')}>
                  {vocabularyOptions(statuses.data)}
                </Select>
              </Field>
              <Field label="份量">
                <Input value={form.servings} onChange={set('servings')} placeholder="例如 2 人份" />
              </Field>
              <Field label="時間">
                <Input value={form.time} onChange={set('time')} placeholder="例如 30 分鐘" />
              </Field>
            </div>
          </Section>

          <Section title="來源">
            <RowEditor
              rows={form.sources}
              onChange={(rows) => setField('sources', rows)}
              newRow={() => sourceRow()}
              addLabel="加一個來源"
              itemLabel="來源"
            >
              {(row, { update, index }) => (
                <div className="grid gap-2 sm:grid-cols-4">
                  <Select
                    aria-label="平台"
                    value={platformOf(row)}
                    onChange={(event) => update({ platform_id: event.target.value })}
                  >
                    {vocabularyOptions(platforms.data)}
                  </Select>
                  {row.author ? (
                    <Picked
                      label={row.author.label}
                      tag={row.author.type === 'new' ? '新作者' : null}
                      onClear={() => update({ author: null, pendingAuthor: '' })}
                    />
                  ) : (
                    <Typeahead
                      items={authors.data ?? []}
                      allowNew
                      newHint="（存檔時建立作者）"
                      label={`作者 ${index + 1}`}
                      placeholder="作者（可留空）"
                      onSelect={(option) => update({ author: authorFromOption(option) })}
                      onQueryChange={(text) => setSourcePending(row._key, text)}
                    />
                  )}
                  <Input
                    aria-label="來源標題"
                    placeholder="標題"
                    value={row.title}
                    onChange={(event) => update({ title: event.target.value })}
                    className="sm:col-span-2"
                  />
                  <Input
                    aria-label="來源網址"
                    type="url"
                    placeholder="https://（書可以留空）"
                    value={row.url}
                    onChange={(event) => update({ url: event.target.value })}
                    className="sm:col-span-4"
                  />
                </div>
              )}
            </RowEditor>
          </Section>

          <RecipeLinesSection value={form.lines} setValue={setter('lines')} excludeDishes={ownDish} />
          <RecipeStepsSection value={form.steps} setValue={setter('steps')} />
          <RecipeMethodsSection methodIds={form.method_ids} equipmentIds={form.equipment_ids} onChange={setField} />

          <Section title="說明">
            <Field label="保存">
              <TextArea rows={3} value={form.storage_notes} onChange={set('storage_notes')} />
            </Field>
            <Field label="筆記">
              <TextArea value={form.notes} onChange={set('notes')} />
            </Field>
          </Section>

          <Section title="圖片">
            <GalleryPicker value={form.gallery} onChange={(gallery) => setField('gallery', gallery)} />
          </Section>

          <FormActions
            saving={saving}
            error={error}
            onCancel={() =>
              navigate(isNew ? (presetId ? `/dishes/${presetId}` : '/recipes') : `/recipes/${id}`)
            }
            onDelete={isNew ? null : () => setDeleting(true)}
          />
        </>
      ) : null}

      {deleting ? (
        <DeleteDialog
          kind="recipe"
          id={id}
          name={existing.data?.display_name}
          onClose={() => setDeleting(false)}
        />
      ) : null}
    </form>
  )
}
