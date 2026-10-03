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
import { Link, Outlet, useLocation } from 'react-router-dom'

import { activeSection, SECTIONS } from '../../lib/nav'

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

export default function Layout() {
  const { pathname } = useLocation()
  const active = activeSection(pathname)

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-30 hidden border-b border-border bg-canvas/95 backdrop-blur md:block">
        <nav aria-label="主要" className="mx-auto flex max-w-5xl items-center gap-8 px-6 py-3">
          <Link
            to="/"
            className="font-display text-2xl font-bold leading-none text-brand"
            aria-label="首頁"
          >
            食
          </Link>
          <div className="flex items-center gap-1">
            <NavItems
              active={active}
              className="rounded-md px-3 py-1.5 font-display text-[0.95rem] text-text-muted transition-colors hover:text-text aria-[current=page]:bg-brand-soft aria-[current=page]:text-brand"
            />
          </div>
        </nav>
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
