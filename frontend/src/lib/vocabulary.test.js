import { describe, expect, it } from 'vitest'

import { categoryBlockers, inUseMessage, nextSortOrder, reorderPatches } from './vocabulary'

const rows = (...orders) => orders.map((sort_order, i) => ({ id: i + 1, sort_order }))

describe('reorderPatches', () => {
  it('swaps two values when every sort_order is distinct', () => {
    expect(reorderPatches(rows(10, 20, 30), 2, -1)).toEqual([
      { id: 3, sort_order: 20 },
      { id: 2, sort_order: 30 },
    ])
  })

  it('restores the original numbers when moved up and back down', () => {
    const start = rows(10, 20, 30)
    const [a, b] = reorderPatches(start, 1, -1)
    const after = [
      { id: 2, sort_order: a.sort_order },
      { id: 1, sort_order: b.sort_order },
      start[2],
    ]
    const back = reorderPatches(after, 0, 1)
    expect(back).toEqual([
      { id: 2, sort_order: 20 },
      { id: 1, sort_order: 10 },
    ])
  })

  it('renumbers when sort_orders tie, sending only what changes', () => {
    // [0, 0, 0] ordered by name; moving the last up gives 1, 3, 2.
    expect(reorderPatches(rows(0, 0, 0), 2, -1)).toEqual([
      { id: 1, sort_order: 1 },
      { id: 3, sort_order: 2 },
      { id: 2, sort_order: 3 },
    ])
    // [1, 2, 2]: the third already holds 2, so only the second moves.
    expect(reorderPatches(rows(1, 2, 2), 2, -1)).toEqual([{ id: 2, sort_order: 3 }])
  })

  it('answers nothing for a move off either end', () => {
    expect(reorderPatches(rows(1, 2), 0, -1)).toEqual([])
    expect(reorderPatches(rows(1, 2), 1, 1)).toEqual([])
  })
})

describe('nextSortOrder', () => {
  it('goes after the largest, or 0 for an empty list', () => {
    expect(nextSortOrder(rows(3, 9, 1))).toBe(10)
    expect(nextSortOrder([])).toBe(0)
  })
})

describe('categoryBlockers', () => {
  it('names what is filed under the node and what sits beneath it', () => {
    expect(categoryBlockers({ display_name: '蔬菜', ingredient_count: 3, children: [{}] })).toBe(
      '「蔬菜」底下還有 3 種食材、1 個子分類，先移走再刪。',
    )
    expect(categoryBlockers({ display_name: '空', ingredient_count: 0, children: [] })).toBeNull()
  })
})

describe('inUseMessage', () => {
  it("uses the server's count from a 409", () => {
    const error = Object.assign(new Error('x'), { status: 409, body: { usage_count: 4 } })
    expect(inUseMessage('炒', error)).toBe('「炒」還用在 4 個地方，先改掉那些再刪。')
  })

  it("falls back to the server's sentence otherwise", () => {
    expect(inUseMessage('炒', Object.assign(new Error('No such course.'), { status: 404 }))).toBe(
      'No such course.',
    )
  })
})
