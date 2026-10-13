// Frontend: a merge preview (GET /api/ingredients/{id}/merge-preview) in words.
//
// The preview is computed by the same function the merge runs, so what this
// says is what will happen: which rows move, which names become aliases,
// which storage rows the target already has and so drops, which prose
// fields move (the target's is empty) or are dropped (the target has its own),
// the same for the source's homemade version (自製版), and how many recipe
// alternatives the merge drops because they would repeat their line or
// another alternative of it.

const MOVE_WORDS = [
  ['lines', '行食譜材料'],
  ['alternatives', '個食譜替代'],
  ['children', '個品種'],
  ['preservation', '筆保存方式'],
  ['heating', '筆加熱方式'],
  ['links', '個連結'],
  ['labels', '個標籤'],
  ['images', '張圖片'],
]

export const PROSE_WORDS = {
  description: '說明',
  selection_notes: '挑選',
  sourcing_notes: '哪裡買',
  preservation_notes: '保存備註',
}

const label = (list, value) => list?.find((item) => item.value === value)?.label ?? value

/**
 * `{ moves: [{ key, count, words }], aliases, dropped: [text],
 * droppedAlternatives, proseMoved, proseDropped, homemade }`, every list
 * empty when there is nothing of its kind; `homemade` is 'moved', 'dropped'
 * or null (the source has none).
 * `states` is the fixed preservation states, for 未使用 rather than `unused`.
 */
export function describeMerge(preview, states) {
  if (!preview) return null
  const moves = MOVE_WORDS.filter(([key]) => preview.moves?.[key] > 0).map(([key, words]) => ({
    key,
    count: preview.moves[key],
    words,
  }))
  const prose = Object.entries(preview.prose ?? {})
  const proseNamed = (outcome) =>
    prose.filter(([, value]) => value === outcome).map(([field]) => PROSE_WORDS[field] ?? field)
  return {
    moves,
    aliases: preview.new_aliases ?? [],
    dropped: (preview.dropped_preservation ?? []).map(
      (row) => `${label(states, row.state)} · ${row.method}`,
    ),
    droppedAlternatives: preview.dropped_alternatives ?? 0,
    proseMoved: proseNamed('moved'),
    proseDropped: proseNamed('dropped'),
    homemade: preview.homemade_dish ?? null,
  }
}
