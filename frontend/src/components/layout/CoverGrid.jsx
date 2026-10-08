// Frontend: a library's 封面 view - a grid of covers.
//
// Each tile is a link to the item: the cover image (cropped, at its focal
// point) or a placeholder, the name in the serif, one line of metadata, and
// the badges. The page says what goes in each slot through `card(item, place)`,
// which returns { cover, title, subtitle?, meta?, badges? }; the grid owns the
// shape, so the libraries cannot drift apart.
//
// A library may hand over `sections` instead of a flat list - the ingredient
// library does, from lib/ingredientGroups.js. Each section is headed with its
// title and count, and a `group` entry is one outlined block: the parent's
// tile on the left, its varieties' tiles beside it, so what belongs to what is
// read without a label. `place` tells `card` where a tile sits -
// { depth, root } inside a block, {} elsewhere - so a variety need not repeat
// what the block already says.
import { Link } from 'react-router-dom'

import { focusStyle } from '../../lib/images'
import { SectionHeading } from './LibraryTable'

const GRID = 'grid grid-cols-2 gap-x-3 gap-y-5 sm:grid-cols-3 xl:grid-cols-4'

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

function CoverTile({ item, itemTo, card, place = {} }) {
  const { cover, title, subtitle, meta, badges } = card(item, place)
  return (
    <Link to={itemTo(item)} className="group block space-y-1.5">
      <div className="aspect-[4/3] overflow-hidden rounded-md border border-border transition-colors group-hover:border-brand">
        <CoverImage cover={cover} title={title} />
      </div>
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-display text-base font-bold leading-snug text-text group-hover:text-brand">
            {place.depth > 1 ? <span className="mr-0.5 font-sans font-normal text-text-faint">└</span> : null}
            {title}
          </p>
          {subtitle ? <p className="truncate text-xs text-text-muted">{subtitle}</p> : null}
        </div>
        {badges ? <div className="flex shrink-0 items-center gap-1">{badges}</div> : null}
      </div>
      {meta ? <p className="truncate text-xs text-text-faint">{meta}</p> : null}
    </Link>
  )
}

function Tiles({ items, itemTo, card }) {
  return (
    <ul className={GRID}>
      {items.map((item) => (
        <li key={item.id}>
          <CoverTile item={item} itemTo={itemTo} card={card} />
        </li>
      ))}
    </ul>
  )
}

function GroupBlock({ entry, itemTo, card }) {
  return (
    <li className="grid gap-3 rounded-lg border border-border-strong bg-surface p-3 sm:grid-cols-[minmax(0,1fr)_minmax(0,3fr)]">
      <div className="border-b border-dashed border-border-strong pb-3 sm:border-r sm:border-b-0 sm:pr-3 sm:pb-0">
        <CoverTile item={entry.root} itemTo={itemTo} card={card} />
      </div>
      <ul aria-label={`${entry.root.display_name} 的品種`} className="grid grid-cols-2 content-start gap-x-3 gap-y-4 lg:grid-cols-3">
        {entry.members.map(({ item, depth }) => (
          <li key={item.id}>
            <CoverTile item={item} itemTo={itemTo} card={card} place={{ depth, root: entry.root }} />
          </li>
        ))}
      </ul>
    </li>
  )
}

function Section({ section, itemTo, card }) {
  const blocks = section.entries.filter((entry) => entry.kind === 'group')
  const items = section.entries.filter((entry) => entry.kind === 'item').map((entry) => entry.item)
  return (
    <section aria-label={section.title} className="space-y-3.5">
      <SectionHeading title={section.title} count={section.count} />
      {blocks.length ? (
        <ul className="space-y-3.5">
          {blocks.map((entry) => (
            <GroupBlock key={entry.root.id} entry={entry} itemTo={itemTo} card={card} />
          ))}
        </ul>
      ) : null}
      {items.length ? <Tiles items={items} itemTo={itemTo} card={card} /> : null}
    </section>
  )
}

export default function CoverGrid({ items, sections, itemTo, card }) {
  if (sections) {
    return (
      <div className="space-y-8">
        {sections.map((section) => (
          <Section key={section.key} section={section} itemTo={itemTo} card={card} />
        ))}
      </div>
    )
  }
  return <Tiles items={items} itemTo={itemTo} card={card} />
}
