// Frontend: a detail page's pictures - one large, the rest as a strip.
//
// The first image of an owner's gallery is its cover (GalleryPicker marks it
// 封面), so it is the one shown large when the page opens. A thumbnail swaps
// it in place; nothing navigates. Every image is cropped at its focal point,
// the large one included, so a subject set off-centre in the picker stays in
// frame here too. No images, no block: the page does not draw an empty frame.
import { useState } from 'react'

import { cx } from '../../lib/cx'
import { focusStyle } from '../../lib/images'

export default function Gallery({ images, title, className }) {
  const [chosen, setChosen] = useState(0)
  if (!images?.length) return null
  const index = chosen < images.length ? chosen : 0
  const shown = images[index]

  return (
    <div className={cx('space-y-2', className)}>
      <a
        href={shown.url}
        target="_blank"
        rel="noreferrer"
        className="block aspect-[4/3] overflow-hidden rounded-lg border border-border bg-surface-2"
        title="開啟原圖"
      >
        <img
          src={shown.url}
          alt={title}
          loading="lazy"
          className="h-full w-full object-cover"
          style={focusStyle(shown.focus)}
        />
      </a>
      {images.length > 1 ? (
        <ul className="flex gap-2 overflow-x-auto pb-1" aria-label="其他圖片">
          {images.map((image, i) => (
            <li key={image.image_id} className="shrink-0">
              <button
                type="button"
                onClick={() => setChosen(i)}
                aria-pressed={i === index}
                aria-label={`第 ${i + 1} 張`}
                className={cx(
                  'block h-16 w-16 overflow-hidden rounded-md border-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand',
                  i === index ? 'border-brand' : 'border-transparent hover:border-border-strong',
                )}
              >
                <img
                  src={image.thumb_url}
                  alt=""
                  loading="lazy"
                  className="h-full w-full object-cover"
                  style={focusStyle(image.focus)}
                />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
