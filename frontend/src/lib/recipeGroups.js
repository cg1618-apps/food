// Frontend: a recipe's lines and steps as its page reads them - in their
// groups, steps numbered.
//
// The API sends the ungrouped rows as `lines` / `steps` and each group with
// its own rows in `line_groups` / `step_groups`, in order. The page shows the
// ungrouped rows first, without a heading, then one block per group under its
// name. A group with nothing in it has nothing to read and is left out.

import { stepNumbers } from './steps'

function blocks(ungrouped, groups, inner) {
  const out = []
  if (ungrouped?.length) out.push({ key: 'ungrouped', heading: null, rows: ungrouped })
  for (const group of groups ?? []) {
    const rows = group[inner] ?? []
    if (rows.length) out.push({ key: `group-${group.id}`, heading: group.display_name, rows })
  }
  return out
}

/** `[{ key, heading: string | null, rows }]` for a recipe's lines. */
export function lineBlocks(recipe) {
  return blocks(recipe.lines, recipe.line_groups, 'lines')
}

/**
 * The same for its steps, each step carrying `number`: counted through the
 * whole recipe in the order the page shows them, so 「第 5 步」 names one step
 * even when the groups are headed separately. Only an ordinary step is
 * counted; an optional step or a note carries `number: null`
 * (lib/steps.js).
 */
export function stepBlocks(recipe) {
  const out = blocks(recipe.steps, recipe.step_groups, 'steps')
  const numbers = stepNumbers(out.flatMap((block) => block.rows))
  let index = 0
  return out.map((block) => ({
    ...block,
    rows: block.rows.map((step) => ({ ...step, number: numbers[index++] })),
  }))
}
