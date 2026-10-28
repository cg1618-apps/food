// Frontend: an author as its form edits it, and as its library searches it.
//
// The other vocabularies are two names; an author is also a remark (備註)
// and a list of links (a label - YouTube, IG, 部落格 - and a url each), edited
// together on the author's form (pages/edit/AuthorForm.jsx). `authorDraft`
// is what the form starts from, beside the two names, and `authorBody` is the
// POST or PATCH. The links are sent whole and replace what was stored, in the
// order shown - the server's rule, as on TBD. The gallery is not in the body:
// it is its own PUT, as on every owner (hooks/useOwnerSave.js).
//
// A link row left wholly empty is dropped rather than sent; one with only a
// label is sent, so the server's "needs a link" answers it rather than the
// label vanishing on save. The remark keeps its line breaks; a blank one is
// null, which clears it.
import { blankToNull, keyed } from './rowList'

/** The draft fields an author's form adds to its two names. */
export function authorDraft(author) {
  return {
    notes: author.notes ?? '',
    links: (author.links ?? []).map((link) => keyed({ label: link.label ?? '', url: link.url })),
  }
}

/** The draft as the request body: the names as typed, the remark, the links. */
export function authorBody({ name_cn, name_en, notes, links }) {
  return {
    name_cn,
    name_en,
    notes: String(notes ?? '').trim() ? String(notes).trim() : null,
    links: links
      .filter((row) => blankToNull(row.url) || blankToNull(row.label))
      .map((row) => ({ url: String(row.url ?? '').trim(), label: blankToNull(row.label) })),
  }
}

/**
 * Whether an author answers to the library's search term - either name,
 * ignoring case. The author list is read whole (every author, never paged),
 * so the library filters it here rather than asking the server again.
 */
export function matchesAuthor(author, term) {
  const needle = String(term ?? '').trim().toLowerCase()
  if (!needle) return true
  return [author.name_cn, author.name_en, author.display_name].some((name) =>
    String(name ?? '').toLowerCase().includes(needle),
  )
}
