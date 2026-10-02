// Frontend: a library's 封面 view - a grid of covers.
//
// Each tile is a link to the item: the cover image (cropped, at its focal
// point) or a placeholder, the name in the serif, one line of metadata, and
// the badges. The page says what goes in each slot through `card(item)`,
// which returns { cover, title, subtitle?, meta?, badges? }; the grid owns the
// shape, so the three libraries cannot drift apart.
import { Link } from 'react-router-dom'

import { focusStyle } from '../../lib/images'

// No photograph yet: the name's first character, set large in the serif, the
// way a notebook page would be headed. Better than a broken-image icon, and it
// keeps a grid of mostly unphotographed ingredients readable.
function CoverPlaceholder({ title }) {
  return (
    <div
      aria-hidden="true"
      className="flex h-full w-full items-center justify-center bg-surface-2 font-display text-4xl text-text-faint"
    >
      {Array.from(title || '·')[0]}
    </div>
  )
}

export function CoverImage({ cover, title }) {
  if (!cover?.thumb_url) return <CoverPlaceholder title={title} />
  return (
    <img
      src={cover.thumb_url}
      alt=""
      loading="lazy"
      className="h-full w-full object-cover"
      style={focusStyle(cover.focus)}
    />
  )
}

export default function CoverGrid({ items, itemTo, card }) {
  return (
    <ul className="grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3 xl:grid-cols-4">
      {items.map((item) => {
        const { cover, title, subtitle, meta, badges } = card(item)
        return (
          <li key={item.id}>
            <Link to={itemTo(item)} className="group block space-y-1.5">
              <div className="aspect-[4/3] overflow-hidden rounded-md border border-border transition-colors group-hover:border-brand">
                <CoverImage cover={cover} title={title} />
              </div>
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="truncate font-display text-base font-bold leading-snug text-text group-hover:text-brand">
                    {title}
                  </p>
                  {subtitle ? <p className="truncate text-xs text-text-muted">{subtitle}</p> : null}
                </div>
                {badges ? <div className="flex shrink-0 items-center gap-1">{badges}</div> : null}
              </div>
              {meta ? <p className="truncate text-xs text-text-faint">{meta}</p> : null}
            </Link>
          </li>
        )
      })}
    </ul>
  )
}
