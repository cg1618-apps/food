// Frontend: Celsius to Fahrenheit, for the heating table.
//
// Temperatures are stored in °C only; °F is computed for display, so there is
// one number to edit and nothing to drift out of step. A reference recipe
// written in °F is converted when it is entered, not stored twice.

/** °C -> °F, rounded to a whole degree; null for anything not a number. */
export function toFahrenheit(celsius) {
  if (celsius === null || celsius === undefined || celsius === '') return null
  const value = Number(celsius)
  if (!Number.isFinite(value)) return null
  // Math.round(-0.4) is -0; normalise so the display never reads "-0".
  return Math.round((value * 9) / 5 + 32) + 0
}

/** "180°C / 356°F", or just the Celsius when there is nothing to convert. */
export function formatTemperature(celsius) {
  const fahrenheit = toFahrenheit(celsius)
  if (fahrenheit === null) return null
  return `${Number(celsius)}°C / ${fahrenheit}°F`
}
