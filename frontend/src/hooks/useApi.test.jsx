import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { endpoints } from '../api/endpoints'
import { fixedLabel, isUnderResource, useApiMutation, useUpload } from './useApi'

describe('isUnderResource', () => {
  it.each([
    ['/api/ingredients', true],
    ['/api/ingredients/3', true],
    ['/api/ingredients/3/cascade', true],
    ['/api/ingredients?q=x', true],
    ['/api/ingredient-categories', false],
    ['/api/ingredientsx', false],
    [undefined, false],
  ])('%s under /api/ingredients is %s', (url, expected) => {
    expect(isUnderResource(url, '/api/ingredients')).toBe(expected)
  })
})

describe('fixedLabel', () => {
  const statuses = [{ value: 'can_cook', label: '可煮' }]
  it('finds the label, or falls back to the value', () => {
    expect(fixedLabel(statuses, 'can_cook')).toBe('可煮')
    expect(fixedLabel(statuses, 'other')).toBe('other')
    expect(fixedLabel(undefined, 'x')).toBe('x')
  })
})

function harness() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }) => <QueryClientProvider client={client}>{children}</QueryClientProvider>
  return { client, wrapper }
}

function seed(client, urls) {
  for (const url of urls) client.setQueryData([url, null], { url })
}

function invalidated(client, url) {
  return client.getQueryState([url, null]).isInvalidated
}

describe('useApiMutation invalidates by resource', () => {
  afterEach(() => vi.unstubAllGlobals())

  // The stale-detail defect: invalidating the list URL alone left the detail
  // page and the cascade counts showing the values from before the save. The
  // unrelated resource is seeded too, so a green here proves the predicate
  // chose - not that everything was invalidated.
  it('refreshes every read under the prefix and nothing else', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ id: 3 }), { status: 200 })))
    const { client, wrapper } = harness()
    const touched = [
      endpoints.ingredients.list(),
      endpoints.ingredients.detail(3),
      endpoints.ingredients.cascade(3),
    ]
    const untouched = [endpoints.categories.tree(), endpoints.recipes.list()]
    seed(client, [...touched, ...untouched])

    const { result } = renderHook(
      () => useApiMutation({ method: 'PATCH', invalidate: [endpoints.ingredients.list()] }),
      { wrapper },
    )
    await act(() => result.current.mutateAsync({ url: endpoints.ingredients.update(3), body: {} }))

    for (const url of touched) expect(invalidated(client, url)).toBe(true)
    for (const url of untouched) expect(invalidated(client, url)).toBe(false)
  })
})

describe('useUpload', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('posts the file as multipart to the upload URL and refreshes the image library', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ id: 9 }), { status: 201 }))
    vi.stubGlobal('fetch', fetchMock)
    const { client, wrapper } = harness()
    seed(client, [endpoints.images.list(), endpoints.recipes.list()])

    const { result } = renderHook(() => useUpload(), { wrapper })
    const file = new File(['bytes'], 'dish.jpg', { type: 'image/jpeg' })
    let saved
    await act(async () => {
      saved = await result.current.mutateAsync(file)
    })

    expect(saved).toEqual({ id: 9 })
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe(endpoints.images.upload())
    expect(init.method).toBe('POST')
    expect(init.body.get('file')).toBeInstanceOf(File)
    await waitFor(() => expect(invalidated(client, endpoints.images.list())).toBe(true))
    expect(invalidated(client, endpoints.recipes.list())).toBe(false)
  })
})
