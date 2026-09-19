import { describe, expect, it } from 'vitest'

import { flatten, subtreeIds } from './tree'

const tree = [
  {
    id: 1,
    display_name: '調味料',
    children: [
      { id: 2, display_name: '醬油', children: [{ id: 3, display_name: '生抽', children: [] }] },
    ],
  },
  { id: 4, display_name: '蔬菜', children: [] },
]

describe('flatten', () => {
  it('carries the depth of every node', () => {
    expect(flatten(tree).map((n) => [n.id, n.depth])).toEqual([
      [1, 0],
      [2, 1],
      [3, 2],
      [4, 0],
    ])
  })

  it('handles a node with no children key at all', () => {
    expect(flatten([{ id: 9 }]).map((n) => n.id)).toEqual([9])
  })
})

describe('subtreeIds', () => {
  it('includes the node itself and every descendant', () => {
    expect(subtreeIds(tree[0])).toEqual([1, 2, 3])
  })
})
