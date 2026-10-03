// Frontend: what the typeahead offers, from what the server answered.
//
// The search itself is the list endpoints' `q`, which matches every name slot
// and every alias on the server (ingredients and dishes alike). This turns
// the two answers into one list of options: ingredients first, because a
// recipe line names an ingredient far more often than a sauce, each source
// capped so a common syllable cannot bury the other; then 「新增 'xxx'」 when
// it is allowed and nothing matches the typed text exactly - a new ingredient,
// a new dish, or one of each when the caller allows both.
//
// A short list the caller already holds - the authors - is filtered here in
// the browser instead (localResults), with the same 「新增」 rule.

/** Case- and width-insensitive comparison text: trimmed, lowercased. */
export function normalise(text) {
  return String(text ?? '')
    .normalize('NFKC')
    .trim()
    .toLowerCase()
}

function names(row) {
  return [row.display_name, row.name_cn, row.name_en, row.name_alt].filter(Boolean)
}

/** Whether `row` answers to `query` by one of its names, exactly. */
export function isExactMatch(row, query) {
  const wanted = normalise(query)
  return wanted !== '' && names(row).some((name) => normalise(name) === wanted)
}

// The names under the display name, so two rows that display alike can be
// told apart - "醬油" the ingredient beside "醬油" the sauce.
function secondary(row) {
  return [row.name_cn, row.name_en, row.name_alt]
    .filter((name) => name && name !== row.display_name)
    .join(' · ')
}

/**
 * The options for `query`.
 *
 *   ingredients, dishes, recipes  the server's answers (any may be absent);
 *                        a recipe is offered by its display name, its dish's
 *                        beside it when the two differ
 *   exclude              { ingredient: [ids], dish: [ids] } never offered -
 *                        a recipe's own dish on its lines, an ingredient not
 *                        merged into itself
 *   allowNew             offer 「新增」 when nothing matches exactly
 *   allowNewDish         offer 「新增 料理」 as well (type 'new-dish')
 *   limit                per source
 *
 * Each option: { key, type: 'ingredient' | 'dish' | 'recipe' | 'new' | 'new-dish', id,
 * label, detail, needsDetail, kind }. A new option's `label` is the typed
 * text.
 */
export function mergeResults({
  ingredients = [],
  dishes = [],
  recipes = [],
  query = '',
  exclude = {},
  allowNew = false,
  allowNewDish = false,
  limit = 8,
}) {
  const skipIngredient = new Set(exclude.ingredient ?? [])
  const skipDish = new Set(exclude.dish ?? [])

  const options = [
    ...(ingredients ?? [])
      .filter((row) => !skipIngredient.has(row.id))
      .slice(0, limit)
      .map((row) => ({
        key: `ingredient-${row.id}`,
        type: 'ingredient',
        id: row.id,
        label: row.display_name,
        detail: secondary(row),
        needsDetail: Boolean(row.needs_detail),
        exact: isExactMatch(row, query),
      })),
    ...(dishes ?? [])
      .filter((row) => !skipDish.has(row.id))
      .slice(0, limit)
      .map((row) => ({
        key: `dish-${row.id}`,
        type: 'dish',
        id: row.id,
        label: row.display_name,
        detail: secondary(row),
        kind: row.kind,
        exact: isExactMatch(row, query),
      })),
    ...(recipes ?? []).slice(0, limit).map((row) => ({
      key: `recipe-${row.id}`,
      type: 'recipe',
      id: row.id,
      label: row.display_name,
      detail: row.dish && row.dish.display_name !== row.display_name ? row.dish.display_name : '',
      exact: isExactMatch(row, query),
    })),
  ]

  return withNew(options, query, allowNew, allowNewDish)
}

// An exact match anywhere is what the user meant, so 「新增」 would only make
// a duplicate the server then folds into it.
function withNew(options, query, allowNew, allowNewDish = false) {
  const typed = String(query ?? '').trim()
  if (typed && !options.some((option) => option.exact)) {
    if (allowNew) options.push({ key: `new-${typed}`, type: 'new', id: null, label: typed, detail: '' })
    if (allowNewDish) {
      options.push({ key: `new-dish-${typed}`, type: 'new-dish', id: null, label: typed, detail: '' })
    }
  }
  return options
}

/**
 * The options for `query` from a list held in the browser: every row one of
 * whose names contains the typed text, case- and width-insensitively, in the
 * list's own order. Each option is { key, type: 'item', id, label, detail },
 * then 「新增」 as mergeResults adds it.
 */
export function localResults({ items = [], query = '', allowNew = false, limit = 8 }) {
  const wanted = normalise(query)
  const options = (items ?? [])
    .filter((row) => wanted !== '' && names(row).some((name) => normalise(name).includes(wanted)))
    .slice(0, limit)
    .map((row) => ({
      key: `item-${row.id}`,
      type: 'item',
      id: row.id,
      label: row.display_name,
      detail: secondary(row),
      exact: isExactMatch(row, query),
    }))
  return withNew(options, query, allowNew)
}

/** The next active index for an arrow key: wraps, and -1 means none. */
export function stepActive(current, delta, count) {
  if (count === 0) return -1
  if (current < 0) return delta > 0 ? 0 : count - 1
  return (current + delta + count) % count
}
