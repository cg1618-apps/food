// Frontend: 常用 - the recipe form's one-tap chips above 材料, one per
// 常用食材 (未來固定設定), in that structure's order: 未分組 first, then each group
// under its own heading.
//
// Headings appear only when they tell chips apart: while the chips are all
// in one place - all ungrouped, which is how the list reads with no group at
// all - the row is the single 「常用」 row it always was. A group with no
// chips is not drawn; there is nothing in it to tap.
//
// Tapping a chip adds a line for that ingredient; what a line is and where it
// goes is the form's, through `onAdd(ingredient)`, and a group here is no
// 材料分組 there. A chip whose ingredient is already on a line anywhere in the
// recipe is drawn as used - ticked and muted, and named so ("（已在材料中）")
// for a screen reader - but stays tappable, because one ingredient on two
// lines is a real recipe (蒜 in the sauce and again on top).
//
// Nothing at all is drawn while there are no chips: they are a shortcut, and
// an empty row of them would only be noise above the lines.
//
//   common   { ungrouped: [ingredient], groups: [{ id, name, ingredients }] },
//            each ingredient { id, display_name, needs_detail }
//   usedIds  Set of ingredient ids already on a line
//   onAdd    (ingredient) => void
import { cx } from '../../lib/cx'

const UNGROUPED_TITLE = '未分組'

function Chip({ ingredient, used, onAdd }) {
  const name = ingredient.display_name
  return (
    <button
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
}

export default function CommonIngredientChips({ common, usedIds, onAdd }) {
  const sections = [
    { key: 'ungrouped', title: UNGROUPED_TITLE, ingredients: common?.ungrouped ?? [] },
    ...(common?.groups ?? []).map((group) => ({ key: `group-${group.id}`, title: group.name, ingredients: group.ingredients })),
  ].filter((section) => section.ingredients.length)
  if (!sections.length) return null

  const chips = (ingredients) =>
    ingredients.map((ingredient) => (
      <Chip key={ingredient.id} ingredient={ingredient} used={usedIds.has(ingredient.id)} onAdd={onAdd} />
    ))

  if (sections.length === 1 && sections[0].key === 'ungrouped') {
    return (
      <div role="group" aria-label="常用食材" className="flex flex-wrap items-center gap-1.5">
        <span aria-hidden="true" className="text-xs text-text-faint">
          常用
        </span>
        {chips(sections[0].ingredients)}
      </div>
    )
  }

  return (
    <div role="group" aria-label="常用食材" className="space-y-1.5">
      {sections.map((section) => (
        <div key={section.key} role="group" aria-label={section.title} className="flex flex-wrap items-center gap-1.5">
          <span aria-hidden="true" className="text-xs text-text-faint">
            {section.title}
          </span>
          {chips(section.ingredients)}
        </div>
      ))}
    </div>
  )
}
