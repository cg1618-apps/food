// How a new recipe's start is read from its URL and written back.
import { describe, expect, it } from 'vitest'

import { chosenSearch, newRecipeStart } from './newRecipe'

const params = (text) => new URLSearchParams(text)

describe('newRecipeStart', () => {
  it('has chosen nothing without blank or from - a preset dish alone is no choice', () => {
    expect(newRecipeStart(params(''))).toEqual({ dish: null, from: null, chosen: false })
    expect(newRecipeStart(params('?dish=4'))).toMatchObject({ dish: '4', chosen: false })
  })

  it('reads each choice, ignoring an id that is not a number', () => {
    expect(newRecipeStart(params('?blank=1'))).toMatchObject({ chosen: true, from: null })
    expect(newRecipeStart(params('?from=9&dish=4'))).toEqual({ dish: '4', from: '9', chosen: true })
    expect(newRecipeStart(params('?from=x'))).toMatchObject({ from: null, chosen: false })
  })
})

describe('chosenSearch', () => {
  it('writes the choice, keeping the dish and dropping any earlier choice', () => {
    expect(chosenSearch(params('?dish=4'), { blank: true })).toBe('?dish=4&blank=1')
    expect(chosenSearch(params('?dish=4&from=2'), { blank: true })).toBe('?dish=4&blank=1')
    expect(chosenSearch(params(''), { from: 9 })).toBe('?from=9')
  })
})
