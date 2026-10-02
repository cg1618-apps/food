// Frontend: a library's 清單 view - one row per item.
//
// The first column is always the name, as a link, with the item's badges -
// `listBadges` when the card gives them, for a badge that has its own column
// here (an ingredient's rating) and would otherwise show twice. The rest are
// the page's `columns`, [{ key, header, render(item), className? }].
// media makes the whole row clickable; here the name is a real link instead,
// so a row can be opened in a new tab and a keyboard reaches it with Tab.
//
// On a phone the table scrolls sideways inside its frame rather than pushing
// the page wider than the screen.
import { Link } from 'react-router-dom'

import { cx } from '../../lib/cx'

export default function LibraryTable({ items, itemTo, card, columns, nameHeader = '名稱' }) {
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
          {items.map((item) => {
            const { title, subtitle, badges, listBadges } = card(item)
            return (
              <tr key={item.id} className="transition-colors hover:bg-surface-2">
                <td className="px-3 py-2 align-top">
                  <div className="flex items-center gap-2">
                    <Link
                      to={itemTo(item)}
                      className="font-display font-bold text-text hover:text-brand"
                    >
                      {title}
                    </Link>
                    {listBadges !== undefined ? listBadges : badges}
                  </div>
                  {subtitle ? <div className="text-xs text-text-faint">{subtitle}</div> : null}
                </td>
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cx('px-3 py-2 align-top text-text-muted', column.className)}
                  >
                    {column.render(item) ?? <span className="text-text-faint">—</span>}
                  </td>
                ))}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
