// Frontend: the four sections of the app and which one a path belongs to.
//
// The navigation is 食譜 · 食材 · 筆記 · 設定. A section is active on its own
// pages AND on the edit pages behind them - the recipe form is still "in"
// 食譜 - which react-router's NavLink prefix match cannot say, because the
// edit pages live under /edit/... for the Access gate. So the match is written
// out here, once, and tested.

export const SECTIONS = [
  { key: 'recipes', label: '食譜', to: '/recipes', prefixes: ['/recipes', '/edit/recipes'] },
  {
    key: 'ingredients',
    label: '食材',
    to: '/ingredients',
    prefixes: ['/ingredients', '/edit/ingredients'],
  },
  { key: 'notes', label: '筆記', to: '/notes', prefixes: ['/notes', '/edit/notes'] },
  // 設定 is a write page and lives under the gated prefix; the image library
  // is filed under it because it is maintenance, not reading.
  {
    key: 'settings',
    label: '設定',
    to: '/edit/settings',
    prefixes: ['/edit/settings', '/edit/images'],
  },
]

function underPrefix(pathname, prefix) {
  return pathname === prefix || pathname.startsWith(`${prefix}/`)
}

/** The key of the section `pathname` belongs to, or null. */
export function activeSection(pathname) {
  const section = SECTIONS.find((s) => s.prefixes.some((p) => underPrefix(pathname, p)))
  return section ? section.key : null
}
