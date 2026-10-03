// Frontend: what DeleteDialog needs to know about each kind of row.
//
// Kept apart from the component so the dialog file exports only a component
// (fast refresh), and so a new kind of row is one entry here.
import { endpoints } from '../api/endpoints'

// Per kind: where its counts and its delete are, which counts the delete
// echoes (the router's query parameters, read from app/routers/*.py) and how
// each is worded, which cascade keys BLOCK rather than cascade, and which
// reads the delete makes stale.
export const DELETE_TARGETS = {
  recipe: {
    noun: '食譜',
    group: endpoints.recipes,
    library: '/recipes',
    counts: [
      ['aliases', '個別名'],
      ['sources', '個來源'],
      ['lines', '行材料'],
      ['steps', '個步驟'],
    ],
    blockers: [['used_in', (n) => `有 ${n} 道食譜把它當材料用，要先從那些食譜拿掉才能刪除。`]],
    invalidate: [
      endpoints.recipes.list(),
      endpoints.authors.list(),
      endpoints.ingredients.list(),
      endpoints.labels.list(),
      endpoints.courses.list(),
      endpoints.methods.list(),
      endpoints.equipment.list(),
      endpoints.images.list(),
    ],
  },
  ingredient: {
    noun: '食材',
    group: endpoints.ingredients,
    library: '/ingredients',
    counts: [
      ['aliases', '個別名'],
      ['preservation', '筆保存方式'],
      ['heating', '筆加熱方式'],
      ['links', '個連結'],
    ],
    blockers: [
      ['children', (n) => `底下還有 ${n} 個品種，要先移走或刪除它們。`],
      ['recipes', (n) => `有 ${n} 道食譜直接用到它，要先在那些食譜換掉，或把它合併到別的食材。`],
    ],
    invalidate: [
      endpoints.ingredients.list(),
      // A deleted ingredient leaves 常用食材 (ON DELETE CASCADE).
      endpoints.commonIngredients.list(),
      endpoints.categories.tree(),
      endpoints.labels.list(),
      endpoints.recipes.list(),
      endpoints.methods.list(),
      endpoints.images.list(),
    ],
  },
  note: {
    noun: '筆記',
    group: endpoints.notes,
    library: '/notes',
    counts: [],
    blockers: [],
    invalidate: [endpoints.notes.list(), endpoints.labels.list(), endpoints.images.list()],
  },
}
