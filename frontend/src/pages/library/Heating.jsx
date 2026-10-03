// Frontend: 加熱, /heating - how to heat or reheat a food.
//
// A standalone page shaped as TBD's (pages/library/Tbd.jsx): each note is a
// name - 冷凍吐司, 香腸, a boxed meal - and how to heat it, in the owner's
// words with their line breaks, kept in the owner's order. No filters, covers
// or detail pages: one list, read whole.
import { endpoints } from '../../api/endpoints'
import { LinkButton } from '../../components/ui/primitives'
import { Empty, ErrorNote, Loading } from '../../components/ui/states'
import { useApiQuery } from '../../hooks/useApi'

const TITLE = '加熱'

export default function Heating() {
  const query = useApiQuery(endpoints.heating.list())
  const notes = query.data ?? []
  const editButton = (
    <LinkButton to="/edit/heating" size="sm">
      編輯
    </LinkButton>
  )

  let body
  if (query.isPending) body = <Loading />
  else if (query.error) body = <ErrorNote error={query.error} />
  else if (notes.length === 0) body = <Empty action={editButton}>還沒有任何加熱筆記。</Empty>
  else
    body = (
      <ul aria-label={TITLE} className="divide-y divide-border border-y border-border">
        {notes.map((note) => (
          <li key={note.id} aria-label={note.name} className="space-y-1 py-3">
            <p className="font-medium text-text">{note.name}</p>
            {note.body ? (
              <p className="whitespace-pre-line text-sm text-text-muted">{note.body}</p>
            ) : null}
          </li>
        ))}
      </ul>
    )

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-3xl font-bold">{TITLE}</h1>
        {editButton}
      </div>
      {body}
    </div>
  )
}
