import { describe, expect, it } from 'vitest'

import { authorFromOption, sourceRow, sourcesPayload } from './recipeSources'

const first = () => '12'

describe('recipe sources', () => {
  it('reads a saved source into a row with its author picked', () => {
    const row = sourceRow({
      platform: { id: 4, display_name: '書' },
      author: { id: 3, display_name: '阿基師' },
      url: null,
      title: '家常菜',
    })
    expect(row).toMatchObject({
      platform_id: '4',
      author: { type: 'author', id: 3, label: '阿基師' },
      pendingAuthor: '',
      url: '',
      title: '家常菜',
    })
  })

  it('sends a picked author by id, a new one by name in its slot, and none as null', () => {
    const rows = [
      { ...sourceRow(), author: authorFromOption({ type: 'item', id: 3, label: '阿基師' }) },
      { ...sourceRow(), author: authorFromOption({ type: 'new', label: ' Babish ' }) },
      { ...sourceRow(), author: authorFromOption({ type: 'new', label: '詹姆士' }) },
      { ...sourceRow(), title: ' 家常菜 ' },
    ]
    expect(sourcesPayload(rows, first)).toEqual([
      { platform_id: 12, author_id: 3, url: null, title: null },
      { platform_id: 12, new_author: { name_en: 'Babish' }, url: null, title: null },
      { platform_id: 12, new_author: { name_cn: '詹姆士' }, url: null, title: null },
      { platform_id: 12, author_id: null, url: null, title: '家常菜' },
    ])
  })

  it('drops a blank row but refuses one whose author was typed and not picked', () => {
    expect(sourcesPayload([sourceRow()], first)).toEqual([])
    const typed = [sourceRow(), { ...sourceRow(), pendingAuthor: '詹姆士', title: 'x' }]
    expect(() => sourcesPayload(typed, first)).toThrow(/第 2 個來源.*詹姆士/)
    // Typed text alone is not blank either.
    expect(() => sourcesPayload([{ ...sourceRow(), pendingAuthor: '詹' }], first)).toThrow(/第 1 個來源/)
  })
})
