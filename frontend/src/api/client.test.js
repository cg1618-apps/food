import { afterEach, describe, expect, it, vi } from 'vitest'

import { buildUrl, errorMessage, fetchJson, jsonBody, SIGN_IN_MESSAGE } from './client'

describe('errorMessage', () => {
  it('reads a plain detail string', () => {
    expect(errorMessage({ detail: 'That name is taken.' }, 'x')).toBe('That name is taken.')
  })

  // The defect this wrapper exists not to have: FastAPI's automatic validation
  // error is an array, and the naive version renders it as "[object Object]" -
  // for the one error a malformed body actually produces.
  it('joins the array FastAPI produces for a validation error', () => {
    const body = {
      detail: [
        { loc: ['body', 'category_id'], msg: 'Input should be a valid integer' },
        { loc: ['body', 'name_cn'], msg: 'Field required' },
      ],
    }
    expect(errorMessage(body, 'x')).toBe(
      'category_id: Input should be a valid integer; name_cn: Field required',
    )
  })

  it('falls back when there is nothing usable', () => {
    expect(errorMessage(null, 'Server error')).toBe('Server error')
    expect(errorMessage({ detail: [] }, 'Server error')).toBe('Server error')
  })
})

describe('buildUrl', () => {
  it('drops empty values rather than sending blank filters', () => {
    expect(buildUrl('/api/ingredients', { q: '', category_id: 3, label_id: null })).toBe(
      '/api/ingredients?category_id=3',
    )
  })

  it('keeps false, which is a real filter value', () => {
    // needs_detail=false means "only the finished ones" and must survive.
    expect(buildUrl('/api/ingredients', { needs_detail: false })).toBe(
      '/api/ingredients?needs_detail=false',
    )
  })

  // FastAPI reads a list[int] query parameter from a repeated key; a joined
  // "1,2" is a 422.
  it('repeats the key for an array, dropping its empty members', () => {
    expect(buildUrl('/api/recipes', { course_id: [1, 2], status: [], kind: ['', null] })).toBe(
      '/api/recipes?course_id=1&course_id=2',
    )
  })
})

describe('fetchJson request headers', () => {
  afterEach(() => vi.unstubAllGlobals())

  function stubFetch() {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: 1 }), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)
    return fetchMock
  }

  it('sends JSON with a JSON content type', async () => {
    const fetchMock = stubFetch()
    await fetchJson('/api/edit/labels', { method: 'POST', ...jsonBody({ name_cn: '辣' }) })
    expect(fetchMock.mock.calls[0][1].headers['Content-Type']).toBe('application/json')
  })

  // An upload with a forced JSON content type is a body the server cannot
  // parse; the browser has to write the multipart boundary itself.
  it('leaves the content type to the browser for FormData', async () => {
    const fetchMock = stubFetch()
    const form = new FormData()
    form.append('file', new Blob(['x']), 'x.jpg')
    await fetchJson('/api/edit/images', { method: 'POST', body: form })
    const { headers, body } = fetchMock.mock.calls[0][1]
    expect(body).toBe(form)
    expect(Object.keys(headers).map((k) => k.toLowerCase())).not.toContain('content-type')
  })

  it('attaches status and body to a failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ detail: 'In use.', usage_count: 3 }), { status: 409 })),
    )
    await expect(fetchJson('/api/edit/equipment/1', { method: 'DELETE' })).rejects.toMatchObject({
      message: 'In use.',
      status: 409,
      body: { usage_count: 3 },
    })
  })
})

// Access answers a signed-out write with a redirect to its login on another
// origin. Followed, that dies as a bare "Failed to fetch"; not followed, it is
// an opaqueredirect, which is readable and means exactly one thing here.
describe('fetchJson and the Access sign-in', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('does not follow redirects under the gated prefix', async () => {
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }))
    vi.stubGlobal('fetch', fetchMock)
    await fetchJson('/api/edit/ingredient-categories', { method: 'POST' })
    expect(fetchMock.mock.calls[0][1].redirect).toBe('manual')
  })

  // The mirror: a public read keeps the browser's default, so a redirect the
  // server means (a trailing slash) is still followed rather than read as a
  // sign-in.
  it('leaves public reads to follow redirects as usual', async () => {
    const fetchMock = vi.fn(async () => new Response('[]', { status: 200 }))
    vi.stubGlobal('fetch', fetchMock)
    await fetchJson('/api/ingredient-categories')
    expect(fetchMock.mock.calls[0][1]).not.toHaveProperty('redirect')
  })

  it('turns the redirect into a 401 that says what to do', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ type: 'opaqueredirect', ok: false, status: 0 })))
    await expect(
      fetchJson('/api/edit/ingredient-categories', { method: 'POST' }),
    ).rejects.toMatchObject({ status: 401, signInRequired: true, message: SIGN_IN_MESSAGE })
  })
})
