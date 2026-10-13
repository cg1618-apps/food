// Frontend: an author's remark (備註) and links, as 設定 edits them.
//
// The other vocabularies are two names; an author is also a remark and a
// list of links (a label - YouTube, IG, 部落格 - and a url each). 設定's row
// opens all of it at once: `authorDraft` is what the row starts from, beside
// the two names, and `authorBody` is the PATCH. The links are sent whole and
// replace what was stored, in the order shown - the server's rule, as on TBD.
//
// A link row left wholly empty is dropped rather than sent; one with only a
// label is sent, so the server's "needs a link" answers it rather than the
// label vanishing on save. The remark keeps its line breaks; a blank one is
// null, which clears it.
import { blankToNull, keyed } from './rowList'

/** The draft fields an author's row adds to its two names. */
export function authorDraft(author) {
  return {
    notes: author.notes ?? '',
    links: (author.links ?? []).map((link) => keyed({ label: link.label ?? '', url: link.url })),
  }
}

/** The draft as the PATCH body: the names as typed, the remark, the links. */
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
