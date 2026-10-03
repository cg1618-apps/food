// Frontend: 「貼上多行」 - a block of pasted text as recipe steps.
//
// A recipe copied from a page or a video description arrives as one block,
// usually already numbered. Each non-blank line is a step, and the numbering
// is stripped because the page numbers steps itself: a stored "1." would read
// "1. 1. 切菜" and go wrong the moment a step is moved.

// Leading markers, in the shapes recipes are actually written in:
//   1.  1)  1、 1：  (1)  （1）  ①..⑳  一、 二. 十二、  第一步 第3步  Step 1:
//   and bullets - * • ・
const NUMBERING = new RegExp(
  [
    '^\\s*(?:',
    [
      '(?:step|STEP|Step)\\s*\\d+\\s*[:：.．、)）-]?',
      '第\\s*[0-9一二三四五六七八九十百]+\\s*步\\s*[:：.．、)）]?',
      '[(（]\\s*[0-9一二三四五六七八九十]+\\s*[)）]',
      '\\d+\\s*[.．、:：)）]',
      '[一二三四五六七八九十]+\\s*[、.．:：)）]',
      '[\\u2460-\\u2473\\u2776-\\u277f]',
      '[-*•・]',
    ].join('|'),
    ')\\s*',
  ].join(''),
)

/** One line without its leading number or bullet, trimmed. */
export function stripNumbering(line) {
  return String(line).replace(NUMBERING, '').trim()
}

/** Pasted text -> step bodies: one per non-blank line, numbering stripped. */
export function splitSteps(text) {
  return String(text ?? '')
    .split(/\r?\n/)
    .map(stripNumbering)
    .filter(Boolean)
}

// A step's kind (STEP_KINDS on the server, served as `step_kinds`): an
// ordinary `step`, an `optional` one, or a `note` among the steps. Only an
// ordinary step is numbered - a step with no kind is one - so the number
// counts the steps a cook must do, and an optional step or a note sits in the
// order without one.
export const STEP = 'step'
export const NOTE = 'note'
export const OPTIONAL = 'optional'

/** Whether a step takes a number. */
export const isNumbered = (step) => (step.kind ?? STEP) === STEP

/** The numbers a list of steps is shown with, in order: 1..n over the
 * ordinary steps, null for the rest. */
export function stepNumbers(steps) {
  let number = 0
  return steps.map((step) => (isNumbered(step) ? ++number : null))
}
