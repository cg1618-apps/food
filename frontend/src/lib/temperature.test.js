import { describe, expect, it } from 'vitest'

import { formatTemperature, toFahrenheit } from './temperature'

describe('toFahrenheit', () => {
  it.each([
    [0, 32],
    [100, 212],
    [180, 356],
    [-40, -40],
    [37, 99], // 98.6 rounds up
    ['200', 392], // a form field hands over a string
  ])('%s°C is %s°F', (celsius, fahrenheit) => {
    expect(toFahrenheit(celsius)).toBe(fahrenheit)
  })

  it('never answers -0', () => {
    expect(Object.is(toFahrenheit(-17.9), -0)).toBe(false)
  })

  it.each([null, undefined, '', 'hot', NaN])('is null for %s', (value) => {
    expect(toFahrenheit(value)).toBeNull()
  })
})

describe('formatTemperature', () => {
  it('shows both scales', () => {
    expect(formatTemperature(180)).toBe('180°C / 356°F')
  })

  it('is null when there is no temperature', () => {
    expect(formatTemperature(null)).toBeNull()
  })
})
