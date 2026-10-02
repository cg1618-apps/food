import { Link, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import { Card, Empty, ErrorNote, Loading, Pill } from '../../components/ui'
import { useApiQuery } from '../../hooks/useApi'

const STATE_LABELS = { opened: '已開封', cooked: '熟食' }

// min = max is one number, a lone max is "up to", a lone min is "at least".
function durationText({ duration_min_days: min, duration_max_days: max }) {
  if (min && max) return min === max ? `${min} days` : `${min}–${max} days`
  if (max) return `up to ${max} days`
  if (min) return `at least ${min} days`
  return null
}

function Notes({ title, body }) {
  if (!body) return null
  return (
    <section className="space-y-1">
      <h2 className="text-sm font-semibold text-text-muted">{title}</h2>
      {/* whitespace-pre-line, not a markdown renderer: notes are written as
          short lines and read on a phone, and a renderer is a dependency this
          page has not yet earned. */}
      <p className="whitespace-pre-line text-sm">{body}</p>
    </section>
  )
}

export default function IngredientDetail() {
  const { id } = useParams()
  const { data, isPending, error } = useApiQuery(endpoints.ingredients.detail(id))

  if (isPending) return <Loading />
  if (error) return <ErrorNote error={error} />
  if (!data) return <Empty>No such ingredient.</Empty>

  const hasNotes =
    data.description || data.selection_notes || data.sourcing_notes || data.preservation_notes

  return (
    <article className="space-y-5">
      <header className="space-y-1">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold">{data.display_name}</h1>
          {data.needs_detail ? <Pill tone="warn">needs detail</Pill> : null}
        </div>
        <p className="text-sm text-text-muted">
          {[data.name_cn, data.name_en, data.name_alt].filter(Boolean).join(' · ')}
        </p>
        <p className="text-sm">
          {data.category ? (
            <Link
              to={`/library/ingredient?category=${data.category.id}`}
              className="text-brand"
            >
              {data.category.display_name}
            </Link>
          ) : null}
          {data.parent ? (
            <>
              {' · a kind of '}
              <Link to={`/ingredient/${data.parent.id}`} className="text-brand">
                {data.parent.display_name}
              </Link>
            </>
          ) : null}
        </p>
        {data.labels.length ? (
          <div className="flex flex-wrap gap-1 pt-1">
            {data.labels.map((label) => (
              <Pill key={label.id}>{label.display_name}</Pill>
            ))}
          </div>
        ) : null}
      </header>

      {data.children.length ? (
        <Card className="space-y-1">
          <h2 className="text-sm font-semibold text-text-muted">Kinds of this</h2>
          <ul className="flex flex-wrap gap-2 text-sm">
            {data.children.map((child) => (
              <li key={child.id}>
                <Link to={`/ingredient/${child.id}`} className="text-brand">
                  {child.display_name}
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {data.preservation.length ? (
        <Card className="space-y-2">
          <h2 className="text-sm font-semibold text-text-muted">Keeping it</h2>
          <ul className="space-y-1 text-sm">
            {data.preservation.map((entry) => (
              <li key={entry.id} className="flex flex-wrap gap-2">
                <span className="font-medium">{entry.method}</span>
                {durationText(entry) ? (
                  <span className="text-text-muted">
                    {STATE_LABELS[entry.state] ? `${STATE_LABELS[entry.state]} ` : ''}
                    {durationText(entry)}
                  </span>
                ) : STATE_LABELS[entry.state] ? (
                  <span className="text-text-muted">{STATE_LABELS[entry.state]}</span>
                ) : null}
                {entry.notes ? <span>{entry.notes}</span> : null}
              </li>
            ))}
          </ul>
        </Card>
      ) : null}

      {hasNotes ? (
        <Card className="space-y-4">
          <Notes title="What it is" body={data.description} />
          <Notes title="Picking a good one" body={data.selection_notes} />
          <Notes title="Where to get it" body={data.sourcing_notes} />
          <Notes title="Keeping it — general" body={data.preservation_notes} />
        </Card>
      ) : (
        <Empty>Nothing written down yet.</Empty>
      )}

      {data.aliases.length ? (
        <p className="text-xs text-text-muted">Also found as: {data.aliases.join(', ')}</p>
      ) : null}

      <Link to={`/edit/ingredient/${data.id}`} className="inline-block text-sm text-brand">
        Edit this
      </Link>
    </article>
  )
}
