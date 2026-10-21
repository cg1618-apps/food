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
//
// A line's `alternatives` (或 on the page) are rows of the same shape -
// `{ target, pending, amount, note }` - each naming what may stand in for the
// line's target, with the same four kinds of target and the same rules for a
// blank or an unpicked one. They have no 可省略 and no group of their own.

import { blankToNull, keyed } from './rowList'

// The dish kinds (app/constants.py DISH_KINDS). A dish typed into a line is a
// sauce unless the form says otherwise; one typed as a recipe's own dish is
// a 料理.
export const DISH = 'dish'
export const SAUCE = 'sauce'

// Which group a line is in is where it sits in the form's grouped list
// (lib/groupedRows.js), not a field of the line.

export function emptyAlternative() {
  return keyed({ target: null, pending: '', amount: '', note: '' })
}

export function emptyLine() {
  return keyed({ target: null, pending: '', amount: '', note: '', is_optional: false, alternatives: [] })
}

/** The target a saved line or alternative names, from its response. */
function targetFromResponse(row) {
  if (row.ingredient) {
    return {
      type: 'ingredient',
      id: row.ingredient.id,
      label: row.ingredient.display_name,
      needsDetail: row.ingredient.needs_detail,
    }
  }
  if (row.sub_dish) {
    return { type: 'dish', id: row.sub_dish.id, label: row.sub_dish.display_name, kind: row.sub_dish.kind }
  }
  return null
}

/** An alternative as a response carries it -> a form row. */
function alternativeFromResponse(alternative) {
  return keyed({
    target: targetFromResponse(alternative),
    pending: '',
    amount: alternative.amount ?? '',
    note: alternative.note ?? '',
  })
}

/** A line as GET /api/recipes/{id} returns it -> a form row, its
 * alternatives included. */
export function lineFromResponse(line) {
  return keyed({
    target: targetFromResponse(line),
    pending: '',
    amount: line.amount ?? '',
    note: line.note ?? '',
    is_optional: Boolean(line.is_optional),
    alternatives: (line.alternatives ?? []).map(alternativeFromResponse),
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

function isBlank(row) {
  return !row.target && !blankToNull(row.pending) && !blankToNull(row.amount) && !blankToNull(row.note)
}

/** A row's target -> the one field naming it on the wire. */
function targetPayload({ type, id, label, kind }) {
  if (type === 'ingredient') return { ingredient_id: id }
  if (type === 'dish') return { sub_dish_id: id }
  if (type === 'new-dish') return { new_dish: { ...newNames(label), kind: kind ?? SAUCE } }
  return { new_ingredient: newNames(label) }
}

/** The error for a row with something typed but nothing chosen. `what` names
 * it: 第 3 行材料, or 第 3 行材料的替代 1. */
function unpicked(row, what) {
  const typed = blankToNull(row.pending)
  return new Error(
    typed
      ? `${what}打了「${typed}」，但還沒選食材或料理：從清單選一個，或選「新增」。`
      : `${what}還沒選食材或料理。`,
  )
}

function alternativesPayload(alternatives, number) {
  const out = []
  ;(alternatives ?? []).forEach((alternative, index) => {
    if (isBlank(alternative)) return
    if (!alternative.target) throw unpicked(alternative, `第 ${number} 行材料的替代 ${index + 1} `)
    out.push({
      amount: blankToNull(alternative.amount),
      note: blankToNull(alternative.note),
      ...targetPayload(alternative.target),
    })
  })
  return out
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
    const number = start + index + 1
    const alternatives = alternativesPayload(line.alternatives, number)
    if (isBlank(line) && !alternatives.length) return
    if (!line.target) throw unpicked(line, `第 ${number} 行材料`)
    out.push({
      amount: blankToNull(line.amount),
      note: blankToNull(line.note),
      is_optional: Boolean(line.is_optional),
      ...targetPayload(line.target),
      alternatives,
    })
  })
  return out
}

/** Whether a target is still only a name: a saved stub, or one this save makes. */
export function isStub(target) {
  return Boolean(target && (target.type === 'new' || target.needsDetail))
}
