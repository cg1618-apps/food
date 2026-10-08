// Frontend: the ingredient library's groups - an ingredient and its varieties.
//
// A GROUP is an ingredient with at least one variety (a child by parent_id)
// anywhere in the library. That is read from the whole, unfiltered library,
// never from the filtered result: under 只看主項 the varieties are gone from
// the result, and 雞肉 must still count as a group and still sort on top.
//
// Two shapes are built from it:
//
//   arrangeIngredients - the list, cut into one section per category in the
//     tree's order. Inside a section, a block per group present (the parent,
//     then its varieties depth-first), then groups whose varieties are not in
//     the result, then everything else. A block sits in its PARENT's section
//     even when a variety is filed elsewhere; a variety whose parent is not in
//     the result stands alone in its own category's section.
//   categoryGroupTree - the 分類 sidebar: each category's child categories,
//     then the groups filed under it, each group nesting its sub-groups.
//
// Pure, so the arrangement is tested without rendering a page.
import { flatten } from './tree'

const OTHER = '其他'

/** parent id -> its varieties, in the order `all` lists them. */
function varietiesByParent(all) {
  const map = new Map()
  for (const row of all) {
    if (row.parent_id == null) continue
    if (!map.has(row.parent_id)) map.set(row.parent_id, [])
    map.get(row.parent_id).push(row)
  }
  return map
}

/** id -> how many varieties sit below it, at any depth. Only groups have an entry. */
export function groupSizes(all) {
  const varieties = varietiesByParent(all)
  const sizes = new Map()
  // `seen` guards the walk: the write path refuses a parent cycle, and this
  // only stops a bad row from hanging the page.
  const size = (id, seen) => {
    let total = 0
    for (const child of varieties.get(id) ?? []) {
      if (seen.has(child.id)) continue
      total += 1 + size(child.id, new Set(seen).add(child.id))
    }
    return total
  }
  for (const id of varieties.keys()) sizes.set(id, size(id, new Set([id])))
  return sizes
}

/** Each category's title, a child category carrying its path: 蔬菜 › 葉菜. */
function categoryTitles(categories) {
  const titles = new Map()
  const walk = (nodes, prefix) => {
    for (const node of nodes) {
      const title = prefix ? `${prefix} › ${node.display_name}` : node.display_name
      titles.set(node.id, title)
      walk(node.children ?? [], title)
    }
  }
  walk(categories, '')
  return titles
}

/**
 * `result` is the filtered list, `all` the whole library, `categories` the
 * category tree. Returns [{ key, title, count, entries }], each entry either
 * { kind: 'group', root, members: [{ item, depth }] } or { kind: 'item', item }.
 */
export function arrangeIngredients(result, all, categories = []) {
  const inResult = new Set(result.map((row) => row.id))
  const varieties = varietiesByParent(all)
  const presentVarieties = (id) => (varieties.get(id) ?? []).filter((v) => inResult.has(v.id))

  const titles = categoryTitles(categories)
  const order = flatten(categories).map((node) => node.id)
  const sections = new Map()
  const sectionFor = (categoryId) => {
    const key = titles.has(categoryId) ? categoryId : OTHER
    if (!sections.has(key)) {
      sections.set(key, {
        key: String(key),
        title: titles.get(categoryId) ?? OTHER,
        count: 0,
        blocks: [],
        groups: [],
        rest: [],
      })
    }
    return sections.get(key)
  }

  for (const row of result) {
    if (row.parent_id != null && inResult.has(row.parent_id)) continue
    const section = sectionFor(row.category_id)
    if (presentVarieties(row.id).length) {
      const members = []
      const walk = (id, depth, seen) => {
        for (const child of presentVarieties(id)) {
          if (seen.has(child.id)) continue
          members.push({ item: child, depth })
          walk(child.id, depth + 1, new Set(seen).add(child.id))
        }
      }
      walk(row.id, 1, new Set([row.id]))
      section.blocks.push({ kind: 'group', root: row, members })
      section.count += 1 + members.length
    } else {
      const bucket = varieties.has(row.id) ? section.groups : section.rest
      bucket.push({ kind: 'item', item: row })
      section.count += 1
    }
  }

  const rank = (key) => (key === OTHER ? Infinity : order.indexOf(key))
  return [...sections.entries()]
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([, { key, title, count, blocks, groups, rest }]) => ({
      key,
      title,
      count,
      entries: [...blocks, ...groups, ...rest],
    }))
}

/**
 * The 分類 sidebar's nodes: [{ key, kind, id, label, count, children }].
 * `kind` is 'category' (count: its exact ingredient_count) or 'group'
 * (count: the group's size including itself - what choosing it lists). A
 * top-level group sits under its own category; a group that is itself a
 * variety sits under its parent group.
 */
export function categoryGroupTree(categories = [], all = []) {
  const varieties = varietiesByParent(all)
  const sizes = groupSizes(all)

  const groupNode = (row, seen) => ({
    key: `group:${row.id}`,
    kind: 'group',
    id: row.id,
    label: row.display_name,
    count: 1 + sizes.get(row.id),
    children: (varieties.get(row.id) ?? [])
      .filter((child) => varieties.has(child.id) && !seen.has(child.id))
      .map((child) => groupNode(child, new Set(seen).add(child.id))),
  })

  const topGroups = new Map()
  for (const row of all) {
    if (row.parent_id != null || !varieties.has(row.id)) continue
    if (!topGroups.has(row.category_id)) topGroups.set(row.category_id, [])
    topGroups.get(row.category_id).push(row)
  }

  const categoryNode = (node) => ({
    key: `category:${node.id}`,
    kind: 'category',
    id: node.id,
    label: node.display_name,
    count: node.ingredient_count,
    children: [
      ...(node.children ?? []).map(categoryNode),
      ...(topGroups.get(node.id) ?? []).map((row) => groupNode(row, new Set([row.id]))),
    ],
  })
  return categories.map(categoryNode)
}
