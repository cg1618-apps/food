// Frontend: the ingredient library, /ingredients.
//
// The sidebar: the category tree with counts and, under each category, the
// groups filed there (an ingredient with varieties - lib/ingredientGroups.js);
// 品種 (全部 / 只看主項 / 只看品種); the stub backlog (with its size); rating;
// labels. Every filter is in the URL, which is what makes the ingredient
// page's category link - /ingredients?category=3 - land on that category, the
// defect the first version had.
//
// The list is cut into one section per category, groups first, each group's
// varieties drawn under it. Choosing a group lists it and every variety below
// it (the API's group_id); a group and a category are never both chosen.
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
import { Badge, Toggle } from '../../components/ui/primitives'
import { useApiQuery, useFixedVocabularies, useLabels } from '../../hooks/useApi'
import { useUrlFilters } from '../../hooks/useUrlFilters'
import { formatDays } from '../../lib/format'
import { arrangeIngredients, categoryGroupTree, groupSizes } from '../../lib/ingredientGroups'
import { flatten } from '../../lib/tree'

const VARIETY_OPTIONS = [
  { value: '', label: '全部' },
  { value: 'top', label: '只看主項' },
  { value: 'only', label: '只看品種' },
]

const SPEC = {
  category: { type: 'single', api: 'category_id', id: true },
  label: { type: 'single', api: 'label_id', id: true },
  stub: { type: 'bool', api: 'needs_detail' },
  group: { type: 'single', api: 'group_id', id: true },
  // 只看主項 sends has_parent=false, which a bool key cannot. `1` is what the
  // 只看品種 switch this replaced wrote, so an old link still lands.
  variety: { type: 'single', api: 'has_parent', values: { top: false, only: true }, aliases: { 1: 'only' } },
  rating: { type: 'single', api: 'rating' },
}

export default function IngredientLibrary() {
  const filters = useUrlFilters(SPEC)
  const { values, toggle, setValue, setValues } = filters

  const ingredients = useApiQuery(endpoints.ingredients.list(), filters.apiParams, {
    placeholderData: keepPreviousData,
  })
  // The whole library, unfiltered: it says which ingredients are groups
  // whatever the filters hide, names a variety's parent wherever the filtered
  // list does not include it, and counts the stub backlog. One
  // request, and the cache shares it with any other page that lists
  // ingredients.
  const everything = useApiQuery(endpoints.ingredients.list())
  const categories = useApiQuery(endpoints.categories.tree())
  const labels = useLabels('ingredient')
  const fixed = useFixedVocabularies()

  const categoryNames = useMemo(
    () => new Map(flatten(categories.data ?? []).map((node) => [node.id, node.display_name])),
    [categories.data],
  )
  const ingredientNames = useMemo(
    () => new Map((everything.data ?? []).map((row) => [row.id, row.display_name])),
    [everything.data],
  )
  const sizes = useMemo(() => groupSizes(everything.data ?? []), [everything.data])
  const tree = useMemo(
    () => categoryGroupTree(categories.data ?? [], everything.data ?? []),
    [categories.data, everything.data],
  )
  const arrange = (rows) => arrangeIngredients(rows, everything.data ?? rows, categories.data ?? [])
  const backlog = useMemo(
    () => (everything.data ?? []).filter((row) => row.needs_detail).length,
    [everything.data],
  )

  // The section heading already names the category, so a row says only what
  // it does not: whose variety it is, or how many varieties it has. Inside a
  // group block the parent is beside it, so a direct variety names its
  // category instead - and only when that differs from the block's (乾辣椒 is
  // 乾貨 inside 辣椒's 蔬菜 block). `place` is { depth, root } in a block.
  const placeOf = (row, place = {}) => {
    const parts = []
    if (place.depth === 1) {
      if (row.category_id !== place.root.category_id) parts.push(categoryNames.get(row.category_id))
    } else if (row.parent_id) {
      parts.push(`${ingredientNames.get(row.parent_id) ?? '…'} 的品種`)
    }
    if (sizes.has(row.id)) parts.push(`${sizes.get(row.id)} 個品種`)
    return parts.filter(Boolean).join(' · ') || null
  }

  const card = (row, place) => ({
    cover: row.cover,
    title: row.display_name,
    subtitle: row.name_en && row.name_en !== row.display_name ? row.name_en : null,
    meta: [placeOf(row, place), row.used_in_count ? `用於 ${row.used_in_count} 道` : null]
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
    { key: 'place', header: '品種', render: placeOf },
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

  // One tree, two filters: a category node sets `category`, a group node
  // sets `group`, each clearing the other in the same history entry.
  const selectedKey = values.group
    ? `group:${values.group}`
    : values.category
      ? `category:${values.category}`
      : ''
  const choose = (node) => {
    const value = String(node.id)
    if (node.kind === 'group') setValues({ group: values.group === value ? '' : value, category: '' })
    else setValues({ category: values.category === value ? '' : value, group: '' })
  }

  const sidebar = (
    <>
      <FilterGroup
        title="分類"
        hint="分類只列出直接歸在該分類下的食材，不含子分類。○ 是有品種的食材，選它會列出它和它所有的品種。"
      >
        <FilterTree nodes={tree} selectedKey={selectedKey} onSelect={choose} />
      </FilterGroup>
      <FilterGroup title="品種" hint="只看主項會隱藏所有品種，例如只看雞肉、不看雞腿。">
        <Toggle
          label="品種"
          options={VARIETY_OPTIONS}
          value={values.variety}
          onChange={(value) => setValue('variety', value)}
          className="flex w-full [&>button]:flex-1 [&>button]:px-1 [&>button]:whitespace-nowrap"
        />
      </FilterGroup>
      <FilterGroup title="待整理">
        <FilterSwitch
          label="只看待補"
          checked={values.stub}
          onChange={(on) => setValue('stub', on)}
          count={backlog}
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
          empty="還沒有食材標籤。"
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
      arrange={arrange}
      searchPlaceholder="搜尋名稱或別名…"
      emptyText="還沒有任何食材。"
      noMatchText="沒有符合條件的食材。"
    />
  )
}
