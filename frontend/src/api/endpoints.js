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

// The six vocabularies the backend builds from one factory
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
  images: {
    list: () => `${API}/images`,
    detail: (id) => `${API}/images/${id}`,
    // POST multipart, field `file`. 201 for a new image, 200 for one whose
    // checksum already exists.
    upload: () => `${WRITE}/images`,
    remove: (id) => `${WRITE}/images/${id}`,
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
  statuses: vocabulary('recipe-statuses'),
  platforms: vocabulary('source-platforms'),
  methods: vocabulary('cooking-methods'),
  equipment: vocabulary('equipment'),
  // A source's author; listed by name, and grown by the recipe form too.
  authors: vocabulary('authors'),
  vocabularies: {
    // Every closed list with its display label: preservation methods and
    // states, ratings, recipe kinds, note kinds.
    fixed: () => `${API}/vocabularies/fixed`,
  },
  // GET under the gated prefix: 204 when Access let the request through, and
  // with ?next=/edit/... a redirect back to that page after a sign-in. See
  // api/session.js.
  session: () => `${WRITE}/session`,
  health: () => '/health',
}

export { API, WRITE }
