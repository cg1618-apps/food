import { describe, expect, it } from 'vitest'

import { arrangeIngredients, categoryGroupTree, groupSizes } from './ingredientGroups'

// 蔬菜 has a child category 葉菜. 雞肉 > 雞腿 > 去骨雞腿 is two levels deep;
// 辣椒 (蔬菜) has a variety filed elsewhere, 乾辣椒 (乾貨). A category's count
// is the API's ingredient_count, exact, as the sidebar has always shown it.
const CATEGORIES = [
  { id: 1, display_name: '肉類', ingredient_count: 5, children: [] },
  {
    id: 2,
    display_name: '蔬菜',
    ingredient_count: 1,
    children: [{ id: 3, display_name: '葉菜', ingredient_count: 1, children: [] }],
  },
  { id: 4, display_name: '乾貨', ingredient_count: 1, children: [] },
]
const row = (id, name, category_id, parent_id = null) => ({ id, display_name: name, category_id, parent_id })
const CHICKEN = row(10, '雞肉', 1)
const THIGH = row(11, '雞腿', 1, 10)
const BONELESS = row(12, '去骨雞腿', 1, 11)
const BREAST = row(13, '雞胸肉', 1, 10)
const BACON = row(14, '培根', 1)
const CHILLI = row(20, '辣椒', 2)
const DRIED = row(21, '乾辣椒', 4, 20)
const CABBAGE = row(22, '高麗菜', 3)
const ALL = [BACON, BONELESS, DRIED, CABBAGE, CHICKEN, BREAST, THIGH, CHILLI]

const shape = (sections) =>
  sections.map((s) => [
    s.title,
    s.count,
    s.entries.map((e) =>
      e.kind === 'group'
        ? [e.root.display_name, e.members.map((m) => `${m.depth}:${m.item.display_name}`)]
        : e.item.display_name,
    ),
  ])

describe('groupSizes', () => {
  it('counts every variety below an ingredient, at any depth', () => {
    const sizes = groupSizes(ALL)
    expect(sizes.get(10)).toBe(3)
    expect(sizes.get(11)).toBe(1)
    expect(sizes.get(20)).toBe(1)
    expect(sizes.has(14)).toBe(false)
  })
})

describe('arrangeIngredients', () => {
  it('sections by category in tree order, groups first, varieties under their parent', () => {
    expect(shape(arrangeIngredients(ALL, ALL, CATEGORIES))).toEqual([
      // Varieties keep the order the API listed them in.
      ['肉類', 5, [['雞肉', ['1:雞胸肉', '1:雞腿', '2:去骨雞腿']], '培根']],
      ['蔬菜', 2, [['辣椒', ['1:乾辣椒']]]],
      ['蔬菜 › 葉菜', 1, ['高麗菜']],
    ])
  })

  // 只看主項: the varieties are gone from the result, but 雞肉 is still a
  // group in the library and still sorts above 培根.
  it('keeps a group on top when its varieties are filtered out', () => {
    const tops = [BACON, CABBAGE, CHICKEN, CHILLI]
    expect(shape(arrangeIngredients(tops, ALL, CATEGORIES))).toEqual([
      ['肉類', 2, ['雞肉', '培根']],
      ['蔬菜', 1, ['辣椒']],
      ['蔬菜 › 葉菜', 1, ['高麗菜']],
    ])
  })

  // The category filter is exact: 乾貨 alone holds 乾辣椒 without its parent,
  // so it stands on its own in its own section.
  it('lets a variety whose parent is not in the result stand alone', () => {
    expect(shape(arrangeIngredients([DRIED], ALL, CATEGORIES))).toEqual([['乾貨', 1, ['乾辣椒']]])
  })

  it('puts a row whose category is not in the tree last rather than dropping it', () => {
    const stray = row(30, '鹽', 99)
    expect(shape(arrangeIngredients([stray, BACON], [...ALL, stray], CATEGORIES))).toEqual([
      ['肉類', 1, ['培根']],
      ['其他', 1, ['鹽']],
    ])
  })
})

describe('categoryGroupTree', () => {
  it('lists the groups filed under each category, nested by parent, after its child categories', () => {
    const tree = categoryGroupTree(CATEGORIES, ALL)
    const walk = (nodes) => nodes.map((n) => [n.key, n.label, n.count, walk(n.children)])
    expect(walk(tree)).toEqual([
      ['category:1', '肉類', 5, [['group:10', '雞肉', 4, [['group:11', '雞腿', 2, []]]]]],
      ['category:2', '蔬菜', 1, [['category:3', '葉菜', 1, []], ['group:20', '辣椒', 2, []]]],
      ['category:4', '乾貨', 1, []],
    ])
  })
})
