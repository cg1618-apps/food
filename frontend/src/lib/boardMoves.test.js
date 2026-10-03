import { describe, expect, it } from 'vitest'

import { neighbourPlace, placeOf } from './boardMoves'

const CONTAINERS = [
  { id: 'ungrouped', items: ['a'] },
  { id: 'g1', items: ['b', 'c'] },
  { id: 'g2', items: [] },
  { id: 'g3', items: ['d'] },
]

describe('neighbourPlace', () => {
  it('moves inside a container while there is room', () => {
    expect(neighbourPlace(CONTAINERS, { container: 'g1', index: 0 }, 1)).toEqual({ container: 'g1', index: 1 })
  })

  it('crosses an edge to the end of the container above and the start of the one below', () => {
    expect(neighbourPlace(CONTAINERS, { container: 'g1', index: 0 }, -1)).toEqual({ container: 'ungrouped', index: 1 })
    expect(neighbourPlace(CONTAINERS, { container: 'g1', index: 1 }, 1)).toEqual({ container: 'g2', index: 0 })
    // Into an empty container from below, too.
    expect(neighbourPlace(CONTAINERS, { container: 'g3', index: 0 }, -1)).toEqual({ container: 'g2', index: 0 })
  })

  it('goes nowhere off the very top or bottom', () => {
    expect(neighbourPlace(CONTAINERS, { container: 'ungrouped', index: 0 }, -1)).toBeNull()
    expect(neighbourPlace(CONTAINERS, { container: 'g3', index: 0 }, 1)).toBeNull()
  })
})

describe('placeOf', () => {
  it('finds a row in whichever container holds it', () => {
    expect(placeOf(CONTAINERS, 'c')).toEqual({ container: 'g1', index: 1 })
    expect(placeOf(CONTAINERS, 'zz')).toBeNull()
  })
})
