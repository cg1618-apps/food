import { describe, expect, it } from 'vitest'

import {
  countActive,
  parseFilters,
  parseSearch,
  serializeFilters,
  toApiParams,
  toggleValue,
  withSearch,
} from './urlFilters'

const SPEC = {
  category: { type: 'single', api: 'category_id' },
  course: { type: 'multi', api: 'course_id' },
  stub: { type: 'bool', api: 'needs_detail' },
}

const params = (query) => new URLSearchParams(query)

describe('parseFilters', () => {
  it('gives every key its empty shape when the URL says nothing', () => {
    expect(parseFilters(params(''), SPEC)).toEqual({ category: '', course: [], stub: false })
  })

  // The known defect: the ingredient page links to /ingredients?category=3
  // and the library ignored it.
  it('reads a single value, as the detail page links it', () => {
    expect(parseFilters(params('category=3'), SPEC).category).toBe('3')
  })

  it('reads repeated keys as a list, without blanks or duplicates', () => {
    expect(parseFilters(params('course=1&course=&course=2&course=1'), SPEC).course).toEqual([
      '1',
      '2',
    ])
  })

  // A hand-edited `?category=abc` would reach the API as a 422 and blank the
  // library; an id key keeps only whole numbers.
  it('ignores a value that is not an id on an id key', () => {
    const spec = {
      category: { type: 'single', api: 'category_id', id: true },
      course: { type: 'multi', api: 'course_id', id: true },
      creator: { type: 'multi', api: 'creator' },
    }
    expect(parseFilters(params('category=abc&course=2&course=x&course=1.5&creator=阿基師'), spec)).toEqual({
      category: '',
      course: ['2'],
      creator: ['阿基師'],
    })
    expect(parseFilters(params('category=12'), spec).category).toBe('12')
  })

  it('reads a switch as on unless it is absent or says off', () => {
    expect(parseFilters(params('stub=1'), SPEC).stub).toBe(true)
    expect(parseFilters(params('stub=true'), SPEC).stub).toBe(true)
    expect(parseFilters(params('stub=0'), SPEC).stub).toBe(false)
    expect(parseFilters(params('stub=false'), SPEC).stub).toBe(false)
  })
})

describe('serializeFilters', () => {
  it('writes each type and round-trips through parseFilters', () => {
    const values = { category: '3', course: ['1', '2'], stub: true }
    const query = serializeFilters(values, SPEC)
    expect(query.toString()).toBe('category=3&course=1&course=2&stub=1')
    expect(parseFilters(query, SPEC)).toEqual(values)
  })

  it('removes a cleared filter instead of leaving it blank', () => {
    const query = serializeFilters(
      { category: '', course: [], stub: false },
      SPEC,
      params('category=3&course=1&stub=1'),
    )
    expect(query.toString()).toBe('')
  })

  it('keeps the search term and anything else outside the spec', () => {
    const query = serializeFilters(
      { category: '3', course: [], stub: false },
      SPEC,
      params('q=蔥&other=x'),
    )
    expect(query.get('q')).toBe('蔥')
    expect(query.get('other')).toBe('x')
    expect(query.get('category')).toBe('3')
  })
})

describe('the search term', () => {
  it('is read from q', () => {
    expect(parseSearch(params('q=%E8%94%A5'))).toBe('蔥')
    expect(parseSearch(params(''))).toBe('')
  })

  it('is written trimmed, and removed when blank, keeping the filters', () => {
    expect(withSearch(params('category=3'), '  蔥 ').toString()).toBe(
      'category=3&q=%E8%94%A5',
    )
    expect(withSearch(params('category=3&q=x'), '   ').toString()).toBe('category=3')
  })
})

describe('countActive', () => {
  it('counts each multi value, each set single and each switch on', () => {
    expect(countActive({ category: '3', course: ['1', '2'], stub: true }, SPEC)).toBe(4)
    expect(countActive({ category: '', course: [], stub: false }, SPEC)).toBe(0)
  })
})

describe('toggleValue', () => {
  const empty = { category: '', course: [], stub: false }

  it('adds and removes a multi value', () => {
    const on = toggleValue(empty, SPEC, 'course', '2')
    expect(on.course).toEqual(['2'])
    expect(toggleValue(on, SPEC, 'course', '2').course).toEqual([])
  })

  it('sets a single value, replaces it, and clears it when chosen again', () => {
    const three = toggleValue(empty, SPEC, 'category', '3')
    expect(three.category).toBe('3')
    expect(toggleValue(three, SPEC, 'category', '4').category).toBe('4')
    expect(toggleValue(three, SPEC, 'category', '3').category).toBe('')
  })

  it('flips a switch', () => {
    expect(toggleValue(empty, SPEC, 'stub').stub).toBe(true)
  })
})

describe('toApiParams', () => {
  it('renames to the API names and passes a multi as a list', () => {
    expect(
      toApiParams({ category: '3', course: ['1', '2'], stub: true }, SPEC, ' 蔥 '),
    ).toEqual({ q: '蔥', category_id: '3', course_id: ['1', '2'], needs_detail: true })
  })

  // Off is the absence of the filter: needs_detail=false would be "only the
  // finished ones", which no switch on the page means.
  it('sends nothing for an empty filter, and never a switch as false', () => {
    expect(toApiParams({ category: '', course: [], stub: false }, SPEC)).toEqual({})
  })
})
