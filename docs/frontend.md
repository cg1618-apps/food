# Frontend

React + Vite, react-router, TanStack Query, Tailwind v4. The conventions are
`media`'s, per the platform's house-style section; what is written here is what
is specific to food.

## Pages

Navigation is 食譜 · 食材 · 筆記 · 設定: a top bar on a desktop, a bar fixed to
the bottom of the screen on a phone (`components/layout/Layout.jsx`). The
section a page belongs to - its edit pages included - is marked with
`aria-current="page"`; `lib/nav.js` holds that match.

| Page | Route | Gate |
| --- | --- | --- |
| Recipe library (the front page; `/` redirects here) | `/recipes` | public |
| Recipe | `/recipes/:id` | public |
| Ingredient library | `/ingredients` | public |
| Ingredient | `/ingredients/:id` | public |
| Kitchen-note library | `/notes` | public |
| Kitchen note | `/notes/:id` | public |
| Add / edit a recipe | `/edit/recipes/new`, `/edit/recipes/:id` | Access |
| Add / edit an ingredient | `/edit/ingredients/new`, `/edit/ingredients/:id` | Access |
| Add / edit a note | `/edit/notes/new`, `/edit/notes/:id` | Access |
| 設定 (`/settings` redirects here) | `/edit/settings` | Access |
| Image library | `/edit/images` | Access |

The recipe and note pages, the recipe and note forms and the image library
render a heading and an empty note until their real versions land; 設定 hosts
the categories-and-labels editor. Any other path is a "page not found" page,
not a redirect.

**The first release's paths redirect**, query string included, so bookmarks
survive: `/library/ingredient` → `/ingredients`, `/ingredient/:id` →
`/ingredients/:id`, `/edit/ingredient/...` → `/edit/ingredients/...`,
`/edit/vocabularies` → `/edit/settings`. `routes.test.jsx` pins every route
and every redirect.

Media's detail route is `/<type>/:publicId/:slug?`; the cosmetic slug and the
second id went with the integer-primary-key decision, so ours is
`/ingredients/:id`.

**The detail page is the one this app exists for.** It is what gets opened on a
phone in a shop, signed out: selection notes, the preservation methods with
their durations, where to get the thing. Everything else is a list or a form.

**Categories and labels share one page**, as two sections. They are the same
kind of work — maintaining a small vocabulary — and a page each would be two
screens with four rows on them.

**There is no route guard, and there must not be one.** The gate is Cloudflare
Access on the path prefix, in front of the box. A guard in the browser would
suggest the gate lives in this application, and the day someone believes that
is the day it moves. For the same reason the edit links are visible to
everyone: hiding them protects nothing.

## Two things that are not pages

**The `needs_detail` backlog and the uncategorised pile are filters** on the
library, with a count shown next to the filter. Without the count the backlog
is invisible and stubs accumulate forever.

**Delete is a dialog, not a page**, and not `window.confirm` — it has to show
counts and to correct itself. It sends the counts it displayed back as required
parameters; on a 409 it takes the server's `actual`, says so, and re-offers the
button. Asking for a reload is what a prose-only error body forces.

## Layers

- **`api/client.js` is the only file that calls `fetch`.** It joins the array
  FastAPI puts under `detail` for a validation error — the naive version
  renders `[object Object]`, for the one error a malformed body produces — and
  it attaches `status` and `body` to the thrown error so a caller can branch on
  409 without re-implementing fetch.
  It leaves the `Content-Type` alone for a `FormData` body, so the browser
  writes the multipart boundary itself.
- **`api/endpoints.js` is the single source of URL truth.** Each group's
  `list()` doubles as the resource's read prefix. Its test asserts every
  mutation URL sits under `/api/edit` - the invariant the backend asserts over
  its route table, on the side where the URL is chosen - and walks the whole
  object, so a new endpoint must be classified as a read or a write before the
  suite passes.
- **`hooks/useApi.js`** wraps TanStack Query so no component builds a cache key
  by hand. `useApiMutation({ method, invalidate })` invalidates **by
  resource**: `invalidate` is a list of read prefixes, and every cached query
  whose URL sits under one of them (whole path segments) is refreshed - a save
  refreshes the detail page and the cascade counts, not only the list.
  `useFixedVocabularies()` reads every closed list once per page load;
  `useUpload()` posts one image file as multipart.

## Colour and type

**The direction is a kitchen notebook**: warm paper, brown-black ink, one
terracotta accent for the thing a page points at, and a warm-brown dark mode
rather than a grey one. Headings are Noto Serif TC (loaded in `index.html`
with `display=swap`, system serifs behind it); metadata and controls use the
system sans.

**Semantic tokens only** - `canvas`, `surface`, `surface-2`, `border`,
`border-strong`, `text`, `text-muted`, `text-faint`, `brand`, `brand-hover`,
`brand-soft`, `on-brand`, `danger`, `ok`, `warn`, `warn-soft`, `scrim`, plus
`font-display` and `font-sans`. As in media, each Tailwind token points at a
runtime `--c-*` variable and the light and dark palettes in `index.css`
redefine only those. A numbered grey or a raw hex in a component fails
`theme-tokens.test.js`, which is what keeps dark mode from rotting one
component at a time and keeps the four apps looking like one product.

## Primitives

`components/ui/primitives.jsx`: `Button` and `LinkButton` (`kind` primary /
outline / danger / ghost, `size` sm / md), `Field`, `Input`, `TextArea`,
`Select`, `Card`, `Chip` (`tone`), `Badge` (`kind` bookmark 書籤 / stub 待補 /
rating with `value`), `Section` (a titled block on a ruled line) and `Toggle`
(封面 / 清單). **`className` extends the base classes, never replaces them.**
`components/ui/Dialog.jsx` is the modal shell - Escape closes, and the
backdrop closes only on a press that starts and ends on it -
and `components/modals/ConfirmModal.jsx` the yes/no question drawn in it.

## Images

Every `<img>` lazy-loads (`lazy-images.test.js`), and every cropped
(`object-cover`) one applies its focal point with `focusStyle()` from
`lib/images.js` or opts out with `data-focus="none"`
(`focus-images.test.js`). Both guards are media's.

## Loading, error and empty

Three states every list and detail page owes the reader, as named components
in `components/ui/states.jsx`, so that forgetting one is visible rather than rendering a
page that looks broken while it is merely empty.

## How the built bundle is served

**One process serves the API and the bundle, and nothing sits in front of it** —
cloudflared connects straight to uvicorn, so there is no proxy to serve a static
file this app declines to. `app/main.py` is the whole story:

- **`/assets/...`** is mounted as `StaticFiles`, when the build produced an
  `assets/` directory at all. Vite inlines every asset when the bundle is small
  enough, so the mount is conditional.
- **`/api/...` and `/health/...`** are refused by the catch-all with a 404, even
  when unregistered. This app's health path is `/health`, not `/api/health`, so
  a mistyped probe path must not come back as a 200 carrying the bundle.
- **Any other path that names a real file inside the bundle is served as that
  file** — `favicon.svg`, `favicon.ico`, `robots.txt`, anything the build copies
  from `frontend/public/` to the root of `frontend_dist/`. The path is resolved
  and confined to the dist directory first, so `..%2F.env` cannot read a file
  beside the bundle.
- **Everything else is `index.html`**, so client-side routing works.

The order matters and is the same as `media`'s: the API routers are registered
before the catch-all, so it cannot shadow a route that exists.

**A file in `frontend/public/` reaches production only through this handler.**
Before it served real files, `/favicon.svg` answered with `index.html` under
`text/html` and the browser discarded it — the icon was in the repository and in
the bundle, and had never once been shown.

## After any frontend change

```bash
cd frontend && npm run build
```

or `:8001` serves the old bundle while `:5174` serves the new one, and the
difference reads as a bug in whichever you looked at second.
