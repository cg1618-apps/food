import { describe, expect, it } from 'vitest'

import { focusStyle, formatFocus, parseFocus } from './images'

describe('focusStyle', () => {
  it('sets object-position for a focus', () => {
    expect(focusStyle('30% 70%')).toEqual({ objectPosition: '30% 70%' })
  })

  it('is undefined for a centred image, so no style attribute is written', () => {
    expect(focusStyle(null)).toBeUndefined()
    expect(focusStyle('')).toBeUndefined()
  })
})

describe('parseFocus', () => {
  it('reads "X% Y%"', () => {
    expect(parseFocus('12% 88%')).toEqual({ x: 12, y: 88 })
    expect(parseFocus('  0%   100% ')).toEqual({ x: 0, y: 100 })
  })

  it('clamps past 100', () => {
    expect(parseFocus('150% 999%')).toEqual({ x: 100, y: 100 })
  })

  it.each([null, undefined, '', '50 50', '50%', 'left top', 42])(
    'treats %s as the centre',
    (value) => {
      expect(parseFocus(value)).toEqual({ x: 50, y: 50 })
    },
  )
})

describe('formatFocus', () => {
  it('writes whole clamped percentages', () => {
    expect(formatFocus({ x: 12.4, y: 120 })).toBe('12% 100%')
    expect(formatFocus({ x: -5, y: 33.6 })).toBe('0% 34%')
  })

  it('stores the centre as null', () => {
    expect(formatFocus({ x: 50, y: 50 })).toBeNull()
    expect(formatFocus({ x: 49.8, y: 50.2 })).toBeNull()
  })

  it('round-trips through parseFocus', () => {
    expect(formatFocus(parseFocus('25% 75%'))).toBe('25% 75%')
  })
})
