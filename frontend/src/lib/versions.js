// Frontend: the "other versions" of a recipe, as one list.
//
// The API answers two fields (app/services/recipes.py, `versions`): an
// original carries its versions in `versions` and no `variant_of`; a version
// carries its original in `variant_of` and the original's OTHER versions in
// `versions`. The page shows the family in one place, original first, so a
// reader on any member can reach every other.

/** `[{ id, display_name, kind, original }]` - empty when there is no family. */
export function otherVersions(recipe) {
  if (!recipe) return []
  const out = []
  const seen = new Set([recipe.id])
  if (recipe.variant_of && !seen.has(recipe.variant_of.id)) {
    seen.add(recipe.variant_of.id)
    out.push({ ...recipe.variant_of, original: true })
  }
  for (const version of recipe.versions ?? []) {
    if (seen.has(version.id)) continue
    seen.add(version.id)
    out.push({ ...version, original: false })
  }
  return out
}
