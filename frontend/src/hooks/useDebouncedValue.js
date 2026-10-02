// Frontend: a value that follows another after it has stopped changing.
//
// One request per keystroke is one too many (media debounces its searches the
// same way, at 250 ms); the typeahead searches with this.
import { useEffect, useState } from 'react'

export function useDebouncedValue(value, delay = 250) {
  const [settled, setSettled] = useState(value)
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), delay)
    return () => clearTimeout(timer)
  }, [value, delay])
  return settled
}
