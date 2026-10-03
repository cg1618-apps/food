// The row reducer every list editor uses, and the small field helpers.
import { describe, expect, it } from 'vitest'

import { integerOrNull, keyed, numberOrNull, rowsReducer, splitAliases } from './rowList'

const rows = (...names) => names.map((name) => keyed({ name }))
const namesOf = (list) => list.map((row) => row.name)

describe('rowsReducer', () => {
  it('adds a row with a key', () => {
    const next = rowsReducer([], { type: 'add', row: { name: 'a' } })
    expect(namesOf(next)).toEqual(['a'])
    expect(next[0]._key).toBeTruthy()
  })

  it('inserts several, each keyed distinctly', () => {
    const next = rowsReducer(rows('a'), { type: 'insert', rows: [{ name: 'b' }, { name: 'c' }] })
    expect(namesOf(next)).toEqual(['a', 'b', 'c'])
    expect(new Set(next.map((row) => row._key)).size).toBe(3)
  })

  it('updates one row and leaves the others the same objects', () => {
    const before = rows('a', 'b')
    const next = rowsReducer(before, { type: 'update', index: 1, patch: { name: 'B' } })
    expect(namesOf(next)).toEqual(['a', 'B'])
    expect(next[0]).toBe(before[0])
    expect(next[1]._key).toBe(before[1]._key)
  })

  it('removes by index', () => {
    expect(namesOf(rowsReducer(rows('a', 'b', 'c'), { type: 'remove', index: 1 }))).toEqual(['a', 'c'])
  })

  it('moves a row to where it was dropped, carrying the key with it', () => {
    const before = rows('a', 'b', 'c', 'd')
    const up = rowsReducer(before, { type: 'move', from: 3, to: 1 })
    expect(namesOf(up)).toEqual(['a', 'd', 'b', 'c'])
    expect(up[1]._key).toBe(before[3]._key)
    expect(namesOf(rowsReducer(before, { type: 'move', from: 0, to: 2 }))).toEqual(['b', 'c', 'a', 'd'])
  })

  it('does not wrap a move off either end', () => {
    const before = rows('a', 'b')
    expect(rowsReducer(before, { type: 'move', from: 0, to: -1 })).toBe(before)
    expect(rowsReducer(before, { type: 'move', from: 1, to: 2 })).toBe(before)
  })

  it('refuses an unknown action loudly', () => {
    expect(() => rowsReducer([], { type: 'shuffle' })).toThrow(/shuffle/)
  })
})

describe('small field helpers', () => {
  it('reads an empty number input as null, not 0', () => {
    expect(numberOrNull('')).toBeNull()
    expect(numberOrNull('  ')).toBeNull()
    expect(numberOrNull('180')).toBe(180)
  })

  it('reads an integer field as an integer, or null when blank or not a number', () => {
    expect(integerOrNull('')).toBeNull()
    expect(integerOrNull('abc')).toBeNull()
    expect(integerOrNull('180')).toBe(180)
    expect(integerOrNull('180.4')).toBe(180)
  })

  it('splits aliases on every comma the keyboard offers and drops repeats', () => {
    expect(splitAliases('薑, ginger，老薑、Ginger,,')).toEqual(['薑', 'ginger', '老薑'])
  })
})
