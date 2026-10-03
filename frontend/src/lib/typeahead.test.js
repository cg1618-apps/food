// What the typeahead offers from the two searches' answers.
import { describe, expect, it } from 'vitest'

import { mergeResults, stepActive } from './typeahead'

describe('mergeResults', () => {
  const ginger = { id: 1, display_name: '薑', name_cn: '薑', name_en: 'Ginger', needs_detail: true }
  const garlic = { id: 2, display_name: '蒜', name_cn: '蒜', name_en: null, needs_detail: false }
  const sauce = { id: 7, display_name: '薑汁', name_cn: '薑汁', kind: 'sauce' }

  it('lists ingredients before dishes, each marked with its type', () => {
    const options = mergeResults({ ingredients: [ginger], dishes: [sauce], query: '薑' })
    expect(options.map((o) => [o.type, o.id])).toEqual([
      ['ingredient', 1],
      ['dish', 7],
    ])
    expect(options[0]).toMatchObject({ label: '薑', detail: 'Ginger', needsDetail: true })
    expect(options[1]).toMatchObject({ kind: 'sauce' })
  })

  it('offers recipes by their name, with the dish beside one that has its own', () => {
    const recipes = [
      { id: 3, display_name: '阿嬤版', name: '阿嬤版', dish: { id: 9, display_name: '滷肉' } },
      { id: 4, display_name: '滷肉', name: null, dish: { id: 9, display_name: '滷肉' } },
    ]
    const options = mergeResults({ recipes, query: '滷' })
    expect(options.map((o) => [o.type, o.id, o.label, o.detail])).toEqual([
      ['recipe', 3, '阿嬤版', '滷肉'],
      ['recipe', 4, '滷肉', ''],
    ])
  })

  it('offers 新增 only when nothing matches the typed text exactly', () => {
    const near = mergeResults({ ingredients: [ginger], query: '薑末', allowNew: true })
    expect(near.at(-1)).toMatchObject({ type: 'new', label: '薑末' })

    const exact = mergeResults({ ingredients: [ginger], query: ' ginger ', allowNew: true })
    expect(exact.some((o) => o.type === 'new')).toBe(false)
  })

  it('counts an exact dish name as a match too', () => {
    const options = mergeResults({ dishes: [sauce], query: '薑汁', allowNew: true, allowNewDish: true })
    expect(options.some((o) => o.type === 'new' || o.type === 'new-dish')).toBe(false)
  })

  it('offers a new dish beside a new ingredient when both are allowed', () => {
    const options = mergeResults({ ingredients: [ginger], query: '薑醬', allowNew: true, allowNewDish: true })
    expect(options.slice(-2).map((o) => [o.type, o.label])).toEqual([
      ['new', '薑醬'],
      ['new-dish', '薑醬'],
    ])
    const dishOnly = mergeResults({ dishes: [], query: '咖哩', allowNewDish: true })
    expect(dishOnly.map((o) => o.type)).toEqual(['new-dish'])
  })

  it('never offers 新增 unless asked, or for blank text', () => {
    expect(mergeResults({ ingredients: [], query: '薑末' })).toEqual([])
    expect(mergeResults({ ingredients: [], query: '  ', allowNew: true })).toEqual([])
  })

  it('leaves out excluded rows and caps each source', () => {
    const options = mergeResults({
      ingredients: [ginger, garlic],
      dishes: [sauce],
      exclude: { ingredient: [1], dish: [7] },
      limit: 1,
    })
    expect(options.map((o) => o.id)).toEqual([2])
  })

  it('tolerates a source that has not answered', () => {
    expect(mergeResults({ ingredients: undefined, dishes: null, query: 'x' })).toEqual([])
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
