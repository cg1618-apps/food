// Frontend: 常用 - the recipe form's one-tap chips above 材料, one per
// 常用食材 (設定), in that list's order.
//
// Tapping one adds a line for that ingredient; what a line is and where it
// goes is the form's, through `onAdd(ingredient)`. A chip whose ingredient is
// already on a line anywhere in the recipe is drawn as used - ticked and
// muted, and named so ("（已在材料中）") for a screen reader - but stays
// tappable, because one ingredient on two lines is a real recipe (蒜 in the
// sauce and again on top).
//
// Nothing at all is drawn while the list is empty: the chips are a shortcut,
// and an empty row of them would only be noise above the lines.
//
//   ingredients  [{ id, display_name, needs_detail }] in order
//   usedIds      Set of ingredient ids already on a line
//   onAdd        (ingredient) => void
import { cx } from '../../lib/cx'

export default function CommonIngredientChips({ ingredients, usedIds, onAdd }) {
  if (!ingredients?.length) return null
  return (
    <div role="group" aria-label="常用食材" className="flex flex-wrap items-center gap-1.5">
      <span aria-hidden="true" className="text-xs text-text-faint">
        常用
      </span>
      {ingredients.map((ingredient) => {
        const name = ingredient.display_name
        const used = usedIds.has(ingredient.id)
        return (
          <button
            key={ingredient.id}
            type="button"
            onClick={() => onAdd(ingredient)}
            aria-label={used ? `加一行「${name}」（已在材料中）` : `加一行「${name}」`}
            data-used={used ? 'true' : undefined}
            title={used ? '已在材料中；點一下再加一行' : '點一下加一行'}
            className={cx(
              'rounded-full border px-2.5 py-0.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand',
              used
                ? 'border-brand/40 bg-brand-soft text-text-muted'
                : 'border-border bg-surface text-text hover:border-border-strong',
            )}
          >
            <span aria-hidden="true">{used ? '✓ ' : '＋ '}</span>
            {name}
          </button>
        )
      })}
    </div>
  )
}
