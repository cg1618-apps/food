// Frontend: the recipe library, /recipes - the app's front page.
//
// The sidebar: course, status, kind, method, equipment, author, label, and
// written up / bookmark only. Every filter but the last is "any of" (the API
// takes the parameter repeated); written-up is one choice of two, since both
// at once is no filter. All of it is in the URL.
//
// A recipe that is only a saved link carries the 書籤 badge: it is in the
// library to be written up later, and the badge is what makes that backlog
// visible from the cover view.
import { keepPreviousData } from '@tanstack/react-query'

import { endpoints } from '../../api/endpoints'
import { FilterGroup, FilterOptions } from '../../components/layout/FilterPanel'
import LibraryLayout from '../../components/layout/LibraryLayout'
import { Badge } from '../../components/ui/primitives'
import { useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { useUrlFilters } from '../../hooks/useUrlFilters'

const SPEC = {
  course: { type: 'multi', api: 'course_id', id: true },
  status: { type: 'multi', api: 'status_id', id: true },
  kind: { type: 'multi', api: 'kind' },
  method: { type: 'multi', api: 'method_id', id: true },
  equipment: { type: 'multi', api: 'equipment_id', id: true },
  author: { type: 'multi', api: 'author_id', id: true },
  label: { type: 'multi', api: 'label_id', id: true },
  written: { type: 'single', api: 'written_up' },
}

const WRITTEN_OPTIONS = [
  { value: 'true', label: '已寫成' },
  { value: 'false', label: '只有書籤' },
]

// A vocabulary's rows as filter options: ids as the URL's strings.
const asOptions = (rows) =>
  (rows ?? []).map((row) => ({ value: String(row.id), label: row.display_name }))

const fixedOptions = (list) => (list ?? []).map(({ value, label }) => ({ value, label }))

const joinNames = (refs) => (refs?.length ? refs.map((ref) => ref.display_name).join('、') : null)

export default function RecipeLibrary() {
  const filters = useUrlFilters(SPEC)
  const { values, toggle } = filters

  const recipes = useApiQuery(endpoints.recipes.list(), filters.apiParams, {
    placeholderData: keepPreviousData,
  })
  const courses = useApiQuery(endpoints.courses.list())
  const statuses = useApiQuery(endpoints.statuses.list())
  const methods = useApiQuery(endpoints.methods.list())
  const equipment = useApiQuery(endpoints.equipment.list())
  const authors = useApiQuery(endpoints.authors.list())
  const labels = useApiQuery(endpoints.labels.list())
  const fixed = useFixedVocabularies()

  const card = (row) => ({
    cover: row.cover,
    title: row.display_name,
    subtitle: row.name_en && row.name_en !== row.display_name ? row.name_en : null,
    meta: [row.course?.display_name, row.time, row.authors[0]?.display_name].filter(Boolean).join(' · '),
    badges: row.written_up ? null : <Badge kind="bookmark" />,
  })

  const columns = [
    { key: 'course', header: '類別', render: (row) => row.course?.display_name ?? null },
    { key: 'methods', header: '做法', render: (row) => joinNames(row.methods) },
    { key: 'time', header: '時間', className: 'whitespace-nowrap', render: (row) => row.time || null },
    { key: 'authors', header: '作者', render: (row) => joinNames(row.authors) },
    {
      key: 'status',
      header: '狀態',
      className: 'whitespace-nowrap',
      render: (row) => row.status?.display_name ?? null,
    },
  ]

  const sidebar = (
    <>
      <FilterGroup title="寫成了嗎">
        <FilterOptions
          options={WRITTEN_OPTIONS}
          selected={values.written}
          onToggle={(value) => toggle('written', value)}
        />
      </FilterGroup>
      <FilterGroup title="類別">
        <FilterOptions
          options={asOptions(courses.data)}
          selected={values.course}
          onToggle={(value) => toggle('course', value)}
        />
      </FilterGroup>
      <FilterGroup title="狀態">
        <FilterOptions
          options={asOptions(statuses.data)}
          selected={values.status}
          onToggle={(value) => toggle('status', value)}
        />
      </FilterGroup>
      <FilterGroup title="種類">
        <FilterOptions
          options={fixedOptions(fixed.data?.recipe_kinds)}
          selected={values.kind}
          onToggle={(value) => toggle('kind', value)}
        />
      </FilterGroup>
      <FilterGroup title="做法">
        <FilterOptions
          options={asOptions(methods.data)}
          selected={values.method}
          onToggle={(value) => toggle('method', value)}
        />
      </FilterGroup>
      <FilterGroup title="器材">
        <FilterOptions
          options={asOptions(equipment.data)}
          selected={values.equipment}
          onToggle={(value) => toggle('equipment', value)}
        />
      </FilterGroup>
      <FilterGroup title="作者">
        <FilterOptions
          options={asOptions(authors.data)}
          selected={values.author}
          onToggle={(value) => toggle('author', value)}
        />
      </FilterGroup>
      <FilterGroup title="標籤">
        <FilterOptions
          options={(labels.data ?? []).map((label) => ({
            value: String(label.id),
            label: label.display_name,
            count: label.recipe_count,
          }))}
          selected={values.label}
          onToggle={(value) => toggle('label', value)}
        />
      </FilterGroup>
    </>
  )

  return (
    <LibraryLayout
      title="食譜"
      library="recipes"
      add={{ to: '/edit/recipes/new', label: '新增食譜' }}
      filters={filters}
      sidebar={sidebar}
      query={recipes}
      card={card}
      columns={columns}
      itemTo={(row) => `/recipes/${row.id}`}
      searchPlaceholder="搜尋名稱或別名…"
      emptyText="還沒有任何食譜。"
      noMatchText="沒有符合條件的食譜。"
    />
  )
}
