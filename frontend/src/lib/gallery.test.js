// The gallery's value and its PUT body.
import { describe, expect, it } from 'vitest'

import { addToGallery, galleryChanged, galleryFromImages, galleryPayload } from './gallery'

describe('gallery', () => {
  const attached = [
    { image_id: 1, url: '/images/a.jpg', thumb_url: '/images/ta.jpg', width: 1, height: 1, focus: '20% 30%' },
  ]

  it('round-trips an owner images list to the PUT body in order', () => {
    const items = addToGallery(galleryFromImages(attached), [{ id: 2, url: '/b', thumb_url: '/tb' }])
    expect(galleryPayload(items)).toEqual([
      { image_id: 1, focus: '20% 30%' },
      { image_id: 2, focus: null },
    ])
  })

  it('does not add an image the gallery already holds', () => {
    const items = galleryFromImages(attached)
    expect(addToGallery(items, [{ id: 1, url: '/a', thumb_url: '/ta' }])).toHaveLength(1)
  })

  it('counts a reorder or a focus change as a change', () => {
    const a = [
      { image_id: 1, focus: null },
      { image_id: 2, focus: null },
    ]
    expect(galleryChanged(a, [...a])).toBe(false)
    expect(galleryChanged(a, [a[1], a[0]])).toBe(true)
    expect(galleryChanged(a, [{ ...a[0], focus: '1% 1%' }, a[1]])).toBe(true)
  })
})
