// Frontend: add or edit an author, /edit/authors/new and /edit/authors/:id.
//
// An author is two names (one is enough - the server says so when both are
// blank), links, a 備註 and pictures, and this is the one place all of it is
// edited: 設定's 作者 tab only adds, renames and deletes, and links each row
// here. The links are TBD's link editor
// (components/forms/RowEditor.jsx): a row each of 名稱 (YouTube, IG, 部落格 -
// optional) and 網址, dragged to reorder, ✕ to remove, ＋ to add.
// lib/authors.js turns the stored author into the draft and the draft into
// the body; the gallery is its own PUT (hooks/useOwnerSave.js). Saving goes
// to the author's page.
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import DeleteDialog from '../../components/forms/DeleteDialog'
import FormActions from '../../components/forms/FormActions'
import GalleryPicker from '../../components/forms/GalleryPicker'
import RowEditor from '../../components/forms/RowEditor'
import { Field, Input, Section, TextArea } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { useApiQuery } from '../../hooks/useApi'
import { useOwnerSave } from '../../hooks/useOwnerSave'
import { authorBody, authorDraft } from '../../lib/authors'
import { galleryChanged, galleryFromImages } from '../../lib/gallery'

// A renamed author is shown on every recipe its sources name.
const INVALIDATE = [endpoints.authors.list(), endpoints.recipes.list(), endpoints.images.list()]

const EMPTY = { name_cn: '', name_en: '', notes: '', links: [], gallery: [] }

function fromAuthor(row) {
  return {
    name_cn: row.name_cn ?? '',
    name_en: row.name_en ?? '',
    ...authorDraft(row),
    gallery: galleryFromImages(row.images),
  }
}

export default function AuthorForm() {
  const { id } = useParams()
  const isNew = id === undefined
  const navigate = useNavigate()

  const existing = useApiQuery(endpoints.authors.detail(id), null, { enabled: !isNew })
  const { save, saving } = useOwnerSave({ group: endpoints.authors, invalidate: INVALIDATE })

  const [form, setForm] = useState(EMPTY)
  const [loaded, setLoaded] = useState(null)
  const [error, setError] = useState(null)
  const [deleting, setDeleting] = useState(false)

  // Adjusted during render, keyed on the id, as the note form does.
  if (!isNew && existing.data && loaded?.id !== existing.data.id) {
    setLoaded(existing.data)
    setForm(fromAuthor(existing.data))
  }

  const set = (field) => (event) => setForm((previous) => ({ ...previous, [field]: event.target.value }))

  async function submit(event) {
    event.preventDefault()
    setError(null)
    try {
      const saved = await save({
        id,
        body: authorBody(form),
        gallery: form.gallery,
        galleryDirty: galleryChanged(galleryFromImages(loaded?.images), form.gallery),
      })
      navigate(`/authors/${saved.id}`)
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl font-bold">{isNew ? '新增作者' : '編輯作者'}</h1>
        {!isNew && existing.data ? (
          <p className="text-sm text-text-muted">{existing.data.display_name}</p>
        ) : null}
      </header>

      {!isNew && existing.isPending ? <Loading /> : null}
      {!isNew && existing.error ? <ErrorNote error={existing.error} /> : null}

      {isNew || existing.data ? (
        <>
          <Section title="名稱">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="中文名">
                <Input value={form.name_cn} onChange={set('name_cn')} />
              </Field>
              <Field label="英文名">
                <Input value={form.name_en} onChange={set('name_en')} />
              </Field>
            </div>
          </Section>

          <Section title="連結">
            <RowEditor
              rows={form.links}
              onChange={(links) => setForm((previous) => ({ ...previous, links }))}
              newRow={() => ({ label: '', url: '' })}
              addLabel="新增連結"
              itemLabel="連結"
            >
              {(row, { number, update }) => (
                <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
                  <Input
                    aria-label={`連結 ${number} 名稱`}
                    value={row.label}
                    onChange={(event) => update({ label: event.target.value })}
                    placeholder="名稱：YouTube、IG…（可留空）"
                  />
                  <Input
                    aria-label={`連結 ${number} 網址`}
                    value={row.url}
                    onChange={(event) => update({ url: event.target.value })}
                    placeholder="網址"
                    inputMode="url"
                  />
                </div>
              )}
            </RowEditor>
          </Section>

          <Section title="備註">
            <TextArea aria-label="備註" rows={5} value={form.notes} onChange={set('notes')} />
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
            onCancel={() => navigate(isNew ? '/authors' : `/authors/${id}`)}
            onDelete={isNew ? null : () => setDeleting(true)}
          />
        </>
      ) : null}

      {deleting ? (
        <DeleteDialog
          kind="author"
          id={id}
          name={existing.data?.display_name}
          onClose={() => setDeleting(false)}
        />
      ) : null}
    </form>
  )
}
