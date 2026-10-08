// Frontend: add or edit a kitchen note, /edit/notes/new and /edit/notes/:id.
//
// A note is a bookmark with a body: one title (not name slots - nothing will
// look it up by an English name it does not have), a kind, a link, the text,
// labels and pictures. Saving goes to the note's page.
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import ChipPicker from '../../components/forms/ChipPicker'
import DeleteDialog from '../../components/forms/DeleteDialog'
import FormActions from '../../components/forms/FormActions'
import GalleryPicker from '../../components/forms/GalleryPicker'
import { Field, Input, Section, Select, TextArea } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { useApiQuery, useFixedVocabularies, useLabels } from '../../hooks/useApi'
import { useOwnerSave } from '../../hooks/useOwnerSave'
import { galleryChanged, galleryFromImages } from '../../lib/gallery'
import { blankToNull } from '../../lib/rowList'

const INVALIDATE = [endpoints.notes.list(), endpoints.labels.list(), endpoints.images.list()]

const EMPTY = { title: '', kind: 'reference', url: '', body: '', label_ids: [], gallery: [] }

function fromNote(row) {
  return {
    title: row.title ?? '',
    kind: row.kind ?? 'reference',
    url: row.url ?? '',
    body: row.body ?? '',
    label_ids: (row.labels ?? []).map((label) => label.id),
    gallery: galleryFromImages(row.images),
  }
}

export default function NoteForm() {
  const { id } = useParams()
  const isNew = id === undefined
  const navigate = useNavigate()

  const existing = useApiQuery(endpoints.notes.detail(id), null, { enabled: !isNew })
  const labels = useLabels('note')
  const fixed = useFixedVocabularies()
  const { save, saving } = useOwnerSave({ group: endpoints.notes, invalidate: INVALIDATE })

  const [form, setForm] = useState(EMPTY)
  const [loaded, setLoaded] = useState(null)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(false)

  // Adjusting state to the loaded row during render, as React documents for
  // this case: an effect would render the empty form once first. Keyed on the
  // id, so a background refetch never throws away what is being typed.
  if (!isNew && existing.data && loaded?.id !== existing.data.id) {
    setLoaded(existing.data)
    setForm(fromNote(existing.data))
  }

  const set = (field) => (event) => setForm((previous) => ({ ...previous, [field]: event.target.value }))

  async function submit(event) {
    event.preventDefault()
    setError(null)
    try {
      const saved = await save({
        id,
        body: {
          title: form.title,
          kind: form.kind,
          url: blankToNull(form.url),
          body: blankToNull(form.body),
          label_ids: form.label_ids,
        },
        gallery: form.gallery,
        galleryDirty: galleryChanged(galleryFromImages(loaded?.images), form.gallery),
      })
      navigate(`/notes/${saved.id}`)
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl font-bold">{isNew ? '新增筆記' : '編輯筆記'}</h1>
        {!isNew && existing.data ? <p className="text-sm text-text-muted">{existing.data.title}</p> : null}
      </header>

      {!isNew && existing.isPending ? <Loading /> : null}
      {!isNew && existing.error ? <ErrorNote error={existing.error} /> : null}

      {isNew || existing.data ? (
        <>
          <Section title="筆記">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="標題" className="sm:col-span-2">
                <Input value={form.title} onChange={set('title')} required />
              </Field>
              <Field label="種類">
                <Select value={form.kind} onChange={set('kind')}>
                  {(fixed.data?.kitchen_note_kinds ?? [{ value: form.kind, label: form.kind }]).map((kind) => (
                    <option key={kind.value} value={kind.value}>
                      {kind.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field label="連結" className="sm:col-span-3" hint="http 或 https 開頭">
                <Input type="url" value={form.url} onChange={set('url')} placeholder="https://" />
              </Field>
              <Field label="內容" className="sm:col-span-3">
                <TextArea rows={10} value={form.body} onChange={set('body')} />
              </Field>
            </div>
          </Section>

          <Section title="標籤">
            <ChipPicker
              label="標籤"
              options={labels.data}
              value={form.label_ids}
              onChange={(label_ids) => setForm((previous) => ({ ...previous, label_ids }))}
              empty="還沒有標籤，可以在設定裡新增。"
            />
          </Section>

          <Section title="圖片">
            <GalleryPicker
              value={form.gallery}
              onChange={(gallery) => setForm((previous) => ({ ...previous, gallery }))}
            />
          </Section>

          <FormActions
            saving={saving}
            error={error}
            onCancel={() => navigate(isNew ? '/notes' : `/notes/${id}`)}
            onDelete={isNew ? null : () => setDeleting(true)}
          />
        </>
      ) : null}

      {deleting ? (
        <DeleteDialog kind="note" id={id} name={existing.data?.title} onClose={() => setDeleting(false)} />
      ) : null}
    </form>
  )
}
