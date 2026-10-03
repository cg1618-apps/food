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
    ['/ingredients', 'ingredients'],
    ['/ingredients/3', 'ingredients'],
    ['/edit/ingredients/3', 'ingredients'],
    ['/notes/4', 'notes'],
    ['/edit/notes/new', 'notes'],
    ['/edit/settings', 'settings'],
    ['/edit/images', 'settings'],
    ['/tbd', 'tbd'],
    ['/edit/tbd', 'tbd'],
  ])('%s is in %s', (path, key) => {
    expect(activeSection(path)).toBe(key)
  })

  it('matches whole segments, not string prefixes', () => {
    // /recipes-old must not light up 食譜.
    expect(activeSection('/recipes-old')).toBeNull()
    expect(activeSection('/')).toBeNull()
  })

  it('has the six sections, in navigation order, 料理 first', () => {
    expect(SECTIONS.map((s) => s.label)).toEqual(['料理', '食譜', '食材', '筆記', 'TBD', '設定'])
  })
})
