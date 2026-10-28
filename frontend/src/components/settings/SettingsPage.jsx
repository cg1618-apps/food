// Frontend: the shape both settings pages share - a heading, the buttons to
// the neighbouring pages, an optional intro line, and a tab bar over one
// panel (components/settings/settingsTabs.jsx holds the tabs).
//
// One page with tabs rather than one page per vocabulary: each is a short
// list maintained the same way, and a route each would be a page per handful
// of rows. Tabs rather than one long column, because the column grows with
// every vocabulary added and the one you meant ends up a long scroll away.
// The tab is in the URL (`?tab=courses`, hooks/useUrlTab.js); a missing or
// unknown one is the first. Only the selected tab's editor is mounted, so
// only its query runs, and one vocabulary failing to load blanks nothing
// else.
//
// A `?tab=` naming a tab the OTHER page holds is a link written before the
// vocabularies were split between 設定 and 未來固定設定; it is sent on to that
// page with the query kept, replacing the history entry so Back does not
// bounce through the redirect.
//
//   title      the page's heading, and the tab bar's accessible name
//   intro      a line under the heading, or nothing
//   actions    the buttons beside the heading
//   tabs       this page's tabs, in order
//   elsewhere  { path, tabs } - the other settings page, for the redirect
import { Navigate, useLocation } from 'react-router-dom'

import { Tabs } from '../ui/primitives'
import { TAB_PARAM, useUrlTab } from '../../hooks/useUrlTab'

export default function SettingsPage({ title, intro, actions, tabs, elsewhere }) {
  const { search, hash } = useLocation()
  const [selected, select] = useUrlTab(tabs)

  const asked = new URLSearchParams(search).get(TAB_PARAM)
  if (asked !== selected && elsewhere.tabs.some(({ id }) => id === asked)) {
    return <Navigate to={`${elsewhere.path}${search}${hash}`} replace />
  }

  const tab = tabs.find(({ id }) => id === selected)

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-3xl font-bold">{title}</h1>
          <div className="flex flex-wrap gap-2">{actions}</div>
        </div>
        {intro && <p className="text-sm text-text-muted">{intro}</p>}
      </div>

      <Tabs label={title} tabs={tabs} selected={selected} onSelect={select}>
        {/* Keyed by tab, so switching tabs never carries an editor's local
            state - an open rename, a half-typed add - into another. */}
        <div key={tab.id}>{tab.render()}</div>
      </Tabs>
    </div>
  )
}
