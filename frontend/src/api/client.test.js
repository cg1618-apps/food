import { describe, expect, it } from 'vitest'

import { buildUrl, errorMessage } from './client'

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
})
