import { describe, expect, it } from 'vitest'

import { endpoints, WRITE } from './endpoints'

// Cloudflare Access gates a PATH PREFIX. A mutation URL that does not start
// with it is a publicly writable endpoint, and nothing in the browser would say
// so - the request simply succeeds. The backend asserts the same invariant over
// its route table; this is that invariant on the side where the URL is chosen.
describe('every write URL sits under the gated prefix', () => {
  const writes = [
    endpoints.ingredients.create(),
    endpoints.ingredients.update(1),
    endpoints.ingredients.remove(1),
    endpoints.categories.create(),
    endpoints.categories.update(1),
    endpoints.categories.remove(1),
    endpoints.labels.create(),
    endpoints.labels.update(1),
    endpoints.labels.remove(1),
  ]

  it.each(writes)('%s', (url) => {
    expect(url.startsWith(WRITE)).toBe(true)
  })

  it('has writes to check at all', () => {
    // Without this the block above is vacuous on an empty list.
    expect(writes.length).toBeGreaterThanOrEqual(9)
  })
})

describe('read URLs stay public', () => {
  it.each([
    endpoints.ingredients.list(),
    endpoints.ingredients.detail(1),
    endpoints.categories.tree(),
    endpoints.labels.list(),
  ])('%s', (url) => {
    expect(url.startsWith(WRITE)).toBe(false)
    expect(url.startsWith('/api/')).toBe(true)
  })
})
