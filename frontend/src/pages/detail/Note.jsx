// Frontend: one kitchen note, /notes/:id.
//
// The smallest of the three detail pages: the title, its kind, the link it
// points at, the body, its labels and its pictures. A note is often only a
// link worth keeping - a compilation video, a technique page - so the link
// sits under the title where it is found first, shown by its host.
import { useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import { DetailActions, DetailStatus, LabelLinks, Prose } from '../../components/layout/Detail'
import Gallery from '../../components/ui/Gallery'
import { Chip, LinkButton } from '../../components/ui/primitives'
import { fixedLabel, useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { linkHost } from '../../lib/format'

export default function Note() {
  const { id } = useParams()
  const query = useApiQuery(endpoints.notes.detail(id))
  const fixed = useFixedVocabularies()
  const note = query.data

  if (!note) {
    return (
      <DetailStatus
        query={query}
        missing="找不到這則筆記。"
        back={<LinkButton to="/notes">回到筆記庫</LinkButton>}
      />
    )
  }

  return (
    <article className="mx-auto max-w-2xl space-y-6">
      <Gallery images={note.images} title={note.title} />

      <header className="space-y-2">
        <div className="flex flex-wrap items-baseline gap-2">
          <h1 className="text-3xl font-bold">{note.title}</h1>
          <Chip>{fixedLabel(fixed.data?.kitchen_note_kinds, note.kind)}</Chip>
        </div>
        {note.url ? (
          <p className="text-sm">
            <a
              href={note.url}
              target="_blank"
              rel="noreferrer"
              className="text-brand hover:underline"
            >
              {linkHost(note.url)} ↗
            </a>
          </p>
        ) : null}
        <LabelLinks labels={note.labels} to={(label) => `/notes?label=${label.id}`} />
      </header>

      <Prose>{note.body}</Prose>

      <DetailActions kind="note" id={note.id} name={note.title} editTo={`/edit/notes/${note.id}`} />
    </article>
  )
}
