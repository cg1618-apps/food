// Every path out of this module yields one of the two known views, because
// the library picks a layout from the result and has no third branch - media's
// dashboardView tests, per library.
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { DEFAULT_VIEW, libraryViewKey, readLibraryView, writeLibraryView } from './libraryView'

beforeEach(() => localStorage.clear())

afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})

describe('libraryViewKey', () => {
  it('is namespaced to the platform and the app', () => {
    expect(libraryViewKey('recipes')).toBe('cg1618:food:recipes-view')
  })
})

describe('readLibraryView', () => {
  it('defaults to covers when nothing is stored', () => {
    expect(readLibraryView('recipes')).toBe('cover')
  })

  it('reads back a stored view, per library', () => {
    localStorage.setItem(libraryViewKey('ingredients'), 'list')
    expect(readLibraryView('ingredients')).toBe('list')
    expect(readLibraryView('recipes')).toBe('cover')
  })

  it('falls back to covers on a value it does not recognise', () => {
    localStorage.setItem(libraryViewKey('notes'), 'table')
    expect(readLibraryView('notes')).toBe(DEFAULT_VIEW)
  })

  it('falls back to covers when localStorage throws', () => {
    vi.stubGlobal('localStorage', {
      getItem() {
        throw new Error('blocked')
      },
    })
    expect(readLibraryView('recipes')).toBe(DEFAULT_VIEW)
  })
})

describe('writeLibraryView', () => {
  it('stores a known view and returns it', () => {
    expect(writeLibraryView('recipes', 'list')).toBe('list')
    expect(localStorage.getItem(libraryViewKey('recipes'))).toBe('list')
  })

  it('refuses an unknown view and stores nothing', () => {
    expect(writeLibraryView('recipes', 'table')).toBe(DEFAULT_VIEW)
    expect(localStorage.getItem(libraryViewKey('recipes'))).toBe(null)
  })

  it('still returns the view when localStorage throws', () => {
    vi.stubGlobal('localStorage', {
      setItem() {
        throw new Error('quota')
      },
    })
    expect(writeLibraryView('recipes', 'list')).toBe('list')
  })
})
