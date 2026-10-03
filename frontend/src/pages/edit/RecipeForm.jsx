// Frontend: add or edit a recipe, /edit/recipes/new and /edit/recipes/:id.
//
// In the order the page reads: names and how it is filed (kind, course,
// what else it serves as, status, servings, time, the recipe it is a version
// of); sources; ingredient lines; steps; labels, methods, equipment; the
// prose; aliases; the gallery.
//
// A line's ingredient or sub-recipe is picked with the Typeahead, which
// searches both libraries. When nothing matches, 「新增 'xxx'」 makes the
// line name an ingredient that does not exist yet: it is shown with 待補 until
// the save, which creates it as a stub in the same transaction (the server
// folds a name it already knows into that row rather than duplicating it).
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
// 材料 and 步驟 each sit in groups (components/forms/GroupedRowEditor.jsx):
// the ungrouped rows first, then a box per group, picked from 設定's
// 材料分組 / 步驟分組 or named for this recipe only. Rows are numbered through
// every group, as the recipe's page numbers its steps.
//
// POST takes the whole recipe and PATCH replaces each list wholesale, so the
// form always sends every list - lines with line_groups, steps with
// step_groups, the pairs the server replaces together. Saving goes to the
// recipe's page.
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import ChipPicker from '../../components/forms/ChipPicker'
import DeleteDialog from '../../components/forms/DeleteDialog'
import FormActions from '../../components/forms/FormActions'
import GalleryPicker from '../../components/forms/GalleryPicker'
import GroupedRowEditor from '../../components/forms/GroupedRowEditor'
import RowEditor from '../../components/forms/RowEditor'
import Typeahead, { Picked } from '../../components/forms/Typeahead'
import Dialog from '../../components/ui/Dialog'
import { Button, Field, Input, Section, Select, TextArea, Toggle } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { useOwnerSave } from '../../hooks/useOwnerSave'
import { galleryChanged, galleryFromImages } from '../../lib/gallery'
import {
  UNGROUPED,
  emptyGrouped,
  flatRows,
  groupsFromResponse,
  groupsPayload,
  rowsOf,
  setRows,
  updateRowByKey,
} from '../../lib/groupedRows'
import { emptyLine, isStub, lineFromResponse, linesPayload, targetFromOption } from '../../lib/recipeLines'
import { authorFromOption, sourceRow, sourcesPayload } from '../../lib/recipeSources'
import { blankToNull, keyed, splitAliases } from '../../lib/rowList'
import { NOTE, STEP, splitSteps, stepNumbers } from '../../lib/steps'

// A recipe save moves its own reads, the authors list, the ingredient
// library (a 新增 line makes a stub; used-in counts move), the category tree
// (the stub is filed in the fallback category, whose count moves), and the
// usage counts of every vocabulary and picture it names.
const INVALIDATE = [
  endpoints.recipes.list(),
  endpoints.authors.list(),
  endpoints.ingredients.list(),
  endpoints.categories.tree(),
  endpoints.labels.list(),
  endpoints.courses.list(),
  endpoints.statuses.list(),
  endpoints.platforms.list(),
  endpoints.methods.list(),
  endpoints.equipment.list(),
  endpoints.lineGroups.list(),
  endpoints.stepGroups.list(),
  endpoints.images.list(),
]

const EMPTY = {
  name_cn: '',
  name_en: '',
  name_alt: '',
  kind: 'dish',
  course_id: '',
  serves_as_ids: [],
  // '' until chosen: the first status is shown, and sent, in its place.
  status_id: '',
  servings: '',
  time: '',
  variant_of: null,
  sources: [],
  // { ungrouped, groups } each (lib/groupedRows.js).
  lines: emptyGrouped(),
  steps: emptyGrouped(),
  label_ids: [],
  method_ids: [],
  equipment_ids: [],
  description: '',
  storage_notes: '',
  notes: '',
  aliases: '',
  gallery: [],
}

const stepRow = (entry = {}) => keyed({ body: entry.body ?? '', kind: entry.kind ?? STEP })

// A step left blank is an "add" pressed once too often, not a step.
const stepsPayload = (rows) =>
  rows.filter((row) => blankToNull(row.body)).map((row) => ({ body: row.body.trim(), kind: row.kind }))

const ids = (refs) => (refs ?? []).map((ref) => ref.id)

function fromRecipe(row) {
  return {
    name_cn: row.name_cn ?? '',
    name_en: row.name_en ?? '',
    name_alt: row.name_alt ?? '',
    kind: row.kind ?? 'dish',
    course_id: row.course ? String(row.course.id) : '',
    serves_as_ids: ids(row.serves_as),
    status_id: row.status ? String(row.status.id) : '',
    servings: row.servings ?? '',
    time: row.time ?? '',
    variant_of: row.variant_of ? { id: row.variant_of.id, label: row.variant_of.display_name } : null,
    sources: (row.sources ?? []).map(sourceRow),
    lines: {
      ungrouped: (row.lines ?? []).map(lineFromResponse),
      groups: groupsFromResponse(row.line_groups, 'lines', lineFromResponse),
    },
    steps: {
      ungrouped: (row.steps ?? []).map(stepRow),
      groups: groupsFromResponse(row.step_groups, 'steps', stepRow),
    },
    label_ids: ids(row.labels),
    method_ids: ids(row.methods),
    equipment_ids: ids(row.equipment),
    description: row.description ?? '',
    storage_notes: row.storage_notes ?? '',
    notes: row.notes ?? '',
    aliases: (row.aliases ?? []).join('、'),
    gallery: galleryFromImages(row.images),
  }
}

export default function RecipeForm() {
  const { id } = useParams()
  const isNew = id === undefined
  const navigate = useNavigate()

  const existing = useApiQuery(endpoints.recipes.detail(id), null, { enabled: !isNew })
  const courses = useApiQuery(endpoints.courses.list())
  const statuses = useApiQuery(endpoints.statuses.list())
  const platforms = useApiQuery(endpoints.platforms.list())
  const methods = useApiQuery(endpoints.methods.list())
  const equipment = useApiQuery(endpoints.equipment.list())
  const labels = useApiQuery(endpoints.labels.list())
  const authors = useApiQuery(endpoints.authors.list())
  const lineGroups = useApiQuery(endpoints.lineGroups.list())
  const stepGroups = useApiQuery(endpoints.stepGroups.list())
  const fixed = useFixedVocabularies()
  const stepKinds = fixed.data?.step_kinds ?? []
  const { save, saving } = useOwnerSave({ group: endpoints.recipes, invalidate: INVALIDATE })

  const [form, setForm] = useState(EMPTY)
  const [loaded, setLoaded] = useState(null)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(false)
  const [pasting, setPasting] = useState(false)
  // Typed into the version-of box and not picked: refused on save, never
  // dropped (Typeahead's onQueryChange).
  const [variantTyped, setVariantTyped] = useState('')

  // Adjusting state to the loaded row during render, keyed on the id so a
  // background refetch never throws away what is being typed.
  if (!isNew && existing.data && loaded?.id !== existing.data.id) {
    setLoaded(existing.data)
    setForm(fromRecipe(existing.data))
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
  const firstId = (query) => (query.data?.length ? String(query.data[0].id) : '')
  const statusId = form.status_id || firstId(statuses)
  const platformOf = (row) => row.platform_id || firstId(platforms)

  function payload() {
    return {
      name_cn: blankToNull(form.name_cn),
      name_en: blankToNull(form.name_en),
      name_alt: blankToNull(form.name_alt),
      kind: form.kind,
      course_id: form.course_id ? Number(form.course_id) : null,
      // The UI does not offer the recipe's own course as a serves-as.
      serves_as_ids: form.serves_as_ids.filter((courseId) => String(courseId) !== form.course_id),
      // Left out when there is no status to choose: the server then gives
      // the first one, or says there is none.
      ...(statusId ? { status_id: Number(statusId) } : {}),
      servings: blankToNull(form.servings),
      time: blankToNull(form.time),
      variant_of_id: form.variant_of?.id ?? null,
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
      label_ids: form.label_ids,
      method_ids: form.method_ids,
      equipment_ids: form.equipment_ids,
      description: blankToNull(form.description),
      storage_notes: blankToNull(form.storage_notes),
      notes: blankToNull(form.notes),
      aliases: splitAliases(form.aliases),
    }
  }

  async function submit(event) {
    event.preventDefault()
    setError(null)
    if (!form.variant_of && variantTyped.trim()) {
      setError(
        new Error(`「是哪道食譜的另一版」打了「${variantTyped.trim()}」，但還沒從清單選：選一道，或把文字清掉。`),
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

  const fixedOptions = (list) =>
    (list ?? []).map((entry) => (
      <option key={entry.value} value={entry.value}>
        {entry.label}
      </option>
    ))
  const vocabularyOptions = (rows) =>
    (rows ?? []).map((row) => (
      <option key={row.id} value={row.id}>
        {row.display_name}
      </option>
    ))
  const otherCourses = (courses.data ?? []).filter((course) => String(course.id) !== form.course_id)

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
          <Section title="名稱與分類">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="中文名">
                <Input value={form.name_cn} onChange={set('name_cn')} />
              </Field>
              <Field label="英文名">
                <Input value={form.name_en} onChange={set('name_en')} />
              </Field>
              <Field label="其他名稱">
                <Input value={form.name_alt} onChange={set('name_alt')} />
              </Field>
              <Field label="種類" hint="基底：醬汁、高湯、麵團這類拿來做別道菜的">
                <Select value={form.kind} onChange={set('kind')}>
                  {fixedOptions(fixed.data?.recipe_kinds ?? [{ value: form.kind, label: form.kind }])}
                </Select>
              </Field>
              <Field label="類別">
                <Select value={form.course_id} onChange={set('course_id')}>
                  <option value="">—</option>
                  {(courses.data ?? []).map((course) => (
                    <option key={course.id} value={course.id}>
                      {course.display_name}
                    </option>
                  ))}
                </Select>
              </Field>
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
              <div className="space-y-1">
                <span className="text-sm font-medium text-text-muted">是哪道食譜的另一版</span>
                {form.variant_of ? (
                  <Picked
                    label={form.variant_of.label}
                    onClear={() => {
                      setField('variant_of', null)
                      setVariantTyped('')
                    }}
                    clearLabel="移除"
                  />
                ) : (
                  <Typeahead
                    sources={['recipe']}
                    label="是哪道食譜的另一版"
                    placeholder="不是就留空"
                    exclude={{ recipe: id ? [Number(id)] : [] }}
                    onSelect={(option) => setField('variant_of', { id: option.id, label: option.label })}
                    onQueryChange={setVariantTyped}
                  />
                )}
              </div>
            </div>
            <div className="space-y-1">
              <span className="text-sm font-medium text-text-muted">也可以當作</span>
              <ChipPicker
                label="也可以當作"
                options={otherCourses}
                value={form.serves_as_ids}
                onChange={(value) => setField('serves_as_ids', value)}
                empty="還沒有類別，可以在設定裡新增。"
              />
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
                        tag={line.target.type === 'recipe' ? '食譜' : null}
                        onClear={() => update({ target: null, pending: '' })}
                      />
                    ) : (
                      <Typeahead
                        allowNew
                        label={`材料 ${number}`}
                        placeholder="食材或食譜…"
                        exclude={{ recipe: id ? [Number(id)] : [] }}
                        onSelect={(option) => update({ target: targetFromOption(option) })}
                        onQueryChange={(text) => setLinePending(line._key, text)}
                      />
                    )}
                  </div>
                  <Input
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

          <Section title="標籤、做法、器材">
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
            <div className="space-y-1">
              <span className="text-sm font-medium text-text-muted">標籤</span>
              <ChipPicker
                label="標籤"
                options={labels.data}
                value={form.label_ids}
                onChange={(value) => setField('label_ids', value)}
                empty="還沒有標籤，可以在設定裡新增。"
              />
            </div>
          </Section>

          <Section title="說明">
            <Field label="簡介">
              <TextArea value={form.description} onChange={set('description')} />
            </Field>
            <Field label="保存">
              <TextArea rows={3} value={form.storage_notes} onChange={set('storage_notes')} />
            </Field>
            <Field label="筆記">
              <TextArea value={form.notes} onChange={set('notes')} />
            </Field>
            <Field label="別名" hint="用逗號或頓號分開。搜尋得到，但不顯示。">
              <Input value={form.aliases} onChange={set('aliases')} />
            </Field>
          </Section>

          <Section title="圖片">
            <GalleryPicker value={form.gallery} onChange={(gallery) => setField('gallery', gallery)} />
          </Section>

          <FormActions
            saving={saving}
            error={error}
            onCancel={() => navigate(isNew ? '/recipes' : `/recipes/${id}`)}
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
