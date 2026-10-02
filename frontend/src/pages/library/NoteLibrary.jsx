// Frontend: the kitchen-notes library, /notes.
//
// The sidebar: kind and label, both "any of" and both in the URL. The API
// lists notes newest first, and the library keeps that order: a note is
// usually looked for soon after it was saved.
import { keepPreviousData } from '@tanstack/react-query'

import { endpoints } from '../../api/endpoints'
import { FilterGroup, FilterOptions } from '../../components/layout/FilterPanel'
import LibraryLayout from '../../components/layout/LibraryLayout'
import { fixedLabel, useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { useUrlFilters } from '../../hooks/useUrlFilters'
import { linkHost } from '../../lib/format'

const SPEC = {
  kind: { type: 'multi', api: 'kind' },
  label: { type: 'multi', api: 'label_id' },
}

export default function NoteLibrary() {
  const filters = useUrlFilters(SPEC)
  const { values, toggle } = filters

  const notes = useApiQuery(endpoints.notes.list(), filters.apiParams, {
    placeholderData: keepPreviousData,
  })
  const labels = useApiQuery(endpoints.labels.list())
  const fixed = useFixedVocabularies()

  const kindLabel = (value) => fixedLabel(fixed.data?.kitchen_note_kinds, value)

  const card = (row) => ({
    cover: row.cover,
    title: row.title,
    meta: [kindLabel(row.kind), linkHost(row.url)].filter(Boolean).join(' · '),
  })

  const columns = [
    { key: 'kind', header: '種類', className: 'whitespace-nowrap', render: (row) => kindLabel(row.kind) },
    { key: 'host', header: '連結', render: (row) => linkHost(row.url) },
  ]

  const sidebar = (
    <>
      <FilterGroup title="種類">
        <FilterOptions
          options={(fixed.data?.kitchen_note_kinds ?? []).map(({ value, label }) => ({ value, label }))}
          selected={values.kind}
          onToggle={(value) => toggle('kind', value)}
        />
      </FilterGroup>
      <FilterGroup title="標籤">
        <FilterOptions
          options={(labels.data ?? []).map((label) => ({
            value: String(label.id),
            label: label.display_name,
            count: label.note_count,
          }))}
          selected={values.label}
          onToggle={(value) => toggle('label', value)}
        />
      </FilterGroup>
    </>
  )

  return (
    <LibraryLayout
      title="筆記"
      library="notes"
      add={{ to: '/edit/notes/new', label: '新增筆記' }}
      filters={filters}
      sidebar={sidebar}
      query={notes}
      card={card}
      columns={columns}
      itemTo={(row) => `/notes/${row.id}`}
      searchPlaceholder="搜尋標題或內文…"
      emptyText="還沒有任何筆記。"
      noMatchText="沒有符合條件的筆記。"
    />
  )
}
