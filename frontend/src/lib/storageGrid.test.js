import { describe, expect, it } from 'vitest'

import { buildStorageGrid } from './storageGrid'

const STATES = [
  { value: 'unused', label: '未使用' },
  { value: 'opened', label: '已開封' },
  { value: 'cooked', label: '熟食' },
]
const METHODS = ['常溫', '冷藏', '冷凍', '乾燥'].map((m) => ({ value: m, label: m }))

const row = (state, method, min, max, notes = null) => ({
  state,
  method,
  duration_min_days: min,
  duration_max_days: max,
  notes,
})

describe('buildStorageGrid', () => {
  it('keeps only the states and methods in use, in the fixed order', () => {
    const grid = buildStorageGrid(
      [row('cooked', '冷凍', 30, 60), row('unused', '冷藏', 3, 5, '用保鮮膜包')],
      STATES,
      METHODS,
    )
    expect(grid.columns.map((c) => c.value)).toEqual(['冷藏', '冷凍'])
    expect(grid.rows.map((r) => r.label)).toEqual(['未使用', '熟食'])
    expect(grid.rows[0].cells).toEqual([{ days: '3–5 天', notes: '用保鮮膜包' }, null])
    expect(grid.rows[1].cells).toEqual([null, { days: '30–60 天', notes: null }])
  })

  it('shows one number for min = max, and a notes-only cell without days', () => {
    const grid = buildStorageGrid(
      [row('unused', '常溫', 7, 7), row('opened', '常溫', null, null, '看包裝日期')],
      STATES,
      METHODS,
    )
    expect(grid.rows.map((r) => r.cells[0])).toEqual([
      { days: '7 天', notes: null },
      { days: null, notes: '看包裝日期' },
    ])
  })

  it('still shows a value the fixed lists do not know, after the known ones', () => {
    const grid = buildStorageGrid([row('unused', '真空', 10, 20), row('unused', '冷藏', 1, 2)], STATES, METHODS)
    expect(grid.columns.map((c) => c.value)).toEqual(['冷藏', '真空'])
  })

  it('is empty for no rows', () => {
    expect(buildStorageGrid([], STATES, METHODS)).toEqual({ columns: [], rows: [] })
    expect(buildStorageGrid(undefined)).toEqual({ columns: [], rows: [] })
  })
})
