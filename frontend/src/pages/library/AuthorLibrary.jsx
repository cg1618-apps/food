// Frontend: the author library, /authors.
//
// Who the recipes came from - 阿基師, 詹姆士, Babish - each a cover (the first
// picture of the author's gallery) or a table row, to the author's page.
// Filed under 食譜 in the navigation, and reached from the recipe library's
// header; there is no nav item of its own.
//
// Nothing to filter by but the name, so there is no sidebar: the search box
// matches either name. The author list is read whole and in name order (the
// vocabulary factory's list, which the recipe form and the recipe-library
// filter read too), so the search narrows it here rather than asking again.
import { useMemo } from 'react'

import { endpoints } from '../../api/endpoints'
import LibraryLayout from '../../components/layout/LibraryLayout'
import { useApiQuery } from '../../hooks/useApi'
import { useUrlFilters } from '../../hooks/useUrlFilters'
import { matchesAuthor } from '../../lib/authors'

const SPEC = {}

const recipeCount = (row) => (row.recipe_count ? `${row.recipe_count} 份食譜` : '還沒有食譜')

export default function AuthorLibrary() {
  const filters = useUrlFilters(SPEC)
  const authors = useApiQuery(endpoints.authors.list())
  const term = filters.apiParams.q

  const data = useMemo(
    () => (authors.data ? authors.data.filter((row) => matchesAuthor(row, term)) : authors.data),
    [authors.data, term],
  )

  const card = (row) => ({
    cover: row.cover,
    title: row.display_name,
    subtitle: row.name_cn && row.name_en ? row.name_en : null,
    meta: recipeCount(row),
  })

  const columns = [
    {
      key: 'recipes',
      header: '食譜數',
      className: 'whitespace-nowrap tabular-nums',
      render: (row) => row.recipe_count,
    },
  ]

  return (
    <LibraryLayout
      title="作者"
      library="authors"
      add={{ to: '/edit/authors/new', label: '新增作者' }}
      filters={filters}
      query={{ ...authors, data }}
      card={card}
      columns={columns}
      itemTo={(row) => `/authors/${row.id}`}
      searchPlaceholder="搜尋作者的名稱…"
      emptyText="還沒有任何作者。"
      noMatchText="沒有符合的作者。"
    />
  )
}
