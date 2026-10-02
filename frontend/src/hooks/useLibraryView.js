// Frontend: a library's 封面 / 清單 choice as React state, remembered per
// library in localStorage by lib/libraryView.js.
import { useCallback, useState } from 'react'

import { readLibraryView, writeLibraryView } from '../lib/libraryView'

export function useLibraryView(library) {
  const [view, setView] = useState(() => readLibraryView(library))
  const choose = useCallback(
    (next) => setView(writeLibraryView(library, next)),
    [library],
  )
  return [view, choose]
}
