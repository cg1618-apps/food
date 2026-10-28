// Frontend: the page frame - navigation and the content column.
//
// A top bar on a desktop and a bar fixed to the bottom of the screen on a
// phone: this app is opened one-handed in a shop and at the stove, and the
// thumb reaches the bottom of the screen, not the top. The main column is
// padded by the bar's height (and the phone's safe area) so the bar never
// covers the last line of a page.
//
// The active section is marked with aria-current="page" and styled from that
// attribute, so what a screen reader announces and what the eye sees cannot
// disagree. See lib/nav.js for why the match is not NavLink's.
//
// The phone bar has one column per section, counted from lib/nav.js's
// SECTIONS rather than written into a class, so a new section is one entry
// there. Its labels are short (two characters, or TBD) and centred in their
// column, which keeps them readable at 360px with room for a few more.
//
// The edit links are visible to everyone on purpose: the gate is Cloudflare
// Access on the /edit path, not a hidden link. Hiding them would protect
// nothing and would make the app look read-only to its own owner.
//
// The theme toggle sits at the right end of the top bar. On a phone that bar
// is kept, but slim, not sticky, and with only 食 and the toggle in it: the
// bottom bar already gives each section a column at 360px and has no room for
// a control that is not a destination, and a choice made once per device does
// not earn a place under the thumb. See docs/notes/decisions.md.
//
// The search box (NavSearch.jsx) sits in the top bar too, for the same
// reason: it is not a destination, so it has no column in the bottom bar. On
// a wide screen it is a field between the sections and the toggle. Below lg
// the sections leave it no room - eight of them already fill a tablet's bar -
// so a search icon beside the toggle opens a full-width row under the bar,
// and the row closes again once a search has gone somewhere. It is a row in
// the flow rather than an overlay, so nothing is covered and nothing can be
// wider than the screen at 360px.
import { useState } from 'react'
import { Link, Outlet, useLocation } from 'react-router-dom'

import { useTheme } from '../../contexts/theme'
import { activeSection, SECTIONS } from '../../lib/nav'
import { Button } from '../ui/primitives'
import { CloseIcon, MoonIcon, SearchIcon, SunIcon } from './icons'
import NavSearch from './NavSearch'

function NavItems({ active, className }) {
  return SECTIONS.map((section) => (
    <Link
      key={section.key}
      to={section.to}
      aria-current={active === section.key ? 'page' : undefined}
      className={className}
    >
      {section.label}
    </Link>
  ))
}

// The icon shows where a press goes: a sun while the page is dark, a moon
// while it is light.
function ThemeToggle({ className }) {
  const { theme, toggle } = useTheme()
  const dark = theme === 'dark'
  const label = dark ? '切換為淺色模式' : '切換為深色模式'
  return (
    <Button
      kind="ghost"
      onClick={toggle}
      aria-label={label}
      title={label}
      aria-pressed={dark}
      className={className}
    >
      {dark ? <SunIcon /> : <MoonIcon />}
    </Button>
  )
}

export default function Layout() {
  const { pathname } = useLocation()
  const active = activeSection(pathname)
  const [searchOpen, setSearchOpen] = useState(false)
  // Going anywhere else - the bottom bar, a link - closes the search row, as
  // a search that went somewhere does. Adjusted during render, as
  // hooks/useUrlFilters.js follows the URL, so the row never lingers a frame.
  const [seenPath, setSeenPath] = useState(pathname)
  if (pathname !== seenPath) {
    setSeenPath(pathname)
    setSearchOpen(false)
  }
  const searchLabel = searchOpen ? '關閉搜尋' : '搜尋'

  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-canvas/95 backdrop-blur md:sticky md:top-0 md:z-30">
        <div className="mx-auto flex max-w-5xl items-center gap-8 px-4 py-1.5 md:px-6 md:py-3">
          <nav aria-label="主要" className="flex items-center gap-8">
            <Link
              to="/"
              className="font-display text-2xl font-bold leading-none text-brand"
              aria-label="首頁"
            >
              食
            </Link>
            <div className="hidden items-center gap-1 md:flex">
              <NavItems
                active={active}
                className="rounded-md px-3 py-1.5 font-display text-[0.95rem] text-text-muted transition-colors hover:text-text aria-[current=page]:bg-brand-soft aria-[current=page]:text-brand"
              />
            </div>
          </nav>
          <NavSearch className="ml-auto hidden w-56 lg:block xl:w-72" />
          <div className="ml-auto flex items-center gap-1 lg:ml-0">
            <Button
              kind="ghost"
              onClick={() => setSearchOpen((open) => !open)}
              aria-label={searchLabel}
              title={searchLabel}
              aria-expanded={searchOpen}
              aria-controls="phone-search"
              className="lg:hidden"
            >
              {searchOpen ? <CloseIcon /> : <SearchIcon />}
            </Button>
            <ThemeToggle />
          </div>
        </div>
        {searchOpen ? (
          <div id="phone-search" className="mx-auto max-w-5xl px-4 pb-2 md:px-6 lg:hidden">
            <NavSearch variant="sheet" onDone={() => setSearchOpen(false)} />
          </div>
        ) : null}
      </header>

      <main className="mx-auto max-w-5xl px-4 pt-5 pb-[calc(4.5rem+env(safe-area-inset-bottom))] md:px-6 md:pt-8 md:pb-12">
        <Outlet />
      </main>

      <nav
        aria-label="主要"
        style={{ gridTemplateColumns: `repeat(${SECTIONS.length}, minmax(0, 1fr))` }}
        className="fixed inset-x-0 bottom-0 z-30 grid border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden"
      >
        <NavItems
          active={active}
          className="relative truncate px-1 py-3 text-center font-display text-base text-text-muted aria-[current=page]:text-brand aria-[current=page]:before:absolute aria-[current=page]:before:inset-x-4 aria-[current=page]:before:top-0 aria-[current=page]:before:h-0.5 aria-[current=page]:before:rounded-full aria-[current=page]:before:bg-brand"
        />
      </nav>
    </div>
  )
}
