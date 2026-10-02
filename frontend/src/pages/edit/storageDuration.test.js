import { describe, expect, it } from 'vitest'
import { reconcileMinDays } from './storageDuration'

describe('reconcileMinDays', () => {
  it('keeps min equal to max when a migrated row has its max lowered', () => {
    expect(reconcileMinDays({ loadedMin: 7, loadedMax: 7, editedMax: '5' })).toBe(5)
  })

  it('clears min when a min = max row has its max cleared', () => {
    expect(reconcileMinDays({ loadedMin: 7, loadedMax: 7, editedMax: '' })).toBeNull()
  })

  it('drops min when max is lowered below a distinct min', () => {
    expect(reconcileMinDays({ loadedMin: 5, loadedMax: 10, editedMax: '3' })).toBeNull()
  })

  it('keeps a distinct min when max is raised', () => {
    expect(reconcileMinDays({ loadedMin: 5, loadedMax: 10, editedMax: '14' })).toBe(5)
  })

  it('sends null for a new row', () => {
    expect(reconcileMinDays({ loadedMin: null, loadedMax: null, editedMax: '4' })).toBeNull()
  })
})
