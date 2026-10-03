import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { checkEditSession, goSignIn, SIGN_IN_RETRY_MS, signInUrl } from './session'

beforeEach(() => {
  window.sessionStorage.clear()
})

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('signInUrl', () => {
  it('asks the session probe to return to the page, query string included', () => {
    expect(signInUrl('/edit/recipes/3?tab=steps')).toBe(
      '/api/edit/session?next=%2Fedit%2Frecipes%2F3%3Ftab%3Dsteps',
    )
  })
})

describe('checkEditSession', () => {
  it('reads a manual redirect as signed out', async () => {
    const fetchMock = vi.fn(async () => ({
      type: 'opaqueredirect',
      ok: false,
      status: 0,
    }))
    vi.stubGlobal('fetch', fetchMock)
    expect(await checkEditSession()).toBe('signed-out')
    // Without `redirect: 'manual'` the browser would chase the login itself
    // and fail; the option is the whole mechanism.
    expect(fetchMock.mock.calls[0][0]).toBe('/api/edit/session')
    expect(fetchMock.mock.calls[0][1].redirect).toBe('manual')
  })

  it('reads a 204 as signed in', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(null, { status: 204 })),
    )
    expect(await checkEditSession()).toBe('signed-in')
  })

  it('does not guess when the probe itself fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => {
        throw new TypeError('Failed to fetch')
      }),
    )
    expect(await checkEditSession()).toBe('unknown')
  })
})

describe('goSignIn', () => {
  function stubLocation() {
    const assign = vi.fn()
    vi.stubGlobal('location', { ...window.location, assign })
    return assign
  }

  it('navigates the whole page to the probe', () => {
    const assign = stubLocation()
    expect(goSignIn('/edit/settings', 1_000_000)).toBe(true)
    expect(assign).toHaveBeenCalledWith('/api/edit/session?next=%2Fedit%2Fsettings')
  })

  it('refuses a second redirect straight after the first, so it cannot loop', () => {
    const assign = stubLocation()
    goSignIn('/edit/settings', 1_000_000)
    expect(goSignIn('/edit/settings', 1_000_000 + SIGN_IN_RETRY_MS - 1)).toBe(false)
    expect(assign).toHaveBeenCalledTimes(1)
  })

  it('tries again once the guard has lapsed', () => {
    const assign = stubLocation()
    goSignIn('/edit/settings', 1_000_000)
    expect(goSignIn('/edit/settings', 1_000_000 + SIGN_IN_RETRY_MS)).toBe(true)
    expect(assign).toHaveBeenCalledTimes(2)
  })
})
