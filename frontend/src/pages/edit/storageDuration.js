// The storage form has one "days" box, which edits the maximum. The minimum is
// loaded and sent back, but there is no control for it, so it must follow the
// maximum where the two were stored as one number (the i2storage migration
// copied every old duration into both ends) or the save is a 422 about a field
// the user cannot see.
export function reconcileMinDays({ loadedMin, loadedMax, editedMax }) {
  const max = editedMax === '' || editedMax == null ? null : Number(editedMax)
  if (loadedMin == null) return null
  if (loadedMin === loadedMax) return max
  if (max !== null && loadedMin > max) return null
  return loadedMin
}
