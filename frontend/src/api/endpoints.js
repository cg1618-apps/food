// The single source of URL truth. Import these instead of hardcoding
// '/api/...' strings in components.
//
// WRITE is the browser-side half of app/routing.py's WRITE_PREFIX. Keeping
// every mutation URL in this file means the read/write split is visible in one
// place, and a write accidentally pointed at a public path is a diff here
// rather than a discovery in production.
//
// Each group's `list()` is also its RESOURCE PREFIX: every read of that
// resource - list, detail, cascade, preview - is a URL under it, which is what
// useApiMutation's `invalidate` matches on. The paths are the backend's, read
// from app/routers/*.py, not recalled.

const API = '/api'
const WRITE = '/api/edit'

// The nine vocabularies the backend builds from one factory
// (app/routers/vocabulary.py) share one URL shape.
function vocabulary(resource) {
  return {
    list: () => `${API}/${resource}`,
    create: () => `${WRITE}/${resource}`,
    update: (id) => `${WRITE}/${resource}/${id}`,
    remove: (id) => `${WRITE}/${resource}/${id}`,
  }
}

export const endpoints = {
  // 料理: a dish or a sauce in general; its recipes are the ways of making it.
  dishes: {
    list: () => `${API}/dishes`,
    detail: (id) => `${API}/dishes/${id}`,
    cascade: (id) => `${API}/dishes/${id}/cascade`,
    create: () => `${WRITE}/dishes`,
    update: (id) => `${WRITE}/dishes/${id}`,
    remove: (id) => `${WRITE}/dishes/${id}`,
    images: (id) => `${WRITE}/dishes/${id}/images`,
  },
  recipes: {
    list: () => `${API}/recipes`,
    detail: (id) => `${API}/recipes/${id}`,
    cascade: (id) => `${API}/recipes/${id}/cascade`,
    create: () => `${WRITE}/recipes`,
    // PATCH; a body of only {status_id} is the in-place status change.
    update: (id) => `${WRITE}/recipes/${id}`,
    remove: (id) => `${WRITE}/recipes/${id}`,
    // PUT [{image_id, focus}] in order: replaces the gallery.
    images: (id) => `${WRITE}/recipes/${id}/images`,
  },
  ingredients: {
    list: () => `${API}/ingredients`,
    detail: (id) => `${API}/ingredients/${id}`,
    cascade: (id) => `${API}/ingredients/${id}/cascade`,
    // GET with ?into=<target id>.
    mergePreview: (id) => `${API}/ingredients/${id}/merge-preview`,
    create: () => `${WRITE}/ingredients`,
    update: (id) => `${WRITE}/ingredients/${id}`,
    remove: (id) => `${WRITE}/ingredients/${id}`,
    // POST {into, fingerprint}; a 409 carries a fresh `preview`.
    merge: (id) => `${WRITE}/ingredients/${id}/merge`,
    images: (id) => `${WRITE}/ingredients/${id}/images`,
    // POST attaches, DELETE detaches one label.
    label: (id, labelId) => `${WRITE}/ingredients/${id}/labels/${labelId}`,
  },
  notes: {
    list: () => `${API}/kitchen-notes`,
    detail: (id) => `${API}/kitchen-notes/${id}`,
    create: () => `${WRITE}/kitchen-notes`,
    update: (id) => `${WRITE}/kitchen-notes/${id}`,
    remove: (id) => `${WRITE}/kitchen-notes/${id}`,
    images: (id) => `${WRITE}/kitchen-notes/${id}/images`,
  },
  // TBD: a standalone page of names and links. Read whole; written one entry
  // at a time, and PUT {ids} saves the order of them all after a drag.
  tbd: {
    list: () => `${API}/tbd`,
    create: () => `${WRITE}/tbd`,
    update: (id) => `${WRITE}/tbd/${id}`,
    remove: (id) => `${WRITE}/tbd/${id}`,
    order: () => `${WRITE}/tbd/order`,
  },
  images: {
    list: () => `${API}/images`,
    detail: (id) => `${API}/images/${id}`,
    // POST multipart, field `file`. 201 for a new image, 200 for one whose
    // checksum already exists.
    upload: () => `${WRITE}/images`,
    remove: (id) => `${WRITE}/images/${id}`,
  },
  // 常用食材: the recipe form's one-tap chips. PUT {ingredient_ids} in order
  // replaces the whole list - add, remove and reorder are each one call.
  commonIngredients: {
    list: () => `${API}/common-ingredients`,
    replace: () => `${WRITE}/common-ingredients`,
  },
  categories: {
    tree: () => `${API}/ingredient-categories`,
    create: () => `${WRITE}/ingredient-categories`,
    update: (id) => `${WRITE}/ingredient-categories/${id}`,
    remove: (id) => `${WRITE}/ingredient-categories/${id}`,
  },
  labels: {
    list: () => `${API}/labels`,
    create: () => `${WRITE}/labels`,
    update: (id) => `${WRITE}/labels/${id}`,
    remove: (id) => `${WRITE}/labels/${id}`,
  },
  courses: vocabulary('recipe-courses'),
  // 地區: where a dish comes from.
  regions: vocabulary('regions'),
  statuses: vocabulary('recipe-statuses'),
  platforms: vocabulary('source-platforms'),
  methods: vocabulary('cooking-methods'),
  equipment: vocabulary('equipment'),
  // A source's author; listed by name, and grown by the recipe form too.
  authors: vocabulary('authors'),
  // The groups a recipe's ingredient lines (材料分組) and steps (步驟分組)
  // are picked from; a recipe may also name a group of its own.
  lineGroups: vocabulary('line-groups'),
  stepGroups: vocabulary('step-groups'),
  vocabularies: {
    // Every closed list with its display label: preservation methods and
    // states, ratings, dish kinds, note kinds, step kinds.
    fixed: () => `${API}/vocabularies/fixed`,
  },
  // GET under the gated prefix: 204 when Access let the request through, and
  // with ?next=/edit/... a redirect back to that page after a sign-in. See
  // api/session.js.
  session: () => `${WRITE}/session`,
  health: () => '/health',
}

export { API, WRITE }
