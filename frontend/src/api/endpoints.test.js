import { describe, expect, it } from 'vitest'

import { endpoints, WRITE } from './endpoints'

// Cloudflare Access gates a PATH PREFIX. A mutation URL that does not start
// with it is a publicly writable endpoint, and nothing in the browser would say
// so - the request simply succeeds. The backend asserts the same invariant over
// its route table; this is that invariant on the side where the URL is chosen.
//
// Every endpoint is found by walking the object rather than listed by hand,
// and every key must be classified as a read or a write below - so a new
// endpoint cannot be added without this test deciding which side it is on.
const WRITE_KEYS = new Set(['create', 'update', 'remove', 'images', 'merge', 'label', 'upload'])
const READ_KEYS = new Set([
  'list',
  'detail',
  'cascade',
  'creators',
  'mergePreview',
  'tree',
  'fixed',
])

function collect(node, path = []) {
  return Object.entries(node).flatMap(([key, value]) =>
    typeof value === 'function'
      ? [{ name: [...path, key].join('.'), key, url: value(1, 2) }]
      : collect(value, [...path, key]),
  )
}

const all = collect(endpoints).filter((entry) => entry.name !== 'health')
const writes = all.filter((entry) => WRITE_KEYS.has(entry.key))
const reads = all.filter((entry) => READ_KEYS.has(entry.key))

describe('endpoint classification', () => {
  it('classifies every endpoint as a read or a write', () => {
    const unknown = all.filter((e) => !WRITE_KEYS.has(e.key) && !READ_KEYS.has(e.key))
    expect(unknown.map((e) => e.name)).toEqual([])
  })

  it('has writes and reads to check at all', () => {
    // Without this the blocks below are vacuous on an empty list.
    expect(writes.length).toBeGreaterThanOrEqual(30)
    expect(reads.length).toBeGreaterThanOrEqual(15)
  })
})

describe('every write URL sits under the gated prefix', () => {
  it.each(writes.map((e) => [e.name, e.url]))('%s -> %s', (_name, url) => {
    expect(url.startsWith(`${WRITE}/`)).toBe(true)
  })
})

describe('read URLs stay public', () => {
  it.each(reads.map((e) => [e.name, e.url]))('%s -> %s', (_name, url) => {
    expect(url.startsWith(WRITE)).toBe(false)
    expect(url.startsWith('/api/')).toBe(true)
  })
})

describe('paths the backend actually serves', () => {
  // The ones easiest to get wrong from memory: a resource whose URL is not
  // its name, and the routes added beside the plain CRUD.
  it.each([
    [endpoints.notes.list(), '/api/kitchen-notes'],
    [endpoints.recipes.creators(), '/api/recipe-creators'],
    [endpoints.courses.list(), '/api/recipe-courses'],
    [endpoints.methods.update(4), '/api/edit/cooking-methods/4'],
    [endpoints.equipment.remove(5), '/api/edit/equipment/5'],
    [endpoints.ingredients.mergePreview(7), '/api/ingredients/7/merge-preview'],
    [endpoints.ingredients.merge(7), '/api/edit/ingredients/7/merge'],
    [endpoints.ingredients.label(7, 2), '/api/edit/ingredients/7/labels/2'],
    [endpoints.images.upload(), '/api/edit/images'],
    [endpoints.vocabularies.fixed(), '/api/vocabularies/fixed'],
  ])('%s', (actual, expected) => {
    expect(actual).toBe(expected)
  })
})
