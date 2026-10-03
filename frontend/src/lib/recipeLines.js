// Frontend: a recipe's ingredient lines, between the form and the API.
//
// A line on the wire names exactly one of `ingredient_id`, `sub_dish_id`,
// `new_ingredient` or `new_dish` - there is no type field, and the server
// refuses one (app/schemas/recipe.py, LineIn). A line names a DISH - usually
// a 醬料 - never one recipe of it. In the form a line holds a `target`
// instead, which is what the typeahead chose:
//
//   { type: 'ingredient', id, label, needsDetail }
//   { type: 'dish', id, label, kind }
//   { type: 'new', label }        - 「新增」: a stub ingredient made by the save
//   { type: 'new-dish', label, kind } - 「新增料理」: a dish made by the save,
//                                   a 醬料 unless told
//
// so the form can show the choice (with 待補 for a stub, saved or not) and
// the payload is derived from it in one place. `pending` is what is typed in
// the line's search box and not yet picked (Typeahead's onQueryChange): never
// sent, but a line holding it is not blank.

import { blankToNull, keyed } from './rowList'

// The dish kinds (app/constants.py DISH_KINDS). A dish typed into a line is a
// sauce unless the form says otherwise; one typed as a recipe's own dish is
// a 料理.
export const DISH = 'dish'
export const SAUCE = 'sauce'

// Which group a line is in is where it sits in the form's grouped list
// (lib/groupedRows.js), not a field of the line.

export function emptyLine() {
  return keyed({ target: null, pending: '', amount: '', note: '', is_optional: false })
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
  } else if (line.sub_dish) {
    target = {
      type: 'dish',
      id: line.sub_dish.id,
      label: line.sub_dish.display_name,
      kind: line.sub_dish.kind,
    }
  }
  return keyed({
    target,
    pending: '',
    amount: line.amount ?? '',
    note: line.note ?? '',
    is_optional: Boolean(line.is_optional),
  })
}

/** A typeahead option -> a line target. */
export function targetFromOption(option) {
  if (option.type === 'new') return { type: 'new', label: option.label }
  if (option.type === 'new-dish') return { type: 'new-dish', label: option.label, kind: SAUCE }
  if (option.type === 'dish') {
    return { type: 'dish', id: option.id, label: option.label, kind: option.kind }
  }
  return { type: 'ingredient', id: option.id, label: option.label, needsDetail: option.needsDetail }
}

// Han characters, kana and Hangul: a name typed in any of them is filed as
// the Chinese name, anything else as the English one. A stub needs one name
// and the user typed exactly one. The author migration (alembic/versions/
// a1uthors_authors.py) files existing creators by the same rule.
const CJK = /[぀-ヿ㐀-鿿豈-﫿가-힯]/

/** The `new_ingredient`, `new_author` or `new_dish` names for a typed name. */
export function newNames(text) {
  const name = String(text ?? '').trim()
  return CJK.test(name) ? { name_cn: name } : { name_en: name }
}

function isBlank(line) {
  return !line.target && !blankToNull(line.pending) && !blankToNull(line.amount) && !blankToNull(line.note)
}

/**
 * Some of the form's lines -> their payload. A line left entirely blank is
 * dropped (an "add" pressed once too often); a line with an amount, a note or
 * a typed name but nothing chosen is an error, named by its number, rather
 * than something silently thrown away. `start` is how many lines the form
 * shows before these - lines are numbered through every group.
 */
export function linesPayload(rows, start = 0) {
  const out = []
  rows.forEach((line, index) => {
    if (isBlank(line)) return
    if (!line.target) {
      const typed = blankToNull(line.pending)
      const number = start + index + 1
      throw new Error(
        typed
          ? `第 ${number} 行材料打了「${typed}」，但還沒選食材或料理：從清單選一個，或選「新增」。`
          : `第 ${number} 行材料還沒選食材或料理。`,
      )
    }
    const base = {
      amount: blankToNull(line.amount),
      note: blankToNull(line.note),
      is_optional: Boolean(line.is_optional),
    }
    const { type, id, label, kind } = line.target
    if (type === 'ingredient') out.push({ ...base, ingredient_id: id })
    else if (type === 'dish') out.push({ ...base, sub_dish_id: id })
    else if (type === 'new-dish') out.push({ ...base, new_dish: { ...newNames(label), kind: kind ?? SAUCE } })
    else out.push({ ...base, new_ingredient: newNames(label) })
  })
  return out
}

/** Whether a target is still only a name: a saved stub, or one this save makes. */
export function isStub(target) {
  return Boolean(target && (target.type === 'new' || target.needsDetail))
}
