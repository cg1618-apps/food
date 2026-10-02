import { describe, expect, it } from 'vitest'

import { describeMerge } from './mergePreview'

const STATES = [
  { value: 'unused', label: '未使用' },
  { value: 'opened', label: '已開封' },
]

const PREVIEW = {
  moves: { lines: 2, children: 0, links: 1, labels: 0, images: 0, heating: 1, preservation: 1 },
  new_aliases: ['蔥', 'scallion'],
  dropped_preservation: [{ state: 'unused', method: '冷藏' }],
  prose: { description: 'dropped', selection_notes: 'moved', sourcing_notes: 'moved' },
  fingerprint: 'abc',
}

describe('describeMerge', () => {
  it('names only the kinds that move, in a fixed order', () => {
    expect(describeMerge(PREVIEW, STATES).moves).toEqual([
      { key: 'lines', count: 2, words: '行食譜材料' },
      { key: 'preservation', count: 1, words: '筆保存方式' },
      { key: 'heating', count: 1, words: '筆加熱方式' },
      { key: 'links', count: 1, words: '個連結' },
    ])
  })

  it('words the dropped storage rows and the prose outcomes', () => {
    const words = describeMerge(PREVIEW, STATES)
    expect(words.aliases).toEqual(['蔥', 'scallion'])
    expect(words.dropped).toEqual(['未使用 · 冷藏'])
    expect(words.proseMoved).toEqual(['挑選', '哪裡買'])
    expect(words.proseDropped).toEqual(['說明'])
  })

  it('has empty lists for a merge that only deletes the source', () => {
    const words = describeMerge(
      { moves: {}, new_aliases: [], dropped_preservation: [], prose: {} },
      STATES,
    )
    expect(words).toEqual({ moves: [], aliases: [], dropped: [], proseMoved: [], proseDropped: [] })
  })
})
