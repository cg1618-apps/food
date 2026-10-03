// Frontend: the arithmetic behind 設定's editors - reordering by sort_order,
// where a new value goes, and what a refused delete says.
//
// Pure, so the cases that are easy to get wrong (ties in sort_order, a move
// off either end, a drop several places away) are tested here rather than by
// clicking.

/**
 * The PATCHes that move `rows[from]` to position `to` - where a drag dropped
 * it, or one place along for an arrow key.
 *
 * `rows` are siblings in the order the API listed them, by sort_order then
 * name. When every sort_order among them is distinct, the rows keep the same
 * set of numbers, handed out again in the new order: a one-place move is a
 * swap of two values, and moving a row and then back restores exactly the
 * numbers it started with. When any two tie - the seed gives everything 0,
 * and a tie is ordered by name, which no reassignment of equal values can
 * change - the whole list is renumbered 1..n in its new order. Either way,
 * only the rows whose number actually changes are sent.
 *
 * Answers [] for a move off either end, or onto itself.
 */
export function reorderPatches(rows, from, to) {
  if (from === to || from < 0 || from >= rows.length || to < 0 || to >= rows.length) return []

  const moved = [...rows]
  const [row] = moved.splice(from, 1)
  moved.splice(to, 0, row)

  const orders = rows.map((each) => each.sort_order)
  const numbers =
    new Set(orders).size === orders.length
      ? [...orders].sort((a, b) => a - b)
      : moved.map((_, position) => position + 1)

  return moved
    .map((each, position) => ({ id: each.id, sort_order: numbers[position] }))
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
