// Frontend: how a new recipe starts, read from and written to its URL.
//
// /edit/recipes/new asks first: 空白, 從範本 or 複製另一份食譜
// (pages/edit/NewRecipeChooser.jsx). The answer is put in the query string -
// ?blank=1, ?template=<id> or ?from=<recipe id> - so the form it opens can be
// reloaded, bookmarked and gone Back from to the question. ?dish=<id>, the
// dish page's 「＋ 新增食譜」, rides along with whichever is chosen.

const ID = /^\d+$/

const idParam = (params, name) => (ID.test(params.get(name) ?? '') ? params.get(name) : null)

/**
 * What the URL says about a new recipe:
 *   dish      the preset dish's id, or null
 *   template  the template to start from, or null
 *   from      the recipe to copy, or null
 *   chosen    whether a start was chosen at all - false shows the chooser
 */
export function newRecipeStart(params) {
  const template = idParam(params, 'template')
  const from = idParam(params, 'from')
  const blank = Boolean(params.get('blank'))
  return { dish: idParam(params, 'dish'), template, from, chosen: blank || template !== null || from !== null }
}

/** The query string for a choice - { blank: true }, { template: id } or
 * { from: id } - keeping the preset dish and nothing else. */
export function chosenSearch(params, choice) {
  const next = new URLSearchParams()
  const dish = idParam(params, 'dish')
  if (dish) next.set('dish', dish)
  if (choice.template !== undefined) next.set('template', String(choice.template))
  else if (choice.from !== undefined) next.set('from', String(choice.from))
  else next.set('blank', '1')
  return `?${next}`
}
