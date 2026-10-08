// Frontend: a library's 清單 view - one row per item.
//
// The first column is always the name, as a link, with the item's badges -
// `listBadges` when the card gives them, for a badge that has its own column
// here (an ingredient's rating) and would otherwise show twice. The rest are
// the page's `columns`, [{ key, header, render(item, place), className? }].
// media makes the whole row clickable; here the name is a real link instead,
// so a row can be opened in a new tab and a keyboard reaches it with Tab.
//
// Given `sections` (see CoverGrid), each section opens with a heading row and
// a group's varieties follow their parent, indented by depth behind a └, the
// parent's row marked by a rule in the accent.
//
// On a phone the table scrolls sideways inside its frame rather than pushing
// the page wider than the screen.
import { Link } from 'react-router-dom'

import { cx } from '../../lib/cx'

/** A section's title and count - shared by the 封面 and 清單 views. */
export function SectionHeading({ title, count }) {
  return (
    <h2 className="flex items-baseline gap-2 border-b border-border-strong pb-1.5 font-display text-base font-bold text-text">
      {title}
      <span className="font-sans text-xs font-normal tabular-nums text-text-faint">{count} 筆</span>
    </h2>
  )
}

function Row({ item, place = {}, tone, itemTo, card, columns }) {
  const { title, subtitle, badges, listBadges } = card(item, place)
  const depth = place.depth ?? 0
  return (
    <tr
      className={cx(
        'transition-colors hover:bg-surface-2',
        tone === 'parent' && 'shadow-[inset_3px_0_var(--c-brand)]',
        tone === 'variety' && 'shadow-[inset_3px_0_var(--c-brand-soft)]',
      )}
    >
      <td className="px-3 py-2 align-top" style={depth ? { paddingLeft: `${0.75 + depth * 1.125}rem` } : undefined}>
        <div className="flex items-center gap-2">
          {depth ? (
            <span aria-hidden="true" className="text-text-faint">
              └
            </span>
          ) : null}
          <Link to={itemTo(item)} className="font-display font-bold text-text hover:text-brand">
            {title}
          </Link>
          {listBadges !== undefined ? listBadges : badges}
        </div>
        {subtitle ? <div className="text-xs text-text-faint">{subtitle}</div> : null}
      </td>
      {columns.map((column) => (
        <td key={column.key} className={cx('px-3 py-2 align-top text-text-muted', column.className)}>
          {column.render(item, place) ?? <span className="text-text-faint">—</span>}
        </td>
      ))}
    </tr>
  )
}

function SectionRows({ section, ...shared }) {
  return (
    <>
      <tr className="bg-surface-2">
        <th
          scope="colgroup"
          colSpan={shared.columns.length + 1}
          className="border-t border-border-strong px-3 py-1.5 text-left font-display text-sm font-bold text-text"
        >
          {section.title}
          <span className="ml-2 font-sans text-xs font-normal tabular-nums text-text-faint">
            {section.count} 筆
          </span>
        </th>
      </tr>
      {section.entries.map((entry) =>
        entry.kind === 'group' ? (
          <GroupRows key={entry.root.id} entry={entry} {...shared} />
        ) : (
          <Row key={entry.item.id} item={entry.item} {...shared} />
        ),
      )}
    </>
  )
}

function GroupRows({ entry, ...shared }) {
  return (
    <>
      <Row item={entry.root} tone="parent" {...shared} />
      {entry.members.map(({ item, depth }) => (
        <Row key={item.id} item={item} place={{ depth, root: entry.root }} tone="variety" {...shared} />
      ))}
    </>
  )
}

export default function LibraryTable({ items, sections, itemTo, card, columns, nameHeader = '名稱' }) {
  const shared = { itemTo, card, columns }
  return (
    <div className="overflow-x-auto rounded-md border border-border bg-surface">
      <table className="w-full text-left text-sm">
        <thead className="border-b border-border-strong">
          <tr>
            <th scope="col" className="px-3 py-2 text-xs font-medium text-text-muted">
              {nameHeader}
            </th>
            {columns.map((column) => (
              <th
                key={column.key}
                scope="col"
                className={cx('px-3 py-2 text-xs font-medium whitespace-nowrap text-text-muted', column.className)}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-border">
          {sections
            ? sections.map((section) => <SectionRows key={section.key} section={section} {...shared} />)
            : items.map((item) => <Row key={item.id} item={item} {...shared} />)}
        </tbody>
      </table>
    </div>
  )
}
