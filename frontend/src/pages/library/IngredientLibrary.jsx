import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import { Card, Empty, ErrorNote, Input, Loading, Pill, Select } from '../../components/ui'
import { useApiQuery } from '../../hooks/useApi'
import { flatten } from '../../lib/tree'

export default function IngredientLibrary() {
  const [q, setQ] = useState('')
  const [categoryId, setCategoryId] = useState('')
  const [labelId, setLabelId] = useState('')
  const [stubsOnly, setStubsOnly] = useState(false)

  const params = useMemo(
    () => ({
      q: q.trim() || undefined,
      category_id: categoryId || undefined,
      label_id: labelId || undefined,
      // Only sent when true. Sending false would mean "only the finished
      // ones", which is a different filter nothing on this page offers.
      needs_detail: stubsOnly ? true : undefined,
    }),
    [q, categoryId, labelId, stubsOnly],
  )

  const ingredients = useApiQuery(endpoints.ingredients.list(), params)
  const categories = useApiQuery(endpoints.categories.tree())
  const labels = useApiQuery(endpoints.labels.list())
  const stubs = useApiQuery(endpoints.ingredients.list(), { needs_detail: true })

  const flatCategories = useMemo(() => flatten(categories.data ?? []), [categories.data])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h1 className="text-xl font-semibold">Ingredients</h1>
        <Link
          to="/edit/ingredient/new"
          className="rounded border border-brand bg-brand px-3 py-1.5 text-sm text-canvas"
        >
          Add an ingredient
        </Link>
      </div>

      <Card className="space-y-3">
        <Input
          value={q}
          onChange={(event) => setQ(event.target.value)}
          placeholder="Search a name or an alias…"
        />
        <div className="grid gap-2 sm:grid-cols-2">
          <Select value={categoryId} onChange={(event) => setCategoryId(event.target.value)}>
            <option value="">Every category</option>
            {flatCategories.map((node) => (
              <option key={node.id} value={node.id}>
                {'— '.repeat(node.depth)}
                {node.display_name} ({node.ingredient_count})
              </option>
            ))}
          </Select>
          <Select value={labelId} onChange={(event) => setLabelId(event.target.value)}>
            <option value="">Every label</option>
            {(labels.data ?? []).map((label) => (
              <option key={label.id} value={label.id}>
                {label.display_name} ({label.ingredient_count})
              </option>
            ))}
          </Select>
        </div>

        {/* The stub backlog is a filter, not a page - but it needs a visible
            count, or it is invisible and stubs accumulate forever. */}
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={stubsOnly}
            onChange={(event) => setStubsOnly(event.target.checked)}
          />
          Needs detail
          {stubs.data?.length ? <Pill tone="warn">{stubs.data.length}</Pill> : null}
        </label>
      </Card>

      {ingredients.isPending ? <Loading /> : null}
      {ingredients.error ? <ErrorNote error={ingredients.error} /> : null}
      {ingredients.data?.length === 0 ? (
        <Empty>Nothing here yet. Add the first ingredient.</Empty>
      ) : null}

      <ul className="grid gap-2 sm:grid-cols-2">
        {(ingredients.data ?? []).map((row) => (
          <li key={row.id}>
            <Link to={`/ingredient/${row.id}`} className="block">
              <Card className="hover:border-brand">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium">{row.display_name}</span>
                  {row.needs_detail ? <Pill tone="warn">needs detail</Pill> : null}
                </div>
                {row.name_en && row.name_en !== row.display_name ? (
                  <span className="text-sm text-text-muted">{row.name_en}</span>
                ) : null}
              </Card>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
