// Frontend: what the typeahead offers, from what the server answered.
//
// The search itself is the list endpoints' `q`, which matches every name slot
// and every alias on the server (ingredients and recipes alike). This turns
// the two answers into one list of options: ingredients first, because a
// recipe line names an ingredient far more often than a base, each source
// capped so a common syllable cannot bury the other; then 「新增 'xxx'」 when
// it is allowed and nothing matches the typed text exactly.

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
// told apart - "醬油" the ingredient beside "醬油" the base recipe.
function secondary(row) {
  return [row.name_cn, row.name_en, row.name_alt]
    .filter((name) => name && name !== row.display_name)
    .join(' · ')
}

/**
 * The options for `query`.
 *
 *   ingredients, recipes  the server's answers (either may be absent)
 *   exclude               { ingredient: [ids], recipe: [ids] } never offered -
 *                         a recipe is not its own version, an ingredient not
 *                         merged into itself
 *   allowNew              offer 「新增」 when nothing matches exactly
 *   limit                 per source
 *
 * Each option: { key, type: 'ingredient' | 'recipe' | 'new', id, label,
 * detail, needsDetail, kind }. A 'new' option's `label` is the typed text.
 */
export function mergeResults({
  ingredients = [],
  recipes = [],
  query = '',
  exclude = {},
  allowNew = false,
  limit = 8,
}) {
  const skipIngredient = new Set(exclude.ingredient ?? [])
  const skipRecipe = new Set(exclude.recipe ?? [])

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
    ...(recipes ?? [])
      .filter((row) => !skipRecipe.has(row.id))
      .slice(0, limit)
      .map((row) => ({
        key: `recipe-${row.id}`,
        type: 'recipe',
        id: row.id,
        label: row.display_name,
        detail: secondary(row),
        kind: row.kind,
        exact: isExactMatch(row, query),
      })),
  ]

  const typed = String(query ?? '').trim()
  // An exact match anywhere - ingredient or recipe - is what the user meant,
  // so 「新增」 would only make a duplicate the server then folds into it.
  if (allowNew && typed && !options.some((option) => option.exact)) {
    options.push({ key: `new-${typed}`, type: 'new', id: null, label: typed, detail: '' })
  }
  return options
}

/** The next active index for an arrow key: wraps, and -1 means none. */
export function stepActive(current, delta, count) {
  if (count === 0) return -1
  if (current < 0) return delta > 0 ? 0 : count - 1
  return (current + delta + count) % count
}
