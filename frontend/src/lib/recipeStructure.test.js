// A recipe's structure through the form and back: what a template body or a
// recipe response holds comes out as the payload that would save it again.
import { describe, expect, it } from 'vitest'

import { emptyStructure, structureFromResponse, structurePayload } from './recipeStructure'

const BODY = {
  servings: '2 人份',
  time: null,
  lines: [{ ingredient: { id: 1, display_name: '薑', needs_detail: false }, sub_dish: null, amount: '1 片', note: null, is_optional: false }],
  line_groups: [
    {
      group: { id: 5, display_name: '主料' },
      name: null,
      display_name: '主料',
      lines: [{ ingredient: null, sub_dish: { id: 7, display_name: '雞高湯', kind: 'sauce' }, amount: null, note: '熱的', is_optional: true }],
    },
    { group: null, name: '醃料', display_name: '醃料', lines: [] },
  ],
  steps: [{ body: '熱鍋', kind: 'step' }],
  step_groups: [{ group: null, name: '收尾', display_name: '收尾', steps: [{ body: '別燒焦', kind: 'note' }] }],
  methods: [{ id: 3, display_name: '炒' }],
  equipment: [{ id: 4, display_name: '炒鍋' }],
}

describe('recipe structure', () => {
  it('reads a body into the form and writes the same structure back', () => {
    expect(structurePayload(structureFromResponse(BODY))).toEqual({
      servings: '2 人份',
      time: null,
      lines: [{ ingredient_id: 1, amount: '1 片', note: null, is_optional: false }],
      line_groups: [
        { line_group_id: 5, lines: [{ sub_dish_id: 7, amount: null, note: '熱的', is_optional: true }] },
        { name: '醃料', lines: [] },
      ],
      steps: [{ body: '熱鍋', kind: 'step' }],
      step_groups: [{ name: '收尾', steps: [{ body: '別燒焦', kind: 'note' }] }],
      method_ids: [3],
      equipment_ids: [4],
    })
  })

  it('starts empty', () => {
    expect(structurePayload(emptyStructure())).toEqual({
      servings: null,
      time: null,
      lines: [],
      line_groups: [],
      steps: [],
      step_groups: [],
      method_ids: [],
      equipment_ids: [],
    })
  })
})
