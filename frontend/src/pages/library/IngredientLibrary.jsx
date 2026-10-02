// Frontend: the ingredient library, /ingredients.
//
// The sidebar: the category tree with counts, labels, the stub backlog (with
// its size), varieties only, and rating. Every filter is in the URL, which is
// what makes the ingredient page's category link - /ingredients?category=3 -
// land on that category, the defect the first version had.
//
// The category filter is EXACT: an ingredient filed under a child category is
// not listed under its parent. That is the API's `category_id`, the count the
// tree shows beside each node, and the category the detail page links to, so
// the three agree; the tree's hint says it in a sentence.
import { keepPreviousData } from '@tanstack/react-query'
import { useMemo } from 'react'

import { endpoints } from '../../api/endpoints'
import { FilterGroup, FilterOptions, FilterSwitch, FilterTree } from '../../components/layout/FilterPanel'
import LibraryLayout from '../../components/layout/LibraryLayout'
import { Badge } from '../../components/ui/primitives'
import { useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { useUrlFilters } from '../../hooks/useUrlFilters'
import { formatDays } from '../../lib/format'
import { flatten } from '../../lib/tree'

const SPEC = {
  category: { type: 'single', api: 'category_id' },
  label: { type: 'single', api: 'label_id' },
  stub: { type: 'bool', api: 'needs_detail' },
  variety: { type: 'bool', api: 'has_parent' },
  rating: { type: 'single', api: 'rating' },
}

export default function IngredientLibrary() {
  const filters = useUrlFilters(SPEC)
  const { values, toggle, setValue } = filters

  const ingredients = useApiQuery(endpoints.ingredients.list(), filters.apiParams, {
    placeholderData: keepPreviousData,
  })
  // The whole library, unfiltered: it names a variety's parent wherever the
  // filtered list does not include it, and it counts the stub backlog. One
  // request, and the cache shares it with any other page that lists
  // ingredients.
  const everything = useApiQuery(endpoints.ingredients.list())
  const categories = useApiQuery(endpoints.categories.tree())
  const labels = useApiQuery(endpoints.labels.list())
  const fixed = useFixedVocabularies()

  const categoryNames = useMemo(
    () => new Map(flatten(categories.data ?? []).map((node) => [node.id, node.display_name])),
    [categories.data],
  )
  const ingredientNames = useMemo(
    () => new Map((everything.data ?? []).map((row) => [row.id, row.display_name])),
    [everything.data],
  )
  const backlog = useMemo(
    () => (everything.data ?? []).filter((row) => row.needs_detail).length,
    [everything.data],
  )

  // A variety is described by what it is a variety of; anything else by its
  // category.
  const placeOf = (row) =>
    row.parent_id
      ? `${ingredientNames.get(row.parent_id) ?? '…'} 的品種`
      : (categoryNames.get(row.category_id) ?? null)

  const card = (row) => ({
    cover: row.cover,
    title: row.display_name,
    subtitle: row.name_en && row.name_en !== row.display_name ? row.name_en : null,
    meta: [placeOf(row), row.used_in_count ? `用於 ${row.used_in_count} 道` : null]
      .filter(Boolean)
      .join(' · '),
    badges:
      row.needs_detail || row.rating ? (
        <>
          {row.needs_detail ? <Badge kind="stub" /> : null}
          <Badge kind="rating" value={row.rating} />
        </>
      ) : null,
    // The table has a rating column, so its name cell carries only 待補.
    listBadges: row.needs_detail ? <Badge kind="stub" /> : null,
  })

  const columns = [
    { key: 'place', header: '分類 / 品種', render: placeOf },
    { key: 'fridge', header: '冷藏', render: (row) => formatDays(row.fridge) },
    {
      key: 'used',
      header: '用於',
      className: 'text-right tabular-nums',
      render: (row) => (row.used_in_count ? `${row.used_in_count} 道` : null),
    },
    {
      key: 'rating',
      header: '評等',
      render: (row) => (row.rating ? <Badge kind="rating" value={row.rating} /> : null),
    },
  ]

  const sidebar = (
    <>
      <FilterGroup title="分類" hint="只列出直接歸在該分類下的食材，不含子分類。">
        <FilterTree
          nodes={categories.data}
          selected={values.category}
          onToggle={(value) => toggle('category', value)}
        />
      </FilterGroup>
      <FilterGroup title="待整理">
        <FilterSwitch
          label="只看待補"
          checked={values.stub}
          onChange={(on) => setValue('stub', on)}
          count={backlog}
        />
        <FilterSwitch
          label="只看品種"
          checked={values.variety}
          onChange={(on) => setValue('variety', on)}
        />
      </FilterGroup>
      <FilterGroup title="評等">
        <FilterOptions
          options={(fixed.data?.ratings ?? []).map((r) => ({ value: r.value, label: r.label }))}
          selected={values.rating}
          onToggle={(value) => toggle('rating', value)}
        />
      </FilterGroup>
      <FilterGroup title="標籤">
        <FilterOptions
          options={(labels.data ?? []).map((label) => ({
            value: String(label.id),
            label: label.display_name,
            count: label.ingredient_count,
          }))}
          selected={values.label}
          onToggle={(value) => toggle('label', value)}
        />
      </FilterGroup>
    </>
  )

  return (
    <LibraryLayout
      title="食材"
      library="ingredients"
      add={{ to: '/edit/ingredients/new', label: '新增食材' }}
      filters={filters}
      sidebar={sidebar}
      query={ingredients}
      card={card}
      columns={columns}
      itemTo={(row) => `/ingredients/${row.id}`}
      searchPlaceholder="搜尋名稱或別名…"
      emptyText="還沒有任何食材。"
      noMatchText="沒有符合條件的食材。"
    />
  )
}
