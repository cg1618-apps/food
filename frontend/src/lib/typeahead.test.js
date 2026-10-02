// What the typeahead offers from the two searches' answers.
import { describe, expect, it } from 'vitest'

import { mergeResults, stepActive } from './typeahead'

describe('mergeResults', () => {
  const ginger = { id: 1, display_name: '薑', name_cn: '薑', name_en: 'Ginger', needs_detail: true }
  const garlic = { id: 2, display_name: '蒜', name_cn: '蒜', name_en: null, needs_detail: false }
  const sauce = { id: 7, display_name: '薑汁', name_cn: '薑汁', kind: 'base' }

  it('lists ingredients before recipes, each marked with its type', () => {
    const options = mergeResults({ ingredients: [ginger], recipes: [sauce], query: '薑' })
    expect(options.map((o) => [o.type, o.id])).toEqual([
      ['ingredient', 1],
      ['recipe', 7],
    ])
    expect(options[0]).toMatchObject({ label: '薑', detail: 'Ginger', needsDetail: true })
    expect(options[1]).toMatchObject({ kind: 'base' })
  })

  it('offers 新增 only when nothing matches the typed text exactly', () => {
    const near = mergeResults({ ingredients: [ginger], query: '薑末', allowNew: true })
    expect(near.at(-1)).toMatchObject({ type: 'new', label: '薑末' })

    const exact = mergeResults({ ingredients: [ginger], query: ' ginger ', allowNew: true })
    expect(exact.some((o) => o.type === 'new')).toBe(false)
  })

  it('counts an exact recipe name as a match too', () => {
    const options = mergeResults({ recipes: [sauce], query: '薑汁', allowNew: true })
    expect(options.some((o) => o.type === 'new')).toBe(false)
  })

  it('never offers 新增 unless asked, or for blank text', () => {
    expect(mergeResults({ ingredients: [], query: '薑末' })).toEqual([])
    expect(mergeResults({ ingredients: [], query: '  ', allowNew: true })).toEqual([])
  })

  it('leaves out excluded rows and caps each source', () => {
    const options = mergeResults({
      ingredients: [ginger, garlic],
      recipes: [sauce],
      exclude: { ingredient: [1], recipe: [7] },
      limit: 1,
    })
    expect(options.map((o) => o.id)).toEqual([2])
  })

  it('tolerates a source that has not answered', () => {
    expect(mergeResults({ ingredients: undefined, recipes: null, query: 'x' })).toEqual([])
  })
})

describe('stepActive', () => {
  it('starts at the first or last item and wraps', () => {
    expect(stepActive(-1, 1, 3)).toBe(0)
    expect(stepActive(-1, -1, 3)).toBe(2)
    expect(stepActive(2, 1, 3)).toBe(0)
    expect(stepActive(0, -1, 3)).toBe(2)
    expect(stepActive(0, 1, 0)).toBe(-1)
  })
})
