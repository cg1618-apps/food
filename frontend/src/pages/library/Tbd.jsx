// Frontend: TBD, /tbd - a standalone page of loose names and links.
//
// Nothing here relates to the rest of the app: an entry is an optional name
// and any number of links, kept in the owner's order, for something worth
// keeping before it is decided what it is. So there are no filters, covers
// or detail pages - one list, read whole. A link is shown by its label, or
// else by its host and path (lib/format.js linkText), and opens in a new tab.
import { endpoints } from '../../api/endpoints'
import { LinkButton } from '../../components/ui/primitives'
import { Empty, ErrorNote, Loading } from '../../components/ui/states'
import { useApiQuery } from '../../hooks/useApi'
import { linkText } from '../../lib/format'

const TITLE = 'TBD'

export default function Tbd() {
  const query = useApiQuery(endpoints.tbd.list())
  const entries = query.data ?? []
  const editButton = (
    <LinkButton to="/edit/tbd" size="sm">
      編輯
    </LinkButton>
  )

  let body
  if (query.isPending) body = <Loading />
  else if (query.error) body = <ErrorNote error={query.error} />
  else if (entries.length === 0) body = <Empty action={editButton}>還沒有任何東西。</Empty>
  else
    body = (
      <ul aria-label={TITLE} className="divide-y divide-border border-y border-border">
        {entries.map((entry) => (
          <li key={entry.id} aria-label={entry.name ?? '未命名'} className="space-y-1 py-3">
            {entry.name ? <p className="font-medium text-text">{entry.name}</p> : null}
            {entry.links.length ? (
              <ul className="space-y-0.5 text-sm">
                {entry.links.map((link) => (
                  <li key={link.id} className="truncate">
                    <a
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-brand hover:underline"
                    >
                      {link.label ?? linkText(link.url)}
                    </a>
                  </li>
                ))}
              </ul>
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
