// Frontend: 上週 / 本週 / 下週 - moving the schedule a week at a time.
//
// Shared by /schedule and /edit/schedule: `base` is the page's path, and the
// week travels as `?week=` (the Saturday), so a week is a link that can be
// opened, bookmarked and come back to. 本週 drops the parameter rather than
// naming today's Saturday, so the bookmark of it stays "this week".
//
// `locked` - the edit page with a day not yet saved - draws the three as
// disabled buttons, so moving away cannot throw the typing away unseen.
import { addDays, shownWeek, WEEK_DAYS } from '../../lib/schedule'
import { Button, LinkButton } from '../ui/primitives'

const LABELS = ['← 上週', '本週', '下週 →']

export default function WeekNav({ base, start, today, locked = false }) {
  const thisWeek = shownWeek(null, today)
  if (locked) {
    return (
      <nav aria-label="週次" className="flex flex-wrap items-center gap-2">
        {LABELS.map((label) => (
          <Button key={label} size="sm" disabled title="先儲存這幾天再換週">
            {label}
          </Button>
        ))}
      </nav>
    )
  }
  return (
    <nav aria-label="週次" className="flex flex-wrap items-center gap-2">
      <LinkButton size="sm" to={`${base}?week=${addDays(start, -WEEK_DAYS)}`}>
        ← 上週
      </LinkButton>
      <LinkButton
        size="sm"
        to={base}
        aria-current={start === thisWeek ? 'page' : undefined}
        className="aria-[current=page]:border-brand aria-[current=page]:text-brand"
      >
        本週
      </LinkButton>
      <LinkButton size="sm" to={`${base}?week=${addDays(start, WEEK_DAYS)}`}>
        下週 →
      </LinkButton>
    </nav>
  )
}
