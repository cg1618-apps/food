import { useState } from 'react'

import { endpoints } from '../../api/endpoints'
import { Button, Card, Empty, ErrorNote, Input, Loading, Select } from '../../components/ui'
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import { flatten } from '../../lib/tree'

// Categories and labels on one page, as two sections. They are the same kind
// of work - maintaining a small vocabulary - and a page each would be two
// screens with four rows on them.
export default function Vocabularies() {
  return (
    <div className="space-y-8">
      <Categories />
      <Labels />
    </div>
  )
}

function Categories() {
  const tree = useApiQuery(endpoints.categories.tree())
  const create = useApiMutation({ method: 'POST', invalidate: [endpoints.categories.tree()] })
  const update = useApiMutation({ method: 'PATCH', invalidate: [endpoints.categories.tree()] })
  const remove = useApiMutation({ method: 'DELETE', invalidate: [endpoints.categories.tree()] })

  const [nameCn, setNameCn] = useState('')
  const [nameEn, setNameEn] = useState('')
  const [parentId, setParentId] = useState('')
  const [error, setError] = useState(null)

  const flat = flatten(tree.data ?? [])

  async function run(action) {
    setError(null)
    try {
      await action()
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <section className="space-y-3">
      <h1 className="text-xl font-semibold">Categories</h1>
      <p className="text-sm text-text-muted">
        Every ingredient is filed in exactly one. New ones start in the fallback category, which
        cannot be deleted or renamed away.
      </p>

      {error ? <ErrorNote error={error} /> : null}

      <Card className="grid gap-2 sm:grid-cols-4">
        <Input placeholder="中文名" value={nameCn} onChange={(e) => setNameCn(e.target.value)} />
        <Input placeholder="English" value={nameEn} onChange={(e) => setNameEn(e.target.value)} />
        <Select value={parentId} onChange={(e) => setParentId(e.target.value)}>
          <option value="">Top level</option>
          {flat.map((node) => (
            <option key={node.id} value={node.id}>
              {'— '.repeat(node.depth)}
              {node.display_name}
            </option>
          ))}
        </Select>
        <Button
          variant="primary"
          onClick={() =>
            run(async () => {
              await create.mutateAsync({
                url: endpoints.categories.create(),
                body: {
                  name_cn: nameCn || null,
                  name_en: nameEn || null,
                  parent_id: parentId ? Number(parentId) : null,
                },
              })
              setNameCn('')
              setNameEn('')
            })
          }
        >
          Add
        </Button>
      </Card>

      {tree.isPending ? <Loading /> : null}
      {flat.length === 0 && !tree.isPending ? <Empty>No categories yet.</Empty> : null}

      <ul className="space-y-1">
        {flat.map((node) => (
          <li key={node.id}>
            <Card className="flex flex-wrap items-center gap-2 py-2">
              <span style={{ paddingLeft: `${node.depth}rem` }} className="flex-1">
                {node.display_name}
                <span className="pl-2 text-xs text-text-muted">
                  {node.ingredient_count} filed here
                  {node.is_fallback ? ' · fallback' : ''}
                </span>
              </span>
              <Select
                className="w-auto"
                value={node.parent_id ?? ''}
                onChange={(e) =>
                  run(() =>
                    update.mutateAsync({
                      url: endpoints.categories.update(node.id),
                      body: { parent_id: e.target.value ? Number(e.target.value) : null },
                    }),
                  )
                }
              >
                <option value="">Top level</option>
                {flat
                  .filter((other) => other.id !== node.id)
                  .map((other) => (
                    <option key={other.id} value={other.id}>
                      {other.display_name}
                    </option>
                  ))}
              </Select>
              {/* The fallback row offers no delete at all. The server refuses
                  it anyway, but a button that always errors is worse than no
                  button. */}
              {node.is_fallback ? null : (
                <Button
                  variant="danger"
                  onClick={() =>
                    run(() => remove.mutateAsync({ url: endpoints.categories.remove(node.id) }))
                  }
                >
                  Delete
                </Button>
              )}
            </Card>
          </li>
        ))}
      </ul>
    </section>
  )
}

function Labels() {
  const labels = useApiQuery(endpoints.labels.list())
  const create = useApiMutation({ method: 'POST', invalidate: [endpoints.labels.list()] })
  const remove = useApiMutation({ method: 'DELETE', invalidate: [endpoints.labels.list()] })

  const [nameCn, setNameCn] = useState('')
  const [nameEn, setNameEn] = useState('')
  const [error, setError] = useState(null)

  async function run(action) {
    setError(null)
    try {
      await action()
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <section className="space-y-3">
      <h2 className="text-xl font-semibold">Labels</h2>
      <p className="text-sm text-text-muted">
        Cross-cutting tags. An ingredient may carry any number, or none. Deleting one removes it
        from everything tagged with it.
      </p>

      {error ? <ErrorNote error={error} /> : null}

      <Card className="grid gap-2 sm:grid-cols-3">
        <Input placeholder="中文名" value={nameCn} onChange={(e) => setNameCn(e.target.value)} />
        <Input placeholder="English" value={nameEn} onChange={(e) => setNameEn(e.target.value)} />
        <Button
          variant="primary"
          onClick={() =>
            run(async () => {
              await create.mutateAsync({
                url: endpoints.labels.create(),
                body: { name_cn: nameCn || null, name_en: nameEn || null },
              })
              setNameCn('')
              setNameEn('')
            })
          }
        >
          Add
        </Button>
      </Card>

      {labels.isPending ? <Loading /> : null}
      {labels.data?.length === 0 ? <Empty>No labels yet.</Empty> : null}

      <ul className="flex flex-wrap gap-2">
        {(labels.data ?? []).map((label) => (
          <li key={label.id}>
            <Card className="flex items-center gap-2 py-2">
              <span>{label.display_name}</span>
              <span className="text-xs text-text-muted">{label.ingredient_count}</span>
              <Button
                variant="danger"
                onClick={() =>
                  run(() => remove.mutateAsync({ url: endpoints.labels.remove(label.id) }))
                }
              >
                Delete
              </Button>
            </Card>
          </li>
        ))}
      </ul>
    </section>
  )
}
