// Frontend: /search?q=… - everything the universal search found.
//
// What Enter in the top bar's search box opens (components/layout/NavSearch.jsx):
// the same buckets as its dropdown, up to the API's cap per kind, each under
// its kind's heading. The term lives in the URL - hooks/useUrlFilters.js's
// search wiring, which the libraries' own boxes use - so a result page can
// be bookmarked and Back returns to it.
//
// Every row links to its page and carries an 編輯 link to its edit page.
// That is how an entry is edited quickly from anywhere: food has no media-
// style "modify" hubs, and finding the thing is the hub (docs/notes/decisions.md).
// 加熱 and TBD have no page per entry, so their rows open the list at the
// entry, and 編輯 opens the list's edit page.
import { Link } from 'react-router-dom'

import { endpoints } from '../api/endpoints'
import { CoverImage } from '../components/layout/CoverGrid'
import { SectionHeading } from '../components/layout/LibraryTable'
import { Input, LinkButton } from '../components/ui/primitives'
import { Empty, ErrorNote, Loading } from '../components/ui/states'
import { useApiQuery } from '../hooks/useApi'
import { useUrlFilters } from '../hooks/useUrlFilters'
import { groupResults, PAGE_LIMIT } from '../lib/search'

const SPEC = {}

function ResultRow({ type, row }) {
  return (
    <li className="flex items-center gap-3 py-2.5">
      {type.hasCover ? (
        <div className="size-11 shrink-0 overflow-hidden rounded-md border border-border">
          <CoverImage cover={row.cover} title={row.display_name} />
        </div>
      ) : null}
      <div className="min-w-0 flex-1">
        <Link
          to={type.itemTo(row.id)}
          className="block truncate font-display font-bold text-text hover:text-brand"
        >
          {row.display_name}
        </Link>
        {row.detail ? <div className="truncate text-xs text-text-faint">{row.detail}</div> : null}
      </div>
      <LinkButton
        to={type.editTo(row.id)}
        size="sm"
        kind="ghost"
        aria-label={`編輯 ${row.display_name}`}
        className="shrink-0"
      >
        編輯
      </LinkButton>
    </li>
  )
}

export default function Search() {
  const filters = useUrlFilters(SPEC)
  const term = filters.apiParams.q ?? ''
  const query = useApiQuery(
    endpoints.search.list(),
    { q: term, limit: PAGE_LIMIT },
    { enabled: term !== '' },
  )
  const groups = query.data ? groupResults(query.data.results) : []

  let body
  if (!term) body = <Empty>輸入名稱，搜尋料理、食譜、食材、筆記、作者、加熱與 TBD。</Empty>
  else if (query.isPending) body = <Loading />
  else if (query.error) body = <ErrorNote error={query.error} />
  else if (groups.length === 0) body = <Empty>找不到「{term}」。</Empty>
  else
    body = (
      <div className="space-y-6">
        {groups.map(({ type, rows }) => (
          <section key={type.key} aria-label={type.label}>
            <SectionHeading title={type.label} count={rows.length} />
            <ul className="divide-y divide-border">
              {rows.map((row) => (
                <ResultRow key={row.id} type={type} row={row} />
              ))}
            </ul>
          </section>
        ))}
      </div>
    )

  return (
    <div className="mx-auto max-w-2xl space-y-5">
      <h1 className="text-3xl font-bold">搜尋</h1>
      <Input
        type="search"
        aria-label="搜尋詞"
        enterKeyHint="search"
        autoComplete="off"
        placeholder="搜尋料理、食譜、食材…"
        value={filters.search}
        onChange={(event) => filters.setSearch(event.target.value)}
      />
      {body}
    </div>
  )
}
