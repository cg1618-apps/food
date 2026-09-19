import { Link, NavLink, Outlet } from 'react-router-dom'

const linkStyle = ({ isActive }) =>
  `rounded px-3 py-1.5 text-sm ${isActive ? 'bg-brand-soft text-text' : 'text-text-muted hover:text-text'}`

export default function Layout() {
  return (
    <div className="min-h-screen">
      <header className="border-b border-border bg-surface">
        <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-2 px-4 py-3">
          <Link to="/" className="mr-4 text-lg font-semibold">
            食
          </Link>
          <NavLink to="/library/ingredient" className={linkStyle}>
            Ingredients
          </NavLink>
          {/* The edit links are visible to everyone on purpose: the gate is
              Cloudflare Access on the path, not a hidden link. Hiding them
              would protect nothing and would make the app look read-only to
              its own owner. */}
          <NavLink to="/edit/vocabularies" className={linkStyle}>
            Categories &amp; labels
          </NavLink>
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-6">
        <Outlet />
      </main>
    </div>
  )
}
