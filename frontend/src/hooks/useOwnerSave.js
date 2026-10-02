// Frontend: save a recipe, an ingredient or a note, gallery included.
//
// The row and its gallery are two requests - POST/PATCH the row, then PUT
// `[{image_id, focus}]` to `.../{id}/images` - because the gallery endpoint is
// shared by all three owners and replaces wholesale. A NEW owner has no id
// until the first request answers, so its gallery can only go second.
//
// If the row saved and the gallery did not, the row exists: the id is kept,
// so pressing Save again PATCHes that row rather than creating a second one,
// and the error says the row is saved and the pictures are not.
import { useState } from 'react'

import { galleryPayload } from '../lib/gallery'
import { useApiMutation } from './useApi'

/**
 * `group` is the resource's entry in api/endpoints.js (create, update,
 * images); `invalidate` the read prefixes the save makes stale.
 *
 * `save({ id, body, gallery, galleryDirty })` resolves to the saved row.
 * `id` is the route's id, or undefined for a new row.
 */
export function useOwnerSave({ group, invalidate }) {
  const create = useApiMutation({ method: 'POST', invalidate })
  const update = useApiMutation({ method: 'PATCH', invalidate })
  const images = useApiMutation({ method: 'PUT', invalidate })
  const [createdId, setCreatedId] = useState(null)

  async function save({ id, body, gallery = [], galleryDirty = false }) {
    const ownerId = id ?? createdId
    let saved
    if (ownerId === null || ownerId === undefined) {
      saved = await create.mutateAsync({ url: group.create(), body })
      setCreatedId(saved.id)
    } else {
      saved = await update.mutateAsync({ url: group.update(ownerId), body })
    }

    const firstSave = ownerId === null || ownerId === undefined
    if (firstSave ? gallery.length > 0 : galleryDirty) {
      try {
        saved = await images.mutateAsync({ url: group.images(saved.id), body: galleryPayload(gallery) })
      } catch (error) {
        error.message = `內容已儲存，但圖片沒有存上：${error.message}`
        throw error
      }
    }
    return saved
  }

  return {
    save,
    saving: create.isPending || update.isPending || images.isPending,
  }
}
