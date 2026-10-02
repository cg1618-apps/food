// Frontend: what the image library says about a picture - where each owner
// lives and what kind of thing it is, and how big the file is.
//
// The owner types are the backend's (app/services/images.py OWNER_TABLES):
// `ingredient`, `recipe`, `kitchen_note`.

const OWNERS = {
  ingredient: { kind: '食材', path: '/ingredients' },
  recipe: { kind: '食譜', path: '/recipes' },
  kitchen_note: { kind: '筆記', path: '/notes' },
}

/** The detail page of an image's owner. */
export function ownerHref({ type, id }) {
  const owner = OWNERS[type]
  return owner ? `${owner.path}/${id}` : null
}

/** 食材, 食譜 or 筆記 - or the raw type for one this file does not know. */
export function ownerKind(type) {
  return OWNERS[type]?.kind ?? type
}

/** A file size in the unit that reads best: "820 B", "14.2 KB", "1.3 MB". */
export function formatBytes(n) {
  if (n == null) return null
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / (1024 * 1024)).toFixed(1)} MB`
}
