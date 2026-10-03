// The grouped list a recipe's 材料 and 步驟 are edited as: rows move within a
// group and across groups, a removed group's rows survive in the ungrouped
// area, and the payload names each group by its 設定 value or its name.
import { describe, expect, it } from 'vitest'

import {
  UNGROUPED,
  containerIds,
  flatRows,
  groupedReducer,
  groupsFromResponse,
  groupsPayload,
  newGroup,
  setRows,
  startOf,
  updateRowByKey,
  valueNamed,
} from './groupedRows'

const row = (key) => ({ _key: key, text: key })

function sample() {
  return {
    ungrouped: [row('a')],
    groups: [
      { _key: 'g1', groupId: 5, name: '備料', rows: [row('b'), row('c')] },
      { _key: 'g2', groupId: null, name: '收尾', rows: [row('d')] },
    ],
  }
}

const keys = (state) => [
  state.ungrouped.map((r) => r._key),
  ...state.groups.map((g) => [g._key, g.rows.map((r) => r._key)]),
]

describe('groupedReducer', () => {
  it('moves a row within its group', () => {
    const next = groupedReducer(sample(), {
      type: 'moveRow',
      from: { container: 'g1', index: 1 },
      to: { container: 'g1', index: 0 },
    })
    expect(keys(next)).toEqual([['a'], ['g1', ['c', 'b']], ['g2', ['d']]])
  })

  it('moves a row across groups to the place it is dropped at', () => {
    const next = groupedReducer(sample(), {
      type: 'moveRow',
      from: { container: UNGROUPED, index: 0 },
      to: { container: 'g1', index: 1 },
    })
    expect(keys(next)).toEqual([[], ['g1', ['b', 'a', 'c']], ['g2', ['d']]])
  })

  it('moves a row into an empty group, and past the end of one to its end', () => {
    const state = groupedReducer(sample(), { type: 'addGroup', group: newGroup({ name: '空' }) })
    const empty = state.groups[2]._key
    const into = groupedReducer(state, {
      type: 'moveRow',
      from: { container: 'g2', index: 0 },
      to: { container: empty, index: 0 },
    })
    expect(into.groups.map((g) => g.rows.map((r) => r._key))).toEqual([['b', 'c'], [], ['d']])
    const end = groupedReducer(sample(), {
      type: 'moveRow',
      from: { container: 'g2', index: 0 },
      to: { container: 'g1', index: 99 },
    })
    expect(end.groups[0].rows.map((r) => r._key)).toEqual(['b', 'c', 'd'])
  })

  it('removes a group and moves its rows to the end of the ungrouped rows', () => {
    const next = groupedReducer(sample(), { type: 'removeGroup', key: 'g1' })
    expect(keys(next)).toEqual([['a', 'b', 'c'], ['g2', ['d']]])
  })

  it('reorders groups, renames one and adds one', () => {
    let state = groupedReducer(sample(), { type: 'moveGroup', from: 1, to: 0 })
    expect(state.groups.map((g) => g._key)).toEqual(['g2', 'g1'])
    state = groupedReducer(state, { type: 'updateGroup', key: 'g2', patch: { name: '擺盤' } })
    expect(state.groups[0]).toMatchObject({ name: '擺盤', groupId: null })
    state = groupedReducer(state, { type: 'addGroup', group: { groupId: 7, name: '烹飪' } })
    expect(state.groups[2]).toMatchObject({ groupId: 7, name: '烹飪', rows: [] })
    expect(state.groups[2]._key).toBeTruthy()
    expect(groupedReducer(state, { type: 'moveGroup', from: 0, to: 5 })).toBe(state)
  })

  it('applies a row action to one container', () => {
    const next = groupedReducer(sample(), {
      type: 'rows',
      container: 'g2',
      action: { type: 'insert', rows: [{ text: 'e' }] },
    })
    expect(next.groups[1].rows.map((r) => r.text)).toEqual(['d', 'e'])
  })
})

describe('the grouped list', () => {
  it('lists containers and numbers rows through every group in display order', () => {
    const state = sample()
    expect(containerIds(state)).toEqual([UNGROUPED, 'g1', 'g2'])
    expect(flatRows(state).map((r) => r._key)).toEqual(['a', 'b', 'c', 'd'])
    expect([UNGROUPED, 'g1', 'g2'].map((c) => startOf(state, c))).toEqual([0, 1, 3])
  })

  it('replaces one container and patches a row wherever it is', () => {
    expect(setRows(sample(), 'g2', []).groups[1].rows).toEqual([])
    expect(updateRowByKey(sample(), 'c', { text: 'C' }).groups[0].rows[1].text).toBe('C')
  })

  it('finds the 設定 value a typed name names, trimmed and in any case', () => {
    const values = [{ id: 1, display_name: '醬汁', name_cn: '醬汁', name_en: 'Sauce' }]
    expect(valueNamed(values, ' sauce ')?.id).toBe(1)
    expect(valueNamed(values, '醬汁')?.id).toBe(1)
    expect(valueNamed(values, '醃料')).toBeNull()
  })

  it('sends each group as its value or its name, with its rows numbered on', () => {
    const seen = []
    const payload = groupsPayload(sample(), {
      idField: 'step_group_id',
      inner: 'steps',
      what: '步驟分組',
      rowsPayload: (rows, start) => {
        seen.push(start)
        return rows.map((r) => ({ body: r.text }))
      },
    })
    expect(payload).toEqual([
      { step_group_id: 5, steps: [{ body: 'b' }, { body: 'c' }] },
      { name: '收尾', steps: [{ body: 'd' }] },
    ])
    expect(seen).toEqual([1, 3])
  })

  it('refuses a group left without a name', () => {
    const state = { ungrouped: [], groups: [newGroup({ name: '  ' })] }
    expect(() =>
      groupsPayload(state, { idField: 'line_group_id', inner: 'lines', what: '材料分組', rowsPayload: () => [] }),
    ).toThrow(/第 1 個材料分組還沒有名稱/)
  })

  it('reads a response group back as its value or its name', () => {
    const groups = groupsFromResponse(
      [
        { id: 1, group: { id: 5, display_name: '備料' }, name: null, display_name: '備料', steps: [{ body: 'x' }] },
        { id: 2, group: null, name: '收尾', display_name: '收尾', steps: [] },
      ],
      'steps',
      (step) => ({ body: step.body }),
    )
    expect(groups.map(({ groupId, name, rows }) => ({ groupId, name, rows: rows.map((r) => r.body) }))).toEqual([
      { groupId: 5, name: '備料', rows: ['x'] },
      { groupId: null, name: '收尾', rows: [] },
    ])
  })
})
