// Thin wrappers over TanStack Query so that no component builds a query key or
// a fetch call by hand. The cache key is an array of [url, params], which is
// what makes a filter change a refetch rather than a stale render.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { buildUrl, fetchJson, jsonBody } from '../api/client'

export function useApiQuery(url, params, options = {}) {
  return useQuery({
    queryKey: [url, params ?? null],
    queryFn: () => fetchJson(buildUrl(url, params)),
    staleTime: 30_000,
    ...options,
  })
}

export function useApiMutation({ method = 'POST', invalidate = [] } = {}) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ url, body }) =>
      fetchJson(url, { method, ...(body === undefined ? {} : jsonBody(body)) }),
    onSuccess: () => {
      for (const key of invalidate) {
        queryClient.invalidateQueries({ queryKey: [key] })
      }
    },
  })
}
