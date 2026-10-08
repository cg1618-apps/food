// Frontend: add or edit a dish, /edit/dishes/new and /edit/dishes/:id.
//
// What is true of the dish whoever cooks it: its names and aliases, its kind
// (料理 / 醬料), course, region, what else it serves as, its labels, a
// description and its gallery. The recipes are each their own form; a dish's
// page adds one with the dish already chosen.
//
// POST takes the whole dish and PATCH replaces each list wholesale, so the
// form always sends every field. Saving goes to the dish's page.
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import ChipPicker from '../../components/forms/ChipPicker'
import DeleteDialog from '../../components/forms/DeleteDialog'
import FormActions from '../../components/forms/FormActions'
import GalleryPicker from '../../components/forms/GalleryPicker'
import { Field, Input, Section, Select, TextArea, Toggle } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { useApiQuery, useFixedVocabularies, useLabels } from '../../hooks/useApi'
import { useOwnerSave } from '../../hooks/useOwnerSave'
import { galleryChanged, galleryFromImages } from '../../lib/gallery'
import { DISH } from '../../lib/recipeLines'
import { blankToNull, splitAliases } from '../../lib/rowList'

// A dish save moves its own reads, every recipe of it (their display names,
// the dish section of their pages) and the recipe library's dish filter, and
// the usage counts of the vocabularies and pictures it names.
const INVALIDATE = [
  endpoints.dishes.list(),
  endpoints.recipes.list(),
  endpoints.labels.list(),
  endpoints.courses.list(),
  endpoints.regions.list(),
  endpoints.images.list(),
]

const EMPTY = {
  name_cn: '',
  name_en: '',
  name_alt: '',
  kind: DISH,
  course_id: '',
  region_id: '',
  serves_as_ids: [],
  label_ids: [],
  description: '',
  aliases: '',
  gallery: [],
}

const ids = (refs) => (refs ?? []).map((ref) => ref.id)

function fromDish(row) {
  return {
    name_cn: row.name_cn ?? '',
    name_en: row.name_en ?? '',
    name_alt: row.name_alt ?? '',
    kind: row.kind ?? DISH,
    course_id: row.course ? String(row.course.id) : '',
    region_id: row.region ? String(row.region.id) : '',
    serves_as_ids: ids(row.serves_as),
    label_ids: ids(row.labels),
    description: row.description ?? '',
    aliases: (row.aliases ?? []).join('、'),
    gallery: galleryFromImages(row.images),
  }
}

/** The form -> the POST / PATCH body. */
function dishPayload(form) {
  return {
    name_cn: blankToNull(form.name_cn),
    name_en: blankToNull(form.name_en),
    name_alt: blankToNull(form.name_alt),
    kind: form.kind,
    course_id: form.course_id ? Number(form.course_id) : null,
    region_id: form.region_id ? Number(form.region_id) : null,
    // The UI does not offer the dish's own course as a serves-as.
    serves_as_ids: form.serves_as_ids.filter((courseId) => String(courseId) !== form.course_id),
    label_ids: form.label_ids,
    description: blankToNull(form.description),
    aliases: splitAliases(form.aliases),
  }
}

export default function DishForm() {
  const { id } = useParams()
  const isNew = id === undefined
  const navigate = useNavigate()

  const existing = useApiQuery(endpoints.dishes.detail(id), null, { enabled: !isNew })
  const courses = useApiQuery(endpoints.courses.list())
  const regions = useApiQuery(endpoints.regions.list())
  const labels = useLabels('dish')
  const fixed = useFixedVocabularies()
  const { save, saving } = useOwnerSave({ group: endpoints.dishes, invalidate: INVALIDATE })

  const [form, setForm] = useState(EMPTY)
  const [loaded, setLoaded] = useState(null)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(false)

  // Adjusting state to the loaded row during render, keyed on the id so a
  // background refetch never throws away what is being typed.
  if (!isNew && existing.data && loaded?.id !== existing.data.id) {
    setLoaded(existing.data)
    setForm(fromDish(existing.data))
  }

  const setField = (field, value) => setForm((previous) => ({ ...previous, [field]: value }))
  const set = (field) => (event) => setField(field, event.target.value)

  async function submit(event) {
    event.preventDefault()
    setError(null)
    try {
      const saved = await save({
        id,
        body: dishPayload(form),
        gallery: form.gallery,
        galleryDirty: galleryChanged(galleryFromImages(loaded?.images), form.gallery),
      })
      navigate(`/dishes/${saved.id}`)
    } catch (caught) {
      setError(caught)
    }
  }

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
        <h1 className="font-display text-2xl font-bold">{isNew ? '新增料理' : '編輯料理'}</h1>
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
            </div>
            <Toggle
              label="種類"
              options={fixed.data?.dish_kinds ?? []}
              value={form.kind}
              onChange={(kind) => setField('kind', kind)}
            />
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="類別">
                <Select value={form.course_id} onChange={set('course_id')}>
                  <option value="">—</option>
                  {vocabularyOptions(courses.data)}
                </Select>
              </Field>
              <Field label="地區">
                <Select value={form.region_id} onChange={set('region_id')}>
                  <option value="">—</option>
                  {vocabularyOptions(regions.data)}
                </Select>
              </Field>
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
            onCancel={() => navigate(isNew ? '/dishes' : `/dishes/${id}`)}
            onDelete={isNew ? null : () => setDeleting(true)}
          />
        </>
      ) : null}

      {deleting ? (
        <DeleteDialog kind="dish" id={id} name={existing.data?.display_name} onClose={() => setDeleting(false)} />
      ) : null}
    </form>
  )
}
