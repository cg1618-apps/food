// Thin wrappers over TanStack Query so that no component builds a query key or
// a fetch call by hand. The cache key is an array of [url, params], which is
// what makes a filter change a refetch rather than a stale render.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { buildUrl, fetchJson, jsonBody } from '../api/client'
import { endpoints } from '../api/endpoints'

export function useApiQuery(url, params, options = {}) {
  return useQuery({
    queryKey: [url, params ?? null],
    queryFn: () => fetchJson(buildUrl(url, params)),
    staleTime: 30_000,
    ...options,
  })
}

/**
 * Whether a cached query's URL is a read of the resource at `prefix`.
 *
 * Whole path segments only: `/api/ingredients` covers `/api/ingredients`,
 * `/api/ingredients?q=...` and `/api/ingredients/3/cascade`, and not a URL
 * that merely begins with the same letters. A bare string prefix would match
 * the day a resource is named after another plus a suffix, and a needless
 * refetch is the kind of over-match nobody notices until a list flickers.
 */
export function isUnderResource(url, prefix) {
  if (typeof url !== 'string') return false
  return url === prefix || url.startsWith(`${prefix}/`) || url.startsWith(`${prefix}?`)
}

/**
 * A mutation that invalidates by RESOURCE, not by one URL.
 *
 * `invalidate` is a list of read prefixes - each group's `list()` in
 * api/endpoints.js. Every cached query whose URL sits under one of them is
 * invalidated: saving an ingredient refreshes its detail page and its cascade
 * counts as well as the list, which invalidating the list URL alone did not.
 * Name every resource whose reads the write changes, e.g. an ingredient save
 * also moves category counts and label counts.
 *
 * Call as `mutation.mutateAsync({ url, body })`; `body` is sent as JSON, or
 * as-is when it is FormData.
 *
 * `onSaved(data, variables)` runs with the response BEFORE the invalidation,
 * for a write whose response is the new state of a read on screen (the
 * recipe's status): put it in the cache, and the page shows it whether or not
 * the refetch that follows succeeds.
 */
export function useApiMutation({ method = 'POST', invalidate = [], onSaved } = {}) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ url, body }) => {
      const payload =
        body === undefined
          ? {}
          : typeof FormData !== 'undefined' && body instanceof FormData
            ? { body }
            : jsonBody(body)
      return fetchJson(url, { method, ...payload })
    },
    onSuccess: (data, variables) => {
      onSaved?.(data, variables, queryClient)
      return invalidateResources(queryClient, invalidate)
    },
  })
}

/**
 * Invalidate every cached read under any of `prefixes`. `options` passes
 * through to TanStack's invalidateQueries - `{ refetchType: 'none' }` marks
 * them stale without refetching what is on screen, for a delete whose own
 * detail and cascade reads would only 404 if refetched before the page leaves.
 */
export function invalidateResources(queryClient, prefixes, options) {
  if (!prefixes.length) return Promise.resolve()
  return queryClient.invalidateQueries(
    {
      predicate: (query) => prefixes.some((prefix) => isUnderResource(query.queryKey[0], prefix)),
    },
    options,
  )
}

/**
 * Every closed list (preservation methods and states, ratings, recipe kinds,
 * note kinds, step kinds), each `[{value, label}]`.
 *
 * Read once per page load: the lists change only with a deploy, so there is
 * nothing to refetch. This is what ends the copies of those lists that used to
 * live in components.
 */
export function useFixedVocabularies() {
  return useApiQuery(endpoints.vocabularies.fixed(), null, {
    staleTime: Infinity,
    gcTime: Infinity,
  })
}

/** The display label of `value` in a fixed list, or the value itself. */
export function fixedLabel(list, value) {
  return list?.find((entry) => entry.value === value)?.label ?? value
}

/**
 * Upload one image file to the library. `mutateAsync(file)` answers the
 * image summary - a new row (201) or the existing one with the same checksum
 * (200), which the caller does not need to tell apart.
 *
 * Several files are several calls; the caller loops, so one bad file fails
 * alone with its own message instead of taking the batch with it.
 */
export function useUpload() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (file) => {
      const form = new FormData()
      form.append('file', file)
      return fetchJson(endpoints.images.upload(), { method: 'POST', body: form })
    },
    onSuccess: () => invalidateResources(queryClient, [endpoints.images.list()]),
  })
}
