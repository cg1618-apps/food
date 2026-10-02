// Frontend: each library's 封面 / 清單 choice, remembered.
//
// media's lib/dashboardView.js, per library. Which layout a library draws is a
// display choice about this screen, so it lives in this browser's
// localStorage and never reaches the server: it does not follow you to another
// machine, and nobody else sees it.
//
// Media's library view is NOT remembered (it resets to the grid on every
// visit); food's is, because the spec asks for it - the ingredient library is
// read as a table at the desk and as covers on a phone, and each device should
// keep its own. Recorded in docs/notes/decisions.md.
//
// Both functions always return one of VIEWS. The library picks a layout from
// the result and has no third branch to fall into, so a stored value that is
// absent, corrupt, or written by a future version has to read as "cover".
export const VIEWS = ['cover', 'list']
export const DEFAULT_VIEW = 'cover'

/** The storage key for one library: `cg1618:food:<library>-view`. */
export function libraryViewKey(library) {
  return `cg1618:food:${library}-view`
}

function known(view) {
  return VIEWS.includes(view)
}

// Every read and write goes through a try/catch: a private window, blocked
// site data or a full quota must degrade to the default layout, never to a
// library that fails to render.
export function readLibraryView(library) {
  let raw
  try {
    raw = localStorage.getItem(libraryViewKey(library))
  } catch {
    return DEFAULT_VIEW
  }
  return known(raw) ? raw : DEFAULT_VIEW
}

export function writeLibraryView(library, view) {
  if (!known(view)) return DEFAULT_VIEW
  try {
    localStorage.setItem(libraryViewKey(library), view)
  } catch {
    // The toggle has already moved on screen. A failed write means the choice
    // does not outlive the tab, which is not worth interrupting anyone over.
  }
  return view
}
