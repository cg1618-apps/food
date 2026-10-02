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
// Steps take a pasted block too: 「貼上多行」 splits it into one step per line
// and strips the numbering (lib/steps.js).
//
// POST takes the whole recipe and PATCH replaces each list wholesale, so the
// form always sends every list. Saving goes to the recipe's page.
import { useId, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import ChipPicker from '../../components/forms/ChipPicker'
import DeleteDialog from '../../components/forms/DeleteDialog'
import FormActions from '../../components/forms/FormActions'
import GalleryPicker from '../../components/forms/GalleryPicker'
import RowEditor from '../../components/forms/RowEditor'
import Typeahead, { Picked } from '../../components/forms/Typeahead'
import Dialog from '../../components/ui/Dialog'
import { Button, Field, Input, Section, Select, TextArea } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { useOwnerSave } from '../../hooks/useOwnerSave'
import { galleryChanged, galleryFromImages } from '../../lib/gallery'
import { emptyLine, isStub, lineFromResponse, linesPayload, sectionsOf, targetFromOption } from '../../lib/recipeLines'
import { blankToNull, keyed, splitAliases } from '../../lib/rowList'
import { splitSteps } from '../../lib/steps'

// A recipe save moves its own reads, the creators list, the ingredient
// library (a 新增 line makes a stub; used-in counts move), the category tree
// (the stub is filed in the fallback category, whose count moves), and the
// usage counts of every vocabulary and picture it names.
const INVALIDATE = [
  endpoints.recipes.list(),
  endpoints.recipes.creators(),
  endpoints.ingredients.list(),
  endpoints.categories.tree(),
  endpoints.labels.list(),
  endpoints.courses.list(),
  endpoints.methods.list(),
  endpoints.equipment.list(),
  endpoints.images.list(),
]

const EMPTY = {
  name_cn: '',
  name_en: '',
  name_alt: '',
  kind: 'dish',
  course_id: '',
  serves_as_ids: [],
  status: 'want_to_try',
  servings: '',
  time: '',
  variant_of: null,
  sources: [],
  lines: [],
  steps: [],
  label_ids: [],
  method_ids: [],
  equipment_ids: [],
  description: '',
  storage_notes: '',
  notes: '',
  aliases: '',
  gallery: [],
}

const sourceRow = (entry = {}) =>
  keyed({
    platform: entry.platform ?? 'youtube',
    creator: entry.creator ?? '',
    url: entry.url ?? '',
    title: entry.title ?? '',
  })

const stepRow = (entry = {}) => keyed({ section: entry.section ?? '', body: entry.body ?? '' })

const ids = (refs) => (refs ?? []).map((ref) => ref.id)

// A source row with nothing typed - the platform always has a value - is an
// "add" pressed once too often, as a blank line or step is.
const isBlankSource = (row) => !blankToNull(row.creator) && !blankToNull(row.url) && !blankToNull(row.title)

function fromRecipe(row) {
  return {
    name_cn: row.name_cn ?? '',
    name_en: row.name_en ?? '',
    name_alt: row.name_alt ?? '',
    kind: row.kind ?? 'dish',
    course_id: row.course ? String(row.course.id) : '',
    serves_as_ids: ids(row.serves_as),
    status: row.status ?? 'want_to_try',
    servings: row.servings ?? '',
    time: row.time ?? '',
    variant_of: row.variant_of ? { id: row.variant_of.id, label: row.variant_of.display_name } : null,
    sources: (row.sources ?? []).map(sourceRow),
    lines: (row.lines ?? []).map(lineFromResponse),
    steps: (row.steps ?? []).map(stepRow),
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
  const sectionListId = useId()
  const creatorListId = useId()

  const existing = useApiQuery(endpoints.recipes.detail(id), null, { enabled: !isNew })
  const courses = useApiQuery(endpoints.courses.list())
  const methods = useApiQuery(endpoints.methods.list())
  const equipment = useApiQuery(endpoints.equipment.list())
  const labels = useApiQuery(endpoints.labels.list())
  const creators = useApiQuery(endpoints.recipes.creators())
  const fixed = useFixedVocabularies()
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
  // A line's typed-but-unpicked text, by the row's key and from the latest
  // state: a pick calls onSelect and then reports '' in the same tick, and
  // RowEditor's update() would build the second change from the rows the
  // first had not yet replaced.
  const setLinePending = (key, pending) =>
    setForm((previous) => ({
      ...previous,
      lines: previous.lines.map((line) => (line._key === key ? { ...line, pending } : line)),
    }))
  const sections = sectionsOf(form.lines, form.steps)

  function payload() {
    return {
      name_cn: blankToNull(form.name_cn),
      name_en: blankToNull(form.name_en),
      name_alt: blankToNull(form.name_alt),
      kind: form.kind,
      course_id: form.course_id ? Number(form.course_id) : null,
      // The UI does not offer the recipe's own course as a serves-as.
      serves_as_ids: form.serves_as_ids.filter((courseId) => String(courseId) !== form.course_id),
      status: form.status,
      servings: blankToNull(form.servings),
      time: blankToNull(form.time),
      variant_of_id: form.variant_of?.id ?? null,
      sources: form.sources.filter((row) => !isBlankSource(row)).map((row) => ({
        platform: row.platform,
        creator: blankToNull(row.creator),
        url: blankToNull(row.url),
        title: blankToNull(row.title),
      })),
      lines: linesPayload(form.lines),
      // A step left blank is an "add" pressed once too often, not a step.
      steps: form.steps
        .filter((row) => blankToNull(row.body))
        .map((row) => ({ section: blankToNull(row.section), body: row.body.trim() })),
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

      {/* Shared suggestions: a section typed once is offered on every line
          and step, and a creator typed on any recipe is offered here. */}
      <datalist id={sectionListId}>
        {sections.map((section) => (
          <option key={section} value={section} />
        ))}
      </datalist>
      <datalist id={creatorListId}>
        {(creators.data ?? []).map((creator) => (
          <option key={creator} value={creator} />
        ))}
      </datalist>

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
                <Select value={form.status} onChange={set('status')}>
                  {fixedOptions(fixed.data?.recipe_statuses ?? [{ value: form.status, label: form.status }])}
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
              {(row, { update }) => (
                <div className="grid gap-2 sm:grid-cols-4">
                  <Select
                    aria-label="平台"
                    value={row.platform}
                    onChange={(event) => update({ platform: event.target.value })}
                  >
                    {fixedOptions(fixed.data?.source_platforms ?? [{ value: row.platform, label: row.platform }])}
                  </Select>
                  <Input
                    aria-label="作者"
                    placeholder="作者"
                    list={creatorListId}
                    value={row.creator}
                    onChange={(event) => update({ creator: event.target.value })}
                  />
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
            <RowEditor
              rows={form.lines}
              onChange={(rows) => setField('lines', rows)}
              newRow={() => emptyLine(form.lines.at(-1)?.section ?? '')}
              addLabel="加一行材料"
              itemLabel="材料"
            >
              {(line, { update, index }) => (
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
                        label={`材料 ${index + 1}`}
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
                    aria-label="分段"
                    placeholder="分段，例如 醬汁"
                    list={sectionListId}
                    value={line.section}
                    onChange={(event) => update({ section: event.target.value })}
                    className="sm:col-span-2"
                  />
                  <Input
                    aria-label="材料備註"
                    placeholder="備註，例如 切絲"
                    value={line.note}
                    onChange={(event) => update({ note: event.target.value })}
                    className="sm:col-span-5"
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
            </RowEditor>
          </Section>

          <Section title="步驟">
            <RowEditor
              rows={form.steps}
              onChange={(rows) => setField('steps', rows)}
              newRow={() => stepRow({ section: form.steps.at(-1)?.section ?? '' })}
              addLabel="加一個步驟"
              itemLabel="步驟"
              actions={
                <Button size="sm" onClick={() => setPasting(true)}>
                  貼上多行
                </Button>
              }
            >
              {(row, { update, index }) => (
                <div className="flex gap-2">
                  <span className="w-6 shrink-0 pt-1.5 text-right font-display font-bold text-text-faint">
                    {index + 1}
                  </span>
                  <div className="grid min-w-0 flex-1 gap-2">
                    <TextArea
                      aria-label={`步驟 ${index + 1}`}
                      rows={2}
                      value={row.body}
                      onChange={(event) => update({ body: event.target.value })}
                    />
                    <Input
                      aria-label="步驟分段"
                      placeholder="分段（可留空）"
                      list={sectionListId}
                      value={row.section}
                      onChange={(event) => update({ section: event.target.value })}
                      className="sm:max-w-xs"
                    />
                  </div>
                </div>
              )}
            </RowEditor>
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
          onClose={() => setPasting(false)}
          onAdd={(bodies) => {
            const section = form.steps.at(-1)?.section ?? ''
            setField('steps', [...form.steps, ...bodies.map((body) => stepRow({ section, body }))])
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
// before anything is added.
function PasteSteps({ onAdd, onClose }) {
  const [text, setText] = useState('')
  const bodies = splitSteps(text)
  return (
    <Dialog
      title="貼上多行步驟"
      size="md"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button kind="primary" disabled={!bodies.length} onClick={() => onAdd(bodies)}>
            加入 {bodies.length} 個步驟
          </Button>
        </>
      }
    >
      <Field label="一行一個步驟" hint="開頭的編號（1.、1)、①、一、、第一步）會自動拿掉。">
        <TextArea rows={10} value={text} onChange={(event) => setText(event.target.value)} autoFocus />
      </Field>
    </Dialog>
  )
}
