// Frontend: where a keyboard move lands on a SortableBoard
// (components/ui/Sortable.jsx) - rows in several containers, one after
// another. Pure, so it is tested here rather than through a drag jsdom
// cannot do.
//
// A place is { container, index }; containers is [{ id, items }] in display
// order, items being the row ids.

/**
 * Where a row lands one place up (`delta` -1) or down (+1) from `from`, a
 * `{ container, index }` in `containers` (`[{ id, items }]`, display order):
 * inside its own container, or across the edge into the neighbour - the end
 * of the one above, the start of the one below. Null off the very top or
 * bottom.
 */
export function neighbourPlace(containers, from, delta) {
  const at = containers.findIndex((c) => c.id === from.container)
  if (at < 0) return null
  const index = from.index + delta
  if (index >= 0 && index < containers[at].items.length) return { container: from.container, index }
  const next = containers[at + (delta < 0 ? -1 : 1)]
  if (!next) return null
  return { container: next.id, index: delta < 0 ? next.items.length : 0 }
}

/** Where `id` is: `{ container, index }`, or null. */
export function placeOf(containers, id) {
  for (const c of containers) {
    const index = c.items.indexOf(id)
    if (index >= 0) return { container: c.id, index }
  }
  return null
}
