// Frontend: which tab a page is on, read from and written to the URL query
// (`?tab=courses`), so a tab can be linked to and survives a reload.
//
// A tab click REPLACES the history entry rather than pushing one. Tabs are
// views of one page, not places you went: Back from 設定 should leave 設定,
// not walk back through every vocabulary looked at on the way - the WAI-ARIA
// tabs pattern does not create history either. A library filter differs
// (hooks/useUrlFilters.js pushes it): a filtered list is a result you may
// want to return to.
//
// A missing or unknown tab is the first one. The URL is left as it is in that
// case rather than rewritten, so an old link is not edited under the reader.
import { useCallback } from 'react'
import { useSearchParams } from 'react-router-dom'

export const TAB_PARAM = 'tab'

/**
 * `tabs` is [{ id, ... }], at least one. Returns [selectedId, select(id)].
 * Other query parameters are kept.
 */
export function useUrlTab(tabs) {
  const [searchParams, setSearchParams] = useSearchParams()
  const asked = searchParams.get(TAB_PARAM)
  const selected = tabs.some((tab) => tab.id === asked) ? asked : tabs[0].id

  const select = useCallback(
    (id) =>
      setSearchParams(
        (previous) => {
          const next = new URLSearchParams(previous)
          next.set(TAB_PARAM, id)
          return next
        },
        { replace: true },
      ),
    [setSearchParams],
  )

  return [selected, select]
}
