// Frontend: a recipe's ingredient lines, between the form and the API.
//
// A line on the wire names exactly one of `ingredient_id`, `sub_recipe_id` or
// `new_ingredient` - there is no type field, and the server refuses one
// (app/schemas/recipe.py, LineIn). In the form a line holds a `target`
// instead, which is what the typeahead chose:
//
//   { type: 'ingredient', id, label, needsDetail }
//   { type: 'recipe', id, label, kind }
//   { type: 'new', label }        - 「新增」: a stub made by the save
//
// so the form can show the choice (with 待補 for a stub, saved or not) and
// the payload is derived from it in one place. `pending` is what is typed in
// the line's search box and not yet picked (Typeahead's onQueryChange): never
// sent, but a line holding it is not blank.

import { blankToNull, keyed } from './rowList'

export function emptyLine(section = '') {
  return keyed({ target: null, pending: '', section, amount: '', note: '', is_optional: false })
}

/** A line as GET /api/recipes/{id} returns it -> a form row. */
export function lineFromResponse(line) {
  let target = null
  if (line.ingredient) {
    target = {
      type: 'ingredient',
      id: line.ingredient.id,
      label: line.ingredient.display_name,
      needsDetail: line.ingredient.needs_detail,
    }
  } else if (line.sub_recipe) {
    target = {
      type: 'recipe',
      id: line.sub_recipe.id,
      label: line.sub_recipe.display_name,
      kind: line.sub_recipe.kind,
    }
  }
  return keyed({
    target,
    pending: '',
    section: line.section ?? '',
    amount: line.amount ?? '',
    note: line.note ?? '',
    is_optional: Boolean(line.is_optional),
  })
}

/** A typeahead option -> a line target. */
export function targetFromOption(option) {
  if (option.type === 'new') return { type: 'new', label: option.label }
  if (option.type === 'recipe') {
    return { type: 'recipe', id: option.id, label: option.label, kind: option.kind }
  }
  return { type: 'ingredient', id: option.id, label: option.label, needsDetail: option.needsDetail }
}

// Han characters, kana and Hangul: a name typed in any of them is filed as
// the Chinese name, anything else as the English one. A stub needs one name
// and the user typed exactly one.
const CJK = /[぀-ヿ㐀-鿿豈-﫿가-힯]/

/** The `new_ingredient` body for a typed name. */
export function newIngredientNames(text) {
  const name = String(text ?? '').trim()
  return CJK.test(name) ? { name_cn: name } : { name_en: name }
}

function isBlank(line) {
  return !line.target && !blankToNull(line.pending) && !blankToNull(line.amount) && !blankToNull(line.note)
}

/**
 * The form's lines -> the `lines` payload. A line left entirely blank is
 * dropped (an "add" pressed once too often); a line with an amount, a note or
 * a typed name but nothing chosen is an error, named by its number, rather
 * than something silently thrown away.
 */
export function linesPayload(rows) {
  const out = []
  rows.forEach((line, index) => {
    if (isBlank(line)) return
    if (!line.target) {
      const typed = blankToNull(line.pending)
      throw new Error(
        typed
          ? `第 ${index + 1} 行材料打了「${typed}」，但還沒選食材或食譜：從清單選一個，或選「新增」。`
          : `第 ${index + 1} 行材料還沒選食材或食譜。`,
      )
    }
    const base = {
      section: blankToNull(line.section),
      amount: blankToNull(line.amount),
      note: blankToNull(line.note),
      is_optional: Boolean(line.is_optional),
    }
    if (line.target.type === 'ingredient') out.push({ ...base, ingredient_id: line.target.id })
    else if (line.target.type === 'recipe') out.push({ ...base, sub_recipe_id: line.target.id })
    else out.push({ ...base, new_ingredient: newIngredientNames(line.target.label) })
  })
  return out
}

/** The distinct non-blank sections of some rows, in first-use order. */
export function sectionsOf(...lists) {
  const seen = new Set()
  for (const rows of lists) {
    for (const row of rows ?? []) {
      const section = blankToNull(row.section)
      if (section) seen.add(section)
    }
  }
  return [...seen]
}

/** Whether a target is still only a name: a saved stub, or one this save makes. */
export function isStub(target) {
  return Boolean(target && (target.type === 'new' || target.needsDetail))
}
