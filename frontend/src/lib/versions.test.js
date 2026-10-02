import { describe, expect, it } from 'vitest'

import { otherVersions } from './versions'

const ref = (id, name) => ({ id, display_name: name, kind: 'dish' })

describe('otherVersions', () => {
  it('lists an original’s versions', () => {
    const recipe = { id: 1, variant_of: null, versions: [ref(2, 'B'), ref(3, 'C')] }
    expect(otherVersions(recipe).map((v) => [v.id, v.original])).toEqual([
      [2, false],
      [3, false],
    ])
  })

  it('puts a version’s original first, then its siblings', () => {
    const recipe = { id: 2, variant_of: ref(1, 'A'), versions: [ref(3, 'C')] }
    expect(otherVersions(recipe).map((v) => [v.id, v.original])).toEqual([
      [1, true],
      [3, false],
    ])
  })

  it('never lists the recipe itself or one twice', () => {
    const recipe = { id: 2, variant_of: ref(1, 'A'), versions: [ref(2, 'B'), ref(1, 'A')] }
    expect(otherVersions(recipe).map((v) => v.id)).toEqual([1])
  })

  it('is empty for a recipe with no family', () => {
    expect(otherVersions({ id: 1, variant_of: null, versions: [] })).toEqual([])
    expect(otherVersions(null)).toEqual([])
  })
})
