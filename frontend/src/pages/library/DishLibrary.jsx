// Frontend: the dish library, /dishes - 料理 and 醬料, each with its recipes.
//
// RecipeLibrary's shape exactly: the sidebar is 種類 (料理 / 醬料), 類別, 地區
// and 標籤, every one "any of" (the API takes the parameter repeated), and
// all of it in the URL. A card is the dish's cover - its own first picture,
// else its first recipe's (the API answers which) - its kind, course and
// region, and how many recipes make it.
import { keepPreviousData } from '@tanstack/react-query'

import { endpoints } from '../../api/endpoints'
import { FilterGroup, FilterOptions } from '../../components/layout/FilterPanel'
import LibraryLayout from '../../components/layout/LibraryLayout'
import { fixedLabel, useApiQuery, useFixedVocabularies, useLabels } from '../../hooks/useApi'
import { useUrlFilters } from '../../hooks/useUrlFilters'

const SPEC = {
  kind: { type: 'multi', api: 'kind' },
  course: { type: 'multi', api: 'course_id', id: true },
  region: { type: 'multi', api: 'region_id', id: true },
  label: { type: 'multi', api: 'label_id', id: true },
}

// A vocabulary's rows as filter options: ids as the URL's strings.
const asOptions = (rows) =>
  (rows ?? []).map((row) => ({ value: String(row.id), label: row.display_name }))

const fixedOptions = (list) => (list ?? []).map(({ value, label }) => ({ value, label }))

const recipeCount = (row) => (row.recipe_count ? `${row.recipe_count} 份食譜` : '還沒有食譜')

export default function DishLibrary() {
  const filters = useUrlFilters(SPEC)
  const { values, toggle } = filters

  const dishes = useApiQuery(endpoints.dishes.list(), filters.apiParams, {
    placeholderData: keepPreviousData,
  })
  const courses = useApiQuery(endpoints.courses.list())
  const regions = useApiQuery(endpoints.regions.list())
  const labels = useLabels('dish')
  const fixed = useFixedVocabularies()
  const kindLabel = (row) => fixedLabel(fixed.data?.dish_kinds, row.kind)

  const card = (row) => ({
    cover: row.cover,
    title: row.display_name,
    subtitle: row.name_en && row.name_en !== row.display_name ? row.name_en : null,
    meta: [kindLabel(row), row.course?.display_name, row.region?.display_name, recipeCount(row)]
      .filter(Boolean)
      .join(' · '),
  })

  const columns = [
    { key: 'kind', header: '種類', className: 'whitespace-nowrap', render: kindLabel },
    { key: 'course', header: '類別', render: (row) => row.course?.display_name ?? null },
    { key: 'region', header: '地區', render: (row) => row.region?.display_name ?? null },
    {
      key: 'recipes',
      header: '食譜',
      className: 'whitespace-nowrap tabular-nums',
      render: (row) => (row.recipe_count ? `${row.recipe_count} 份` : null),
    },
  ]

  const sidebar = (
    <>
      <FilterGroup title="種類">
        <FilterOptions
          options={fixedOptions(fixed.data?.dish_kinds)}
          selected={values.kind}
          onToggle={(value) => toggle('kind', value)}
        />
      </FilterGroup>
      <FilterGroup title="類別">
        <FilterOptions
          options={asOptions(courses.data)}
          selected={values.course}
          onToggle={(value) => toggle('course', value)}
        />
      </FilterGroup>
      <FilterGroup title="地區">
        <FilterOptions
          options={asOptions(regions.data)}
          selected={values.region}
          onToggle={(value) => toggle('region', value)}
        />
      </FilterGroup>
      <FilterGroup title="標籤">
        <FilterOptions
          options={(labels.data ?? []).map((label) => ({
            value: String(label.id),
            label: label.display_name,
            count: label.dish_count,
          }))}
          selected={values.label}
          onToggle={(value) => toggle('label', value)}
          empty="還沒有料理標籤。"
        />
      </FilterGroup>
    </>
  )

  return (
    <LibraryLayout
      title="料理"
      library="dishes"
      add={{ to: '/edit/dishes/new', label: '新增料理' }}
      filters={filters}
      sidebar={sidebar}
      query={dishes}
      card={card}
      columns={columns}
      itemTo={(row) => `/dishes/${row.id}`}
      searchPlaceholder="搜尋名稱或別名…"
      emptyText="還沒有任何料理。"
      noMatchText="沒有符合條件的料理。"
    />
  )
}
