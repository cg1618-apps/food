import { describe, expect, it } from 'vitest'

import { groupBySection, numberedStepGroups } from './sections'

describe('groupBySection', () => {
  it('groups by first use and keeps each row in its own order', () => {
    const rows = [
      { id: 1, section: null },
      { id: 2, section: '醬汁' },
      { id: 3, section: '主體' },
      { id: 4, section: '醬汁' },
    ]
    expect(groupBySection(rows)).toEqual([
      { section: null, rows: [rows[0]] },
      { section: '醬汁', rows: [rows[1], rows[3]] },
      { section: '主體', rows: [rows[2]] },
    ])
  })

  it('treats a blank or padded section as the same as none or its trimmed name', () => {
    const groups = groupBySection([
      { id: 1, section: '  ' },
      { id: 2 },
      { id: 3, section: ' 醬汁 ' },
      { id: 4, section: '醬汁' },
    ])
    expect(groups.map((g) => [g.section, g.rows.map((r) => r.id)])).toEqual([
      [null, [1, 2]],
      ['醬汁', [3, 4]],
    ])
  })

  it('answers nothing for no rows', () => {
    expect(groupBySection([])).toEqual([])
    expect(groupBySection(undefined)).toEqual([])
  })
})

describe('numberedStepGroups', () => {
  it('numbers through the whole recipe in the order the page shows', () => {
    const groups = numberedStepGroups([
      { id: 1, section: '醬汁', body: 'a' },
      { id: 2, section: '主體', body: 'b' },
      { id: 3, section: '醬汁', body: 'c' },
    ])
    expect(groups.map((g) => [g.section, g.rows.map((s) => [s.id, s.number])])).toEqual([
      ['醬汁', [[1, 1], [3, 2]]],
      ['主體', [[2, 3]]],
    ])
  })
})
