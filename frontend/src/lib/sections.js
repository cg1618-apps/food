// Frontend: a recipe's lines and steps as the page reads them - grouped by
// section, steps numbered.
//
// Sections are free text on each row (lib/recipeLines.js's sectionsOf offers
// them back in the form). The page shows one block per section in the order
// the sections are first used, rows keeping their own order inside it, so a
// section that was split by a later edit - 醬汁, 主體, 醬汁 - still reads as
// one block rather than two with the same heading.

const sectionKey = (row) => {
  const section = typeof row.section === 'string' ? row.section.trim() : ''
  return section || null
}

/**
 * Rows grouped by section, in first-use order:
 * `[{ section: string | null, rows }]`. Rows with no section are one group
 * whose `section` is null - the page draws it without a heading.
 */
export function groupBySection(rows) {
  const groups = new Map()
  for (const row of rows ?? []) {
    const key = sectionKey(row)
    if (!groups.has(key)) groups.set(key, [])
    groups.get(key).push(row)
  }
  return [...groups].map(([section, grouped]) => ({ section, rows: grouped }))
}

/**
 * Steps grouped by section, each carrying `number`: counted through the whole
 * recipe in the order the page shows them, so 「第 5 步」 names one step even
 * when the sections are headed separately.
 */
export function numberedStepGroups(steps) {
  let number = 0
  return groupBySection(steps).map((group) => ({
    ...group,
    rows: group.rows.map((step) => ({ ...step, number: ++number })),
  }))
}
