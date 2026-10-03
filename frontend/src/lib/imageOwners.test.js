import { describe, expect, it } from 'vitest'

import { formatBytes, ownerHref, ownerKind } from './imageOwners'

describe('ownerHref and ownerKind', () => {
  it.each([
    ['ingredient', '/ingredients/4', '食材'],
    ['dish', '/dishes/4', '料理'],
    ['recipe', '/recipes/4', '食譜'],
    ['kitchen_note', '/notes/4', '筆記'],
  ])('%s', (type, href, kind) => {
    expect(ownerHref({ type, id: 4 })).toBe(href)
    expect(ownerKind(type)).toBe(kind)
  })

  it('does not invent a page for an unknown type', () => {
    expect(ownerHref({ type: 'menu', id: 1 })).toBeNull()
    expect(ownerKind('menu')).toBe('menu')
  })
})

describe('formatBytes', () => {
  it('picks the unit', () => {
    expect(formatBytes(820)).toBe('820 B')
    expect(formatBytes(14540)).toBe('14.2 KB')
    expect(formatBytes(1363149)).toBe('1.3 MB')
    expect(formatBytes(null)).toBeNull()
  })
})
