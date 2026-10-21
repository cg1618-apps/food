// Frontend: a recipe's structure - servings, time, its lines and steps in
// their groups, its methods and equipment - between the API and a form.
//
// Used by the recipe form both to load the recipe it edits and to prefill a
// new recipe copied from another, so one reader serves both. Form
// state is lib/groupedRows.js's for the lines and steps, lib/recipeLines.js's
// rows inside them, and lib/steps.js's step rows.
import { emptyGrouped, groupsFromResponse, groupsPayload } from './groupedRows'
import { lineFromResponse, linesPayload } from './recipeLines'
import { blankToNull } from './rowList'
import { stepRow, stepsPayload } from './steps'

export const emptyStructure = () => ({
  servings: '',
  time: '',
  // { ungrouped, groups } each (lib/groupedRows.js).
  lines: emptyGrouped(),
  steps: emptyGrouped(),
  method_ids: [],
  equipment_ids: [],
})

const ids = (refs) => (refs ?? []).map((ref) => ref.id)

/** A recipe response -> the form's structure fields. */
export function structureFromResponse(row) {
  return {
    servings: row.servings ?? '',
    time: row.time ?? '',
    lines: {
      ungrouped: (row.lines ?? []).map(lineFromResponse),
      groups: groupsFromResponse(row.line_groups, 'lines', lineFromResponse),
    },
    steps: {
      ungrouped: (row.steps ?? []).map(stepRow),
      groups: groupsFromResponse(row.step_groups, 'steps', stepRow),
    },
    method_ids: ids(row.methods),
    equipment_ids: ids(row.equipment),
  }
}

/**
 * The form's structure fields -> their payload: lines with line_groups and
 * steps with step_groups, the pairs the server replaces together. Throws the
 * sentence for a line typed and never picked, or a group with no name.
 */
export function structurePayload(form) {
  return {
    servings: blankToNull(form.servings),
    time: blankToNull(form.time),
    lines: linesPayload(form.lines.ungrouped),
    line_groups: groupsPayload(form.lines, {
      idField: 'line_group_id',
      inner: 'lines',
      what: '材料分組',
      rowsPayload: linesPayload,
    }),
    steps: stepsPayload(form.steps.ungrouped),
    step_groups: groupsPayload(form.steps, {
      idField: 'step_group_id',
      inner: 'steps',
      what: '步驟分組',
      rowsPayload: stepsPayload,
    }),
    method_ids: form.method_ids,
    equipment_ids: form.equipment_ids,
  }
}
