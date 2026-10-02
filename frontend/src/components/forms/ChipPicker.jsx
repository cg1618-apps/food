// Frontend: choose any number from a short vocabulary - labels, methods,
// equipment, serves-as.
//
// Toggle chips rather than checkboxes or a multi-select: the lists are short,
// a chip is a large target on a phone, and the chosen ones read at a glance.
// Each is a button with aria-pressed, the library filters' shape.
//
//   options   [{ id, display_name }] - a vocabulary list as the API serves it
//   value     [ids]
//   onChange  (nextIds) => void
//   label     the group's accessible name
//   empty     shown when the vocabulary has nothing in it yet
import { cx } from '../../lib/cx'

export default function ChipPicker({ options, value, onChange, label, empty = '還沒有可選的項目。' }) {
  const chosen = new Set(value)
  if (!options?.length) return <p className="text-sm text-text-faint">{empty}</p>
  return (
    <div role="group" aria-label={label} className="flex flex-wrap gap-1.5">
      {options.map((option) => {
        const pressed = chosen.has(option.id)
        return (
          <button
            key={option.id}
            type="button"
            aria-pressed={pressed}
            onClick={() =>
              onChange(pressed ? value.filter((id) => id !== option.id) : [...value, option.id])
            }
            className={cx(
              'rounded-full border px-2.5 py-0.5 text-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand',
              pressed
                ? 'border-brand/40 bg-brand-soft text-brand'
                : 'border-border bg-surface text-text-muted hover:border-border-strong hover:text-text',
            )}
          >
            {option.display_name}
          </button>
        )
      })}
    </div>
  )
}
