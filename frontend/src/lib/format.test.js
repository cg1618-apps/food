import { describe, expect, it } from 'vitest'

import { formatDays, linkHost } from './format'

describe('formatDays', () => {
  it('shows a range, or one number when the ends agree or one is missing', () => {
    expect(formatDays({ min: 3, max: 5 })).toBe('3–5 天')
    expect(formatDays({ min: 4, max: 4 })).toBe('4 天')
    expect(formatDays({ min: null, max: 7 })).toBe('7 天')
    expect(formatDays({ min: 2, max: null })).toBe('2 天')
  })

  it('is null when there is no range', () => {
    expect(formatDays(null)).toBe(null)
    expect(formatDays({ min: null, max: null })).toBe(null)
  })
})

describe('linkHost', () => {
  it('shows the host without www', () => {
    expect(linkHost('https://www.youtube.com/watch?v=x')).toBe('youtube.com')
    expect(linkHost('https://icook.tw/recipes/1')).toBe('icook.tw')
  })

  it('is null for no link and the raw text for one that does not parse', () => {
    expect(linkHost(null)).toBe(null)
    expect(linkHost('not a url')).toBe('not a url')
  })
})
