// Frontend: add or edit a recipe, /edit/recipes/new and /edit/recipes/:id.
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
// dish chosen.
//
// A line's ingredient or dish is picked the same way, searching both
// libraries. When nothing matches, 「新增」 makes the line name an
// ingredient that does not exist yet - shown with 待補 until the save, which
// creates it as a stub in the same transaction - and 「新增料理」 a dish, a
// 醬料, made by the save the same way. The server folds a name it already
// knows into that row rather than duplicating it.
// A source's author is picked the same way from the authors list, which is
// small enough to fetch once and filter in the browser; 「新增」 there makes
// the author on save, and a name the server already knows is reused.
// Steps take a pasted block too: 「貼上多行」 splits it into one step per line,
// strips the numbering (lib/steps.js) and adds them to the group chosen in
// the dialog, or to the ungrouped steps, each an ordinary step.
//
// Each step row has a kind switch - 步驟 / 可省略 / 備註, the fixed
// `step_kinds` list - beside its number. Only an ordinary step shows a
// number, counted through every group as the recipe's page counts them; a
// 備註 row's box is ruled and tinted the way the page draws a note. The rows'
// accessible names (「步驟 3」) keep a running index, so every row has a
// unique one whatever its kind.
//
// Above 材料 sit the 常用 chips, one per 設定's 常用食材, in its order
// (components/forms/CommonIngredientChips.jsx). A tap appends a line naming
// that ingredient to the ungrouped lines and puts the cursor in its 份量, so
// the amount is typed next; a chip whose ingredient is already on a line is
// marked used and still adds. No chips, no row.
//
// 材料 and 步驟 each sit in groups (components/forms/GroupedRowEditor.jsx):
// the ungrouped rows first, then a box per group, picked from 設定's
// 材料分組 / 步驟分組 or named for this recipe only. Rows are numbered through
// every group, as the recipe's page numbers its steps.
//
// POST takes the whole recipe and PATCH replaces each list wholesale, so the
// form always sends every list - lines with line_groups, steps with
// step_groups, the pairs the server replaces together. Saving goes to the
// recipe's page.
import { useEffect, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import ChipPicker from '../../components/forms/ChipPicker'
import CommonIngredientChips from '../../components/forms/CommonIngredientChips'
import DeleteDialog from '../../components/forms/DeleteDialog'
import FormActions from '../../components/forms/FormActions'
import GalleryPicker from '../../components/forms/GalleryPicker'
import GroupedRowEditor from '../../components/forms/GroupedRowEditor'
import RowEditor from '../../components/forms/RowEditor'
import Typeahead, { Picked } from '../../components/forms/Typeahead'
import Dialog from '../../components/ui/Dialog'
import { Button, Field, Input, Section, Select, TextArea, Toggle } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { fixedLabel, useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { useOwnerSave } from '../../hooks/useOwnerSave'
import { galleryChanged, galleryFromImages } from '../../lib/gallery'
import {
  UNGROUPED,
  emptyGrouped,
  flatRows,
  groupedReducer,
  groupsFromResponse,
  groupsPayload,
  rowsOf,
  setRows,
  updateRowByKey,
} from '../../lib/groupedRows'
import {
  DISH,
  emptyLine,
  isStub,
  lineFromResponse,
  linesPayload,
  newNames,
  targetFromOption,
} from '../../lib/recipeLines'
import { authorFromOption, sourceRow, sourcesPayload } from '../../lib/recipeSources'
import { blankToNull, keyed } from '../../lib/rowList'
import { NOTE, STEP, splitSteps, stepNumbers } from '../../lib/steps'

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

const EMPTY = {
  // { type: 'dish', id, label, kind } or { type: 'new-dish', label, kind }.
  dish: null,
  name: '',
  // '' until chosen: the first status is shown, and sent, in its place.
  status_id: '',
  servings: '',
  time: '',
  sources: [],
  // { ungrouped, groups } each (lib/groupedRows.js).
  lines: emptyGrouped(),
  steps: emptyGrouped(),
  method_ids: [],
  equipment_ids: [],
  storage_notes: '',
  notes: '',
  gallery: [],
}

const dishPick = (dish) => ({ type: 'dish', id: dish.id, label: dish.display_name, kind: dish.kind })

// The recipe's own dish from a typeahead pick: a new one is a 料理 unless the
// form's switch says 醬料 - a line's new dish is the other way round.
const dishFromOption = (option) =>
  option.type === 'new-dish'
    ? { ...targetFromOption(option), kind: DISH }
    : { type: 'dish', id: option.id, label: option.label, kind: option.kind }

const stepRow = (entry = {}) => keyed({ body: entry.body ?? '', kind: entry.kind ?? STEP })

// A step left blank is an "add" pressed once too often, not a step.
const stepsPayload = (rows) =>
  rows.filter((row) => blankToNull(row.body)).map((row) => ({ body: row.body.trim(), kind: row.kind }))

const ids = (refs) => (refs ?? []).map((ref) => ref.id)

function fromRecipe(row) {
  return {
    dish: row.dish ? dishPick(row.dish) : null,
    name: row.name ?? '',
    status_id: row.status ? String(row.status.id) : '',
    servings: row.servings ?? '',
    time: row.time ?? '',
    sources: (row.sources ?? []).map(sourceRow),
    lines: {
      ungrouped: (row.lines ?? []).map(lineFromResponse),
      groups: groupsFromResponse(row.line_groups, 'lines', lineFromResponse),
    },
    steps: {
      ungrouped: (row.steps ?? []).map(stepRow),
      groups: groupsFromResponse(row.step_groups, 'steps', stepRow),
    },
    method_ids: ids(row.methods),
    equipment_ids: ids(row.equipment),
    storage_notes: row.storage_notes ?? '',
    notes: row.notes ?? '',
    gallery: galleryFromImages(row.images),
  }
}

export default function RecipeForm() {
  const { id } = useParams()
  const isNew = id === undefined
  const navigate = useNavigate()
  // ?dish=<id>: the dish page's 「＋ 新增食譜」. Only a new recipe reads it.
  const [searchParams] = useSearchParams()
  const presetId = isNew && /^\d+$/.test(searchParams.get('dish') ?? '') ? searchParams.get('dish') : null

  const existing = useApiQuery(endpoints.recipes.detail(id), null, { enabled: !isNew })
  const preset = useApiQuery(endpoints.dishes.detail(presetId), null, { enabled: presetId !== null })
  const statuses = useApiQuery(endpoints.statuses.list())
  const platforms = useApiQuery(endpoints.platforms.list())
  const methods = useApiQuery(endpoints.methods.list())
  const equipment = useApiQuery(endpoints.equipment.list())
  const authors = useApiQuery(endpoints.authors.list())
  const lineGroups = useApiQuery(endpoints.lineGroups.list())
  const stepGroups = useApiQuery(endpoints.stepGroups.list())
  const common = useApiQuery(endpoints.commonIngredients.list())
  const fixed = useFixedVocabularies()
  const stepKinds = fixed.data?.step_kinds ?? []
  const { save, saving } = useOwnerSave({ group: endpoints.recipes, invalidate: INVALIDATE })

  const [form, setForm] = useState(EMPTY)
  const [loaded, setLoaded] = useState(null)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [pasting, setPasting] = useState(false)
  // Typed into the dish box and not picked: refused on save, never dropped
  // (Typeahead's onQueryChange).
  const [dishTyped, setDishTyped] = useState('')
  const [presetApplied, setPresetApplied] = useState(false)
  // The line a 常用 chip just added, whose 份量 takes the focus once drawn.
  const [focusAmountOf, setFocusAmountOf] = useState(null)
  const amountInputs = useRef(new Map())
  useEffect(() => {
    if (focusAmountOf) amountInputs.current.get(focusAmountOf)?.focus()
  }, [focusAmountOf])

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

  const setField = (field, value) => setForm((previous) => ({ ...previous, [field]: value }))
  const set = (field) => (event) => setField(field, event.target.value)

  // The number each ordinary step row shows, by its key, counted through
  // every group as the page counts them; an optional step or a note has none.
  const stepRows = flatRows(form.steps)
  const stepNumber = new Map(
    stepNumbers(stepRows)
      .map((value, index) => [stepRows[index]._key, value])
      .filter(([, value]) => value !== null),
  )
  // A line's typed-but-unpicked text, by the row's key and from the latest
  // state: a pick calls onSelect and then reports '' in the same tick, and
  // RowEditor's update() would build the second change from the rows the
  // first had not yet replaced.
  const setLinePending = (key, pending) =>
    setForm((previous) => ({ ...previous, lines: updateRowByKey(previous.lines, key, { pending }) }))
  // The same for a source's author box.
  const setSourcePending = (key, pendingAuthor) =>
    setForm((previous) => ({
      ...previous,
      sources: previous.sources.map((row) => (row._key === key ? { ...row, pendingAuthor } : row)),
    }))
  // A 常用 chip: a new ungrouped line naming that ingredient.
  function addCommonLine(ingredient) {
    const row = {
      ...emptyLine(),
      target: {
        type: 'ingredient',
        id: ingredient.id,
        label: ingredient.display_name,
        needsDetail: ingredient.needs_detail,
      },
    }
    setForm((previous) => ({
      ...previous,
      lines: groupedReducer(previous.lines, { type: 'rows', container: UNGROUPED, action: { type: 'add', row } }),
    }))
    setFocusAmountOf(row._key)
  }
  const usedIngredients = new Set(
    flatRows(form.lines)
      .filter((line) => line.target?.type === 'ingredient')
      .map((line) => line.target.id),
  )
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
      servings: blankToNull(form.servings),
      time: blankToNull(form.time),
      sources: sourcesPayload(form.sources, platformOf),
      lines: linesPayload(form.lines.ungrouped),
      line_groups: groupsPayload(form.lines, {
        idField: 'line_group_id',
        inner: 'lines',
        what: '材料分組',
        rowsPayload: linesPayload,
      }),
      steps: stepsPayload(form.steps.ungrouped),
      step_groups: groupsPayload(form.steps, {
        idField: 'step_group_id',
        inner: 'steps',
        what: '步驟分組',
        rowsPayload: stepsPayload,
      }),
      method_ids: form.method_ids,
      equipment_ids: form.equipment_ids,
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

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl font-bold">{isNew ? '新增食譜' : '編輯食譜'}</h1>
        {!isNew && existing.data ? (
          <p className="text-sm text-text-muted">{existing.data.display_name}</p>
        ) : null}
      </header>

      {!isNew && existing.isPending ? <Loading /> : null}
      {!isNew && existing.error ? <ErrorNote error={existing.error} /> : null}

      {isNew || existing.data ? (
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

          <Section title="材料">
            <CommonIngredientChips
              ingredients={(common.data ?? []).map((row) => row.ingredient)}
              usedIds={usedIngredients}
              onAdd={addCommonLine}
            />
            <GroupedRowEditor
              value={form.lines}
              onChange={(value) => setField('lines', value)}
              values={lineGroups.data}
              newRow={() => emptyLine()}
              addLabel="加一行材料"
              itemLabel="材料"
              groupLabel="材料分組"
            >
              {(line, { update, number }) => (
                <div className="grid gap-2 sm:grid-cols-6">
                  <div className="sm:col-span-3">
                    {line.target ? (
                      <Picked
                        label={line.target.label}
                        stub={isStub(line.target)}
                        tag={
                          line.target.type === 'dish'
                            ? kindWord(line.target.kind)
                            : line.target.type === 'new-dish'
                              ? `新${kindWord(line.target.kind)}`
                              : null
                        }
                        onClear={() => update({ target: null, pending: '' })}
                      />
                    ) : (
                      <Typeahead
                        allowNew
                        allowNewDish
                        label={`材料 ${number}`}
                        placeholder="食材或料理（醬料）…"
                        exclude={{ dish: ownDish }}
                        onSelect={(option) => update({ target: targetFromOption(option) })}
                        onQueryChange={(text) => setLinePending(line._key, text)}
                      />
                    )}
                  </div>
                  <Input
                    ref={(element) => {
                      if (element) amountInputs.current.set(line._key, element)
                      else amountInputs.current.delete(line._key)
                    }}
                    aria-label="份量"
                    placeholder="份量"
                    value={line.amount}
                    onChange={(event) => update({ amount: event.target.value })}
                    className="sm:col-span-1"
                  />
                  <Input
                    aria-label="材料備註"
                    placeholder="備註，例如 切絲"
                    value={line.note}
                    onChange={(event) => update({ note: event.target.value })}
                    className="sm:col-span-2"
                  />
                  <label className="flex items-center gap-1.5 text-sm">
                    <input
                      type="checkbox"
                      checked={line.is_optional}
                      onChange={(event) => update({ is_optional: event.target.checked })}
                    />
                    可省略
                  </label>
                </div>
              )}
            </GroupedRowEditor>
          </Section>

          <Section title="步驟">
            <GroupedRowEditor
              value={form.steps}
              onChange={(value) => setField('steps', value)}
              values={stepGroups.data}
              newRow={() => stepRow()}
              addLabel="加一個步驟"
              itemLabel="步驟"
              groupLabel="步驟分組"
              actions={
                <Button size="sm" onClick={() => setPasting(true)}>
                  貼上多行
                </Button>
              }
            >
              {(row, { update, number }) => {
                const note = row.kind === NOTE
                return (
                  <div className="flex gap-2">
                    <span className="w-6 shrink-0 pt-1 text-right font-display font-bold text-text-faint">
                      {stepNumber.has(row._key) ? <span data-testid="step-number">{stepNumber.get(row._key)}</span> : null}
                    </span>
                    <div className="min-w-0 flex-1 space-y-1.5">
                      {stepKinds.length ? (
                        <Toggle
                          label={`步驟 ${number} 的種類`}
                          options={stepKinds}
                          value={row.kind}
                          onChange={(kind) => update({ kind })}
                        />
                      ) : null}
                      <div className={note ? 'rounded-md border-l-4 border-border-strong bg-surface-2 p-1.5' : undefined}>
                        <TextArea
                          aria-label={`步驟 ${number}`}
                          rows={2}
                          placeholder={note ? '備註：火候、替換、提醒' : undefined}
                          value={row.body}
                          onChange={(event) => update({ body: event.target.value })}
                        />
                      </div>
                    </div>
                  </div>
                )
              }}
            </GroupedRowEditor>
          </Section>

          <Section title="做法、器材">
            <div className="space-y-1">
              <span className="text-sm font-medium text-text-muted">做法</span>
              <ChipPicker
                label="做法"
                options={methods.data}
                value={form.method_ids}
                onChange={(value) => setField('method_ids', value)}
                empty="還沒有做法，可以在設定裡新增。"
              />
            </div>
            <div className="space-y-1">
              <span className="text-sm font-medium text-text-muted">器材</span>
              <ChipPicker
                label="器材"
                options={equipment.data}
                value={form.equipment_ids}
                onChange={(value) => setField('equipment_ids', value)}
                empty="還沒有器材，可以在設定裡新增。"
              />
            </div>
          </Section>

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

      {pasting ? (
        <PasteSteps
          groups={form.steps.groups}
          onClose={() => setPasting(false)}
          onAdd={(bodies, container) => {
            const rows = [...rowsOf(form.steps, container), ...bodies.map((body) => stepRow({ body }))]
            setField('steps', setRows(form.steps, container, rows))
            setPasting(false)
          }}
        />
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

// 「貼上多行」: one step per line, numbering stripped, previewed by count
// before anything is added - at the end of the chosen group, 不分組 unless
// another is picked.
function PasteSteps({ groups, onAdd, onClose }) {
  const [text, setText] = useState('')
  const [container, setContainer] = useState(UNGROUPED)
  const bodies = splitSteps(text)
  return (
    <Dialog
      title="貼上多行步驟"
      size="md"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button kind="primary" disabled={!bodies.length} onClick={() => onAdd(bodies, container)}>
            加入 {bodies.length} 個步驟
          </Button>
        </>
      }
    >
      <Field label="一行一個步驟" hint="開頭的編號（1.、1)、①、一、、第一步）會自動拿掉。">
        <TextArea rows={10} value={text} onChange={(event) => setText(event.target.value)} autoFocus />
      </Field>
      <Field label="加到">
        <Select value={container} onChange={(event) => setContainer(event.target.value)}>
          <option value={UNGROUPED}>不分組</option>
          {groups.map((group, index) => (
            <option key={group._key} value={group._key}>
              {group.name.trim() || `第 ${index + 1} 組`}
            </option>
          ))}
        </Select>
      </Field>
    </Dialog>
  )
}
