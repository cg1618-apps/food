// Frontend: the scaffold every library page shares - recipes, ingredients,
// kitchen notes.
//
// media's LibraryLayout is the reference for the shape (title bar, search,
// filters, a grid/table toggle, a result count, then the list). Three
// differences, each the spec's and each recorded in docs/notes/decisions.md:
//
//   - the filters and the search term live in the URL (hooks/useUrlFilters),
//     not in component state, so a filtered view is a link;
//   - the filters sit in a sidebar on a desktop and in a drawer on a phone,
//     opened by a 篩選 button carrying the active-filter count, rather than
//     an inline panel the list is pushed down by;
//   - the 封面 / 清單 choice is remembered per library (hooks/useLibraryView).
//
// The page supplies its data and its words; this owns the arrangement and the
// three states. Two empties are different directions and say so: an empty
// LIBRARY offers the add button, an empty RESULT offers clearing the filters.
//
// Props:
//   title         - the page heading, e.g. 食譜
//   library       - the key the view choice is remembered under
//   add           - { to, label } for the add button
//   filters       - the useUrlFilters(spec) result
//   sidebar       - the filter controls (components/layout/FilterPanel)
//   query         - the list's useApiQuery result
//   card(item)    - { cover, title, subtitle?, meta?, badges?, listBadges? }
//   columns       - the table's columns after the name (LibraryTable)
//   itemTo(item)  - the item's detail path
//   searchPlaceholder, emptyText, noMatchText
import { useState } from 'react'

import { useLibraryView } from '../../hooks/useLibraryView'
import Dialog from '../ui/Dialog'
import { Button, Input, LinkButton, Toggle } from '../ui/primitives'
import { Empty, ErrorNote, Loading } from '../ui/states'
import CoverGrid from './CoverGrid'
import LibraryTable from './LibraryTable'

const VIEW_OPTIONS = [
  { value: 'cover', label: '封面' },
  { value: 'list', label: '清單' },
]

function FilterCount({ count }) {
  if (!count) return null
  return (
    <span className="rounded-full bg-brand px-1.5 text-xs leading-5 tabular-nums text-on-brand">
      {count}
    </span>
  )
}

export default function LibraryLayout({
  title,
  library,
  add,
  filters,
  sidebar,
  query,
  card,
  columns,
  itemTo,
  searchPlaceholder = '搜尋…',
  emptyText = '這裡還沒有東西。',
  noMatchText = '沒有符合條件的項目。',
}) {
  const [view, setView] = useLibraryView(library)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const items = query.data ?? []

  const addButton = add ? (
    <LinkButton kind="primary" to={add.to}>
      {add.label}
    </LinkButton>
  ) : null

  const clearButton = <Button onClick={filters.clearAll}>清除搜尋與篩選</Button>

  let body
  if (query.isPending) body = <Loading />
  else if (query.error) body = <ErrorNote error={query.error} />
  else if (items.length === 0 && filters.isFiltered) body = <Empty action={clearButton}>{noMatchText}</Empty>
  else if (items.length === 0) body = <Empty action={addButton}>{emptyText}</Empty>
  else if (view === 'list')
    body = <LibraryTable items={items} itemTo={itemTo} card={card} columns={columns} />
  else body = <CoverGrid items={items} itemTo={itemTo} card={card} />

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h1 className="text-3xl font-bold">{title}</h1>
        {addButton}
      </div>

      <div className="lg:grid lg:grid-cols-[13rem_minmax(0,1fr)] lg:gap-8">
        <aside aria-label="篩選" className="hidden space-y-5 lg:block">
          {sidebar}
          {filters.activeCount ? (
            <Button size="sm" kind="ghost" onClick={filters.clear}>
              清除篩選
            </Button>
          ) : null}
        </aside>

        <div className="min-w-0 space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Input
              type="search"
              aria-label="搜尋"
              value={filters.search}
              onChange={(event) => filters.setSearch(event.target.value)}
              placeholder={searchPlaceholder}
              className="min-w-0 flex-1 basis-48"
            />
            <Button
              className="lg:hidden"
              aria-haspopup="dialog"
              aria-expanded={drawerOpen}
              onClick={() => setDrawerOpen(true)}
            >
              篩選
              <FilterCount count={filters.activeCount} />
            </Button>
            <Toggle label="顯示方式" options={VIEW_OPTIONS} value={view} onChange={setView} />
          </div>

          {query.data ? (
            <p className="text-xs text-text-faint" aria-live="polite">
              共 {items.length} 筆
            </p>
          ) : null}

          {body}
        </div>
      </div>

      {drawerOpen ? (
        <Dialog
          title="篩選"
          onClose={() => setDrawerOpen(false)}
          footer={
            <>
              <Button kind="ghost" onClick={filters.clear} disabled={!filters.activeCount}>
                清除篩選
              </Button>
              <Button kind="primary" onClick={() => setDrawerOpen(false)}>
                看 {items.length} 筆結果
              </Button>
            </>
          }
        >
          <div className="space-y-5">{sidebar}</div>
        </Dialog>
      ) : null}
    </div>
  )
}
