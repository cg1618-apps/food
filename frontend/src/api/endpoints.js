// The single source of URL truth. Import these instead of hardcoding
// '/api/...' strings in components.
//
// WRITE is the browser-side half of app/routing.py's WRITE_PREFIX. Keeping
// every mutation URL in this file means the read/write split is visible in one
// place, and a write accidentally pointed at a public path is a diff here
// rather than a discovery in production.

const API = '/api'
const WRITE = '/api/edit'

export const endpoints = {
  ingredients: {
    list: () => `${API}/ingredients`,
    detail: (id) => `${API}/ingredients/${id}`,
    cascade: (id) => `${API}/ingredients/${id}/cascade`,
    create: () => `${WRITE}/ingredients`,
    update: (id) => `${WRITE}/ingredients/${id}`,
    remove: (id) => `${WRITE}/ingredients/${id}`,
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
  health: () => '/health',
}

export { API, WRITE }
