import { describe, expect, it } from 'vitest'

import { flattenGroups, groupResults, SEARCH_TYPES, searchPath } from './search'

const row = (id, name) => ({ id, display_name: name, detail: null, cover: null })

describe('the search kinds', () => {
  it('lists every bucket the API answers, in its order, with its label', () => {
    expect(SEARCH_TYPES.map((t) => [t.key, t.label])).toEqual([
      ['dishes', '料理'],
      ['recipes', '食譜'],
      ['ingredients', '食材'],
      ['notes', '筆記'],
      ['authors', '作者'],
      ['heating', '加熱'],
      ['tbd', 'TBD'],
    ])
  })

  it.each([
    ['dishes', '/dishes/7', '/edit/dishes/7'],
    ['recipes', '/recipes/7', '/edit/recipes/7'],
    ['ingredients', '/ingredients/7', '/edit/ingredients/7'],
    ['notes', '/notes/7', '/edit/notes/7'],
    ['authors', '/authors/7', '/edit/authors/7'],
    // No page per entry: the list at the entry, and the list's edit page.
    ['heating', '/heating#heating-7', '/edit/heating'],
    ['tbd', '/tbd#tbd-7', '/edit/tbd'],
  ])('a %s row opens %s and edits at %s', (key, item, edit) => {
    const type = SEARCH_TYPES.find((t) => t.key === key)
    expect(type.itemTo(7)).toBe(item)
    expect(type.editTo(7)).toBe(edit)
  })
})

describe('searchPath', () => {
  it('is the results page for a trimmed term', () => {
    expect(searchPath('  紅 燒 ')).toBe(`/search?q=${encodeURIComponent('紅 燒').replace(/%20/g, '+')}`)
  })

  it('is nothing for a blank term', () => {
    expect(searchPath('   ')).toBeNull()
    expect(searchPath(undefined)).toBeNull()
  })
})

describe('grouping and flattening', () => {
  const results = {
    dishes: [row(1, '咖哩'), row(2, '咖哩飯')],
    recipes: [],
    tbd: [row(9, '咖哩粉連結')],
  }

  it('keeps the buckets that hold something, in kind order; a missing one is empty', () => {
    const groups = groupResults(results)
    expect(groups.map((g) => [g.type.key, g.rows.length])).toEqual([
      ['dishes', 2],
      ['tbd', 1],
    ])
    expect(groupResults(undefined)).toEqual([])
  })

  it('numbers the rows across the groups, in the order the arrows walk', () => {
    const flat = flattenGroups(groupResults(results))
    expect(flat.map((item) => [item.index, item.type.key, item.row.id])).toEqual([
      [0, 'dishes', 1],
      [1, 'dishes', 2],
      [2, 'tbd', 9],
    ])
  })
})
