// Frontend: one ingredient, /ingredients/:id - the page this app exists for.
//
// It is what gets opened on a phone in a shop, signed out, so it reads top to
// bottom in the order of that errand: what it is, how to pick a good one,
// which variety, where to get it, how to keep it, how to heat it, where to
// read more, and what it goes into.
//
//   header   the cover, category (a link to the library filtered by it), the
//            parent for a variety, names, rating, how many recipes use it and
//            how many varieties it has, labels
//   說明 · 挑選 · 品種 (children with rating and where bought) · 哪裡買 ·
//   保存 (a state x method grid, lib/storageGrid.js, then the general notes) ·
//   加熱 (°C with the °F beside it) · 參考連結 · 用在
//
// Every section with nothing in it is left out. A stub - an ingredient that
// is only a name, made by a recipe line - shows its header and a 待補 note
// that links to the form, which is the one useful thing to do with it.
//
// 「合併到…」 (components/modals/MergeDialog.jsx) is for the duplicate a stub
// usually turns out to be.
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import { DetailActions, DetailStatus, LabelLinks, Prose, RecipeLinks } from '../../components/layout/Detail'
import MergeDialog from '../../components/modals/MergeDialog'
import Gallery from '../../components/ui/Gallery'
import { Badge, Button, LinkButton, Section } from '../../components/ui/primitives'
import { useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { linkHost } from '../../lib/format'
import { buildStorageGrid } from '../../lib/storageGrid'
import { formatTemperature } from '../../lib/temperature'

function Varieties({ items }) {
  return (
    <ul className="divide-y divide-border">
      {items.map((child) => (
        <li key={child.id} className="flex items-start gap-3 py-2">
          <Badge kind="rating" value={child.rating} />
          <div className="min-w-0 flex-1">
            <p className="flex flex-wrap items-center gap-2">
              <Link to={`/ingredients/${child.id}`} className="font-medium text-brand hover:underline">
                {child.display_name}
              </Link>
              {child.needs_detail ? <Badge kind="stub" /> : null}
            </p>
            {child.sourcing_notes ? (
              <p className="whitespace-pre-line text-sm text-text-muted">{child.sourcing_notes}</p>
            ) : null}
          </div>
        </li>
      ))}
    </ul>
  )
}

function StorageGrid({ grid }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="border-b border-border-strong text-left">
            <th scope="col" className="py-1.5 pr-3 font-medium text-text-muted">
              <span className="sr-only">狀態</span>
            </th>
            {grid.columns.map((column) => (
              <th key={column.value} scope="col" className="px-3 py-1.5 font-bold">
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {grid.rows.map((row) => (
            <tr key={row.value} className="border-b border-border align-top">
              <th scope="row" className="whitespace-nowrap py-2 pr-3 text-left font-medium text-text-muted">
                {row.label}
              </th>
              {row.cells.map((cell, index) => (
                <td key={grid.columns[index].value} className="px-3 py-2">
                  {cell ? (
                    <>
                      {cell.days ? <span className="font-medium tabular-nums">{cell.days}</span> : null}
                      {cell.notes ? (
                        <span className="block whitespace-pre-line text-xs text-text-muted">{cell.notes}</span>
                      ) : null}
                    </>
                  ) : (
                    <span className="text-text-faint" aria-label="沒有">
                      –
                    </span>
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Heating({ rows }) {
  return (
    <ul className="divide-y divide-border">
      {rows.map((row) => {
        const facts = [
          formatTemperature(row.temperature_c),
          row.duration,
          row.preheat ? '要預熱' : null,
          row.flip ? '中途翻面' : null,
        ].filter(Boolean)
        return (
          <li key={row.id} className="space-y-0.5 py-2">
            <p className="flex flex-wrap items-baseline gap-x-3">
              <span className="font-bold">{row.method.display_name}</span>
              {facts.length ? <span className="tabular-nums">{facts.join(' · ')}</span> : null}
            </p>
            {row.notes ? <p className="whitespace-pre-line text-sm text-text-muted">{row.notes}</p> : null}
          </li>
        )
      })}
    </ul>
  )
}

export default function Ingredient() {
  const { id } = useParams()
  const query = useApiQuery(endpoints.ingredients.detail(id))
  const fixed = useFixedVocabularies()
  const [merging, setMerging] = useState(false)
  const item = query.data

  if (!item) {
    return (
      <DetailStatus
        query={query}
        missing="找不到這個食材。"
        back={<LinkButton to="/ingredients">回到食材庫</LinkButton>}
      />
    )
  }

  const otherNames = [item.name_cn, item.name_en, item.name_alt].filter(
    (name) => name && name !== item.display_name,
  )
  const counts = [
    item.used_in.length ? `用在 ${item.used_in.length} 道食譜` : null,
    item.children.length ? `${item.children.length} 個品種` : null,
  ].filter(Boolean)
  const grid = buildStorageGrid(
    item.preservation,
    fixed.data?.preservation_states,
    fixed.data?.preservation_methods,
  )

  return (
    <article className="mx-auto max-w-2xl space-y-8">
      <Gallery images={item.images} title={item.display_name} />

      <header className="space-y-3">
        <p className="flex flex-wrap items-center gap-x-2 text-sm text-text-muted">
          {item.category ? (
            <Link to={`/ingredients?category=${item.category.id}`} className="hover:text-brand">
              {item.category.display_name}
            </Link>
          ) : null}
          {item.parent ? (
            <>
              <span aria-hidden="true">›</span>
              <Link to={`/ingredients/${item.parent.id}`} className="hover:text-brand">
                {item.parent.display_name}
              </Link>
              <span>的品種</span>
            </>
          ) : null}
        </p>
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-3xl font-bold leading-tight">{item.display_name}</h1>
          <Badge kind="rating" value={item.rating} />
          {item.needs_detail ? <Badge kind="stub" /> : null}
        </div>
        {otherNames.length ? <p className="text-text-muted">{otherNames.join(' · ')}</p> : null}
        {item.aliases.length ? (
          <p className="text-sm text-text-muted">也叫 {item.aliases.join('、')}</p>
        ) : null}
        {counts.length ? <p className="text-sm text-text-muted">{counts.join(' · ')}</p> : null}
        <LabelLinks labels={item.labels} to={(label) => `/ingredients?label=${label.id}`} />
      </header>

      {item.needs_detail ? (
        <p className="rounded-md border border-warn/40 bg-warn-soft px-3 py-2 text-sm text-warn">
          這個食材只有名字，細節待補。
          <Link to={`/edit/ingredients/${item.id}`} className="ml-1 font-medium underline">
            去補上
          </Link>
        </p>
      ) : null}

      {item.description ? (
        <Section title="說明">
          <Prose>{item.description}</Prose>
        </Section>
      ) : null}

      {item.selection_notes ? (
        <Section title="挑選">
          <Prose>{item.selection_notes}</Prose>
        </Section>
      ) : null}

      {item.children.length ? (
        <Section title="品種">
          <Varieties items={item.children} />
        </Section>
      ) : null}

      {item.sourcing_notes ? (
        <Section title="哪裡買">
          <Prose>{item.sourcing_notes}</Prose>
        </Section>
      ) : null}

      {grid.rows.length || item.preservation_notes ? (
        <Section title="保存">
          {grid.rows.length ? <StorageGrid grid={grid} /> : null}
          <Prose>{item.preservation_notes}</Prose>
        </Section>
      ) : null}

      {item.heating.length ? (
        <Section title="加熱">
          <Heating rows={item.heating} />
        </Section>
      ) : null}

      {item.links.length ? (
        <Section title="參考連結">
          <ul className="space-y-1">
            {item.links.map((link) => (
              <li key={`${link.sort_order}-${link.url}`}>
                <a href={link.url} target="_blank" rel="noreferrer" className="text-brand hover:underline">
                  {link.title || linkHost(link.url)} ↗
                </a>
              </li>
            ))}
          </ul>
        </Section>
      ) : null}

      {item.used_in.length ? (
        <Section title="用在">
          <RecipeLinks recipes={item.used_in} />
        </Section>
      ) : null}

      <DetailActions
        kind="ingredient"
        id={item.id}
        name={item.display_name}
        editTo={`/edit/ingredients/${item.id}`}
      >
        <Button onClick={() => setMerging(true)}>合併到…</Button>
      </DetailActions>

      {merging ? <MergeDialog ingredient={item} onClose={() => setMerging(false)} /> : null}
    </article>
  )
}
