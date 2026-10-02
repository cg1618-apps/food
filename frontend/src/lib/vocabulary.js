// Frontend: the arithmetic behind 設定's editors - reordering by sort_order,
// where a new value goes, and what a refused delete says.
//
// Pure, so the cases that are easy to get wrong (ties in sort_order, a move
// off either end) are tested here rather than by clicking.

/**
 * The PATCHes that move `rows[index]` one place up (`delta` -1) or down (+1).
 *
 * `rows` are siblings in the order the API listed them, by sort_order then
 * name. When every sort_order among them is distinct, the two rows swap
 * values: one PATCH each, and moving a row up and back down restores exactly
 * the numbers it started with. When any two tie - the seed gives everything
 * 0, and a tie is ordered by name, which a swap cannot change - the whole
 * list is renumbered 1..n in its new order, and only the rows whose number
 * actually changes are sent.
 *
 * Answers [] for a move off either end.
 */
export function reorderPatches(rows, index, delta) {
  const target = index + delta
  if (index < 0 || index >= rows.length || target < 0 || target >= rows.length) return []

  const orders = rows.map((row) => row.sort_order)
  if (new Set(orders).size === orders.length) {
    return [
      { id: rows[index].id, sort_order: rows[target].sort_order },
      { id: rows[target].id, sort_order: rows[index].sort_order },
    ]
  }

  const moved = [...rows]
  const [row] = moved.splice(index, 1)
  moved.splice(target, 0, row)
  return moved
    .map((each, position) => ({ id: each.id, sort_order: position + 1 }))
    .filter(({ id, sort_order }) => rows.find((each) => each.id === id).sort_order !== sort_order)
}

/** The sort_order that puts a new value after every one of `rows`. */
export function nextSortOrder(rows) {
  if (!rows?.length) return 0
  return Math.max(...rows.map((row) => row.sort_order ?? 0)) + 1
}

/**
 * Why a category cannot be deleted, in words, or null when nothing stops it.
 * Both relationships are RESTRICT, so this is said before the delete is sent
 * and the server's 409 is the backstop.
 */
export function categoryBlockers(node) {
  const parts = []
  if (node.ingredient_count) parts.push(`${node.ingredient_count} 種食材`)
  if (node.children?.length) parts.push(`${node.children.length} 個子分類`)
  if (!parts.length) return null
  return `「${node.display_name}」底下還有 ${parts.join('、')}，先移走再刪。`
}

/**
 * The inline explanation for a refused vocabulary delete. The 409 body
 * carries `usage_count`; the number on screen may be older than the server's,
 * so the server's wins.
 */
export function inUseMessage(name, error) {
  const count = error?.body?.usage_count
  if (error?.status === 409 && count) {
    return `「${name}」還用在 ${count} 個地方，先改掉那些再刪。`
  }
  return error?.message || '刪除失敗。'
}
