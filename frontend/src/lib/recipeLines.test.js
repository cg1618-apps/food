// Recipe lines between the form and the API: one target each, no type field.
import { describe, expect, it } from 'vitest'

import {
  emptyLine,
  isStub,
  lineFromResponse,
  linesPayload,
  newNames,
  targetFromOption,
} from './recipeLines'

describe('recipe lines', () => {
  it('reads both kinds of saved line back as targets', () => {
    const ing = lineFromResponse({
      ingredient: { id: 3, display_name: '薑', needs_detail: true },
      sub_recipe: null,
      amount: '1 片',
      note: null,
      is_optional: true,
    })
    expect(ing).toMatchObject({
      target: { type: 'ingredient', id: 3, needsDetail: true },
      amount: '1 片',
      note: '',
      is_optional: true,
    })
    const sub = lineFromResponse({ ingredient: null, sub_recipe: { id: 9, display_name: '高湯', kind: 'base' } })
    expect(sub.target).toMatchObject({ type: 'recipe', id: 9, kind: 'base' })
  })

  it('sends exactly one target per line and no type field', () => {
    const lines = [
      { ...emptyLine(), target: targetFromOption({ type: 'ingredient', id: 3, label: '薑' }), amount: ' 1 片 ' },
      { ...emptyLine(), target: targetFromOption({ type: 'recipe', id: 9, label: '高湯' }) },
      { ...emptyLine(), target: targetFromOption({ type: 'new', label: '紫蘇' }), is_optional: true },
    ]
    expect(linesPayload(lines)).toEqual([
      { amount: '1 片', note: null, is_optional: false, ingredient_id: 3 },
      { amount: null, note: null, is_optional: false, sub_recipe_id: 9 },
      { amount: null, note: null, is_optional: true, new_ingredient: { name_cn: '紫蘇' } },
    ])
  })

  it('files a typed Latin name as English and a Han one as Chinese', () => {
    expect(newNames(' shiso ')).toEqual({ name_en: 'shiso' })
    expect(newNames('紫蘇 leaf')).toEqual({ name_cn: '紫蘇 leaf' })
  })

  it('drops an entirely blank line but refuses one with an amount and no choice', () => {
    expect(linesPayload([emptyLine()])).toEqual([])
    expect(() => linesPayload([emptyLine(), { ...emptyLine(), amount: '2 匙' }])).toThrow(/第 2 行/)
    // Inside a group, numbered through the lines shown before it.
    expect(() => linesPayload([{ ...emptyLine(), amount: '2 匙' }], 3)).toThrow(/第 4 行/)
  })

  // Text typed into a line's search box and never picked is not a blank line:
  // dropping it would save the recipe without an ingredient the cook named.
  it('refuses a line whose name was typed but never picked', () => {
    expect(() => linesPayload([{ ...emptyLine(), pending: '紫蘇' }])).toThrow(/第 1 行.*還沒選/)
    expect(linesPayload([{ ...emptyLine(), pending: '   ' }])).toEqual([])
  })

  it('marks a 新增 target and a saved stub as stubs', () => {
    expect(isStub({ type: 'new', label: 'x' })).toBe(true)
    expect(isStub({ type: 'ingredient', id: 1, needsDetail: true })).toBe(true)
    expect(isStub({ type: 'ingredient', id: 1, needsDetail: false })).toBe(false)
    expect(isStub(null)).toBe(false)
  })
})
