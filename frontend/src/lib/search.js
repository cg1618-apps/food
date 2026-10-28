// Frontend: the universal search - the kinds it answers, where each row goes,
// and the dropdown's flat order.
//
// GET /api/search answers one bucket per kind (app/routers/search.py), each
// best match first. This is the one table that says, per bucket, what label
// heads it and where a row and its 編輯 link go, so the top bar's dropdown
// (components/layout/NavSearch.jsx) and the results page (pages/Search.jsx)
// cannot disagree about either.
//
// 加熱 and TBD have no page per entry: a row opens the list page at the
// entry's anchor (hooks/useHashTarget.js highlights it), and 編輯 opens the
// list's edit page.

export const SEARCH_TYPES = [
  {
    key: 'dishes',
    label: '料理',
    itemTo: (id) => `/dishes/${id}`,
    editTo: (id) => `/edit/dishes/${id}`,
    hasCover: true,
  },
  {
    key: 'recipes',
    label: '食譜',
    itemTo: (id) => `/recipes/${id}`,
    editTo: (id) => `/edit/recipes/${id}`,
    hasCover: true,
  },
  {
    key: 'ingredients',
    label: '食材',
    itemTo: (id) => `/ingredients/${id}`,
    editTo: (id) => `/edit/ingredients/${id}`,
    hasCover: true,
  },
  {
    key: 'notes',
    label: '筆記',
    itemTo: (id) => `/notes/${id}`,
    editTo: (id) => `/edit/notes/${id}`,
    hasCover: true,
  },
  {
    key: 'authors',
    label: '作者',
    itemTo: (id) => `/authors/${id}`,
    editTo: (id) => `/edit/authors/${id}`,
    hasCover: true,
  },
  {
    key: 'heating',
    label: '加熱',
    itemTo: (id) => `/heating#${entryAnchor('heating', id)}`,
    editTo: () => '/edit/heating',
    hasCover: false,
  },
  {
    key: 'tbd',
    label: 'TBD',
    itemTo: (id) => `/tbd#${entryAnchor('tbd', id)}`,
    editTo: () => '/edit/tbd',
    hasCover: false,
  },
]

// Rows per kind in the dropdown, and the `limit` it asks for: a shortcut to
// the likely row, not the result list - Enter opens /search for everything.
export const DROPDOWN_LIMIT = 3
// Rows per kind on /search; the API's own cap.
export const PAGE_LIMIT = 50

/** The id an entry of a page without detail pages carries, for its anchor. */
export function entryAnchor(kind, id) {
  return `${kind}-${id}`
}

/** The results page for `q`, or null for a blank term. */
export function searchPath(q) {
  const term = (q ?? '').trim()
  return term ? `/search?${new URLSearchParams({ q: term })}` : null
}

/**
 * The buckets that hold something, in SEARCH_TYPES order, each
 * `{ type, rows }`. A bucket the response lacks reads as empty.
 */
export function groupResults(results) {
  return SEARCH_TYPES.map((type) => ({ type, rows: results?.[type.key] ?? [] })).filter(
    (group) => group.rows.length > 0,
  )
}

/**
 * The groups as one list, in the order Up and Down walk them: each entry
 * `{ type, row, index }`, `index` being its place in the whole list.
 */
export function flattenGroups(groups) {
  const flat = []
  for (const { type, rows } of groups) {
    for (const row of rows) flat.push({ type, row, index: flat.length })
  }
  return flat
}
