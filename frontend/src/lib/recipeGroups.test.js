import { describe, expect, it } from 'vitest'

import { lineBlocks, stepBlocks } from './recipeGroups'

const group = (id, name, inner, rows) => ({ id, position: 0, group: null, name, display_name: name, [inner]: rows })

describe('lineBlocks', () => {
  it('puts the ungrouped lines first without a heading, then each group under its name', () => {
    const recipe = {
      lines: [{ id: 1 }],
      line_groups: [group(5, '醬汁', 'lines', [{ id: 2 }, { id: 3 }]), group(6, '空', 'lines', [])],
    }
    expect(lineBlocks(recipe).map((b) => [b.heading, b.rows.map((r) => r.id)])).toEqual([
      [null, [1]],
      ['醬汁', [2, 3]],
    ])
  })

  it('answers nothing for a recipe with no lines', () => {
    expect(lineBlocks({ lines: [], line_groups: [] })).toEqual([])
    expect(lineBlocks({})).toEqual([])
  })
})

describe('stepBlocks', () => {
  it('numbers through the whole recipe in the order the page shows', () => {
    const recipe = {
      steps: [{ id: 1 }],
      step_groups: [group(5, '備料', 'steps', [{ id: 2 }, { id: 3 }]), group(6, '烹飪', 'steps', [{ id: 4 }])],
    }
    expect(stepBlocks(recipe).map((b) => [b.heading, b.rows.map((s) => [s.id, s.number])])).toEqual([
      [null, [[1, 1]]],
      ['備料', [[2, 2], [3, 3]]],
      ['烹飪', [[4, 4]]],
    ])
  })
})

describe('stepBlocks with kinds', () => {
  it('numbers only ordinary steps, skipping optional steps and notes across groups', () => {
    const recipe = {
      steps: [{ id: 1, kind: 'note' }, { id: 2, kind: 'step' }],
      step_groups: [
        group(5, '備料', 'steps', [{ id: 3, kind: 'optional' }, { id: 4, kind: 'step' }]),
        group(6, '烹飪', 'steps', [{ id: 5 }, { id: 6, kind: 'note' }, { id: 7, kind: 'step' }]),
      ],
    }
    expect(stepBlocks(recipe).flatMap((b) => b.rows.map((s) => [s.id, s.number]))).toEqual([
      [1, null],
      [2, 1],
      [3, null],
      [4, 2],
      [5, 3],
      [6, null],
      [7, 4],
    ])
  })
})
