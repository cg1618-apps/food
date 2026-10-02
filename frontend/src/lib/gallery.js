// Frontend: an owner's gallery, between the picker and the API.
//
// The picker holds `[{ image_id, url, thumb_url, focus }]` in display order;
// position 0 is the cover. The API takes `[{ image_id, focus }]` in order on
// PUT .../{id}/images and replaces the whole gallery with it.

/** An owner's `images` (AttachedImage) -> the picker's value. */
export function galleryFromImages(images) {
  return (images ?? []).map((image) => ({
    image_id: image.image_id,
    url: image.url,
    thumb_url: image.thumb_url,
    focus: image.focus ?? null,
  }))
}

/** A library image (ImageSummary, as upload and the list answer) -> an item. */
export function galleryItem(image) {
  return { image_id: image.id, url: image.url, thumb_url: image.thumb_url, focus: null }
}

/**
 * Append library images, skipping any already in the gallery. One picture
 * twice in one gallery is never meant, and an upload whose checksum matches
 * an attached image answers that same image.
 */
export function addToGallery(items, images) {
  const held = new Set(items.map((item) => item.image_id))
  const added = []
  for (const image of images) {
    if (held.has(image.id)) continue
    held.add(image.id)
    added.push(galleryItem(image))
  }
  return [...items, ...added]
}

/** The PUT body. */
export function galleryPayload(items) {
  return items.map((item) => ({ image_id: item.image_id, focus: item.focus ?? null }))
}

/** Whether the gallery differs from what was loaded - order and focus count. */
export function galleryChanged(loaded, current) {
  return JSON.stringify(galleryPayload(loaded)) !== JSON.stringify(galleryPayload(current))
}
