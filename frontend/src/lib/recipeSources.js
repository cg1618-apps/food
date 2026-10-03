// Frontend: a recipe's sources, between the form and the API.
//
// A source on the wire names its author as `author_id` or `new_author` - a
// name the save reuses an existing author for, or creates (app/schemas/
// recipe.py, SourceIn). In the form a row holds an `author` instead, which is
// what the author box chose:
//
//   { type: 'author', id, label }
//   { type: 'new', label }        - 「新增」: an author made by the save
//
// as a line holds its target (lib/recipeLines.js). `pendingAuthor` is what is
// typed in the author box and not yet picked: never sent, but a row holding
// it is not blank, and saving over it is refused rather than dropping it.

import { newNames } from './recipeLines'
import { blankToNull, keyed } from './rowList'

/** A source as GET /api/recipes/{id} returns it (or nothing) -> a form row. */
export function sourceRow(entry = {}) {
  return keyed({
    // '' until chosen: shown and sent as the first platform in its place, so
    // a row added before the platforms load still lands on the first one.
    platform_id: entry.platform ? String(entry.platform.id) : '',
    author: entry.author ? { type: 'author', id: entry.author.id, label: entry.author.display_name } : null,
    pendingAuthor: '',
    url: entry.url ?? '',
    title: entry.title ?? '',
  })
}

/** An author-box option -> a row's author. */
export function authorFromOption(option) {
  return option.type === 'new' ? { type: 'new', label: option.label } : { type: 'author', id: option.id, label: option.label }
}

// Nothing typed - the platform always has a value - is an "add" pressed once
// too often, as a blank line or step is.
function isBlank(row) {
  return !row.author && !blankToNull(row.pendingAuthor) && !blankToNull(row.url) && !blankToNull(row.title)
}

/**
 * The form's sources -> the `sources` payload. `platformOf(row)` is the
 * platform id the row shows. A blank row is dropped; a row whose author was
 * typed and not picked is an error, named by its number.
 */
export function sourcesPayload(rows, platformOf) {
  const out = []
  rows.forEach((row, index) => {
    if (isBlank(row)) return
    const typed = blankToNull(row.pendingAuthor)
    if (!row.author && typed) {
      throw new Error(`第 ${index + 1} 個來源的作者打了「${typed}」，但還沒選：從清單選一位，或選「新增」。`)
    }
    const author =
      row.author?.type === 'new' ? { new_author: newNames(row.author.label) } : { author_id: row.author?.id ?? null }
    out.push({
      platform_id: Number(platformOf(row)),
      ...author,
      url: blankToNull(row.url),
      title: blankToNull(row.title),
    })
  })
  return out
}
