import { describe, expect, it } from 'vitest'

import { activeSection, SECTIONS } from './nav'

describe('activeSection', () => {
  it.each([
    ['/dishes', 'dishes'],
    ['/dishes/7', 'dishes'],
    ['/edit/dishes/new', 'dishes'],
    ['/edit/dishes/7', 'dishes'],
    ['/recipes', 'recipes'],
    ['/recipes/12', 'recipes'],
    ['/edit/recipes/new', 'recipes'],
    ['/authors', 'authors'],
    ['/authors/6', 'authors'],
    ['/edit/authors/new', 'authors'],
    ['/edit/authors/6', 'authors'],
    ['/ingredients', 'ingredients'],
    ['/ingredients/3', 'ingredients'],
    ['/edit/ingredients/3', 'ingredients'],
    ['/notes/4', 'notes'],
    ['/edit/notes/new', 'notes'],
    ['/edit/settings', 'settings'],
    ['/edit/fixed-settings', 'settings'],
    ['/edit/images', 'settings'],
    ['/schedule', 'schedule'],
    ['/edit/schedule', 'schedule'],
    ['/heating', 'heating'],
    ['/edit/heating', 'heating'],
    ['/tbd', 'tbd'],
    ['/edit/tbd', 'tbd'],
  ])('%s is in %s', (path, key) => {
    expect(activeSection(path)).toBe(key)
  })

  it('matches whole segments, not string prefixes', () => {
    // /recipes-old must not light up 食譜.
    expect(activeSection('/recipes-old')).toBeNull()
    expect(activeSection('/authorship')).toBeNull()
    expect(activeSection('/')).toBeNull()
  })

  it('puts the search results page in no section', () => {
    // A search reaches every section, so it belongs to none of them.
    expect(activeSection('/search')).toBeNull()
  })

  it('has the eight sections, in navigation order, 料理 first', () => {
    expect(SECTIONS.map((s) => s.label)).toEqual(['料理', '食譜', '作者', '食材', '筆記', '加熱', '排程', 'TBD', '設定'])
  })
})
