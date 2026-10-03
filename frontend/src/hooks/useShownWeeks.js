// The weeks a schedule page shows: the Saturday named by `?week=` (moved to
// its week's Saturday), or this week's, and today's date to mark - both read
// from the browser's own calendar, which is the owner's (lib/schedule.js).
import { useSearchParams } from 'react-router-dom'

import { shownWeek, todayIso } from '../lib/schedule'

export function useShownWeeks() {
  const [params] = useSearchParams()
  const today = todayIso()
  return { start: shownWeek(params.get('week'), today), today }
}
