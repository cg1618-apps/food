# The SPA catch-all serves real files, the way media does

The catch-all resolves `dist / full_path` and serves it only when it is a real
file inside the dist directory; otherwise it answers `index.html`. This is
`media`'s resolve-and-confine block, adopted rather than redesigned.
`docs/frontend.md`, "How the built bundle is served", describes it.

The `.resolve()` + `is_relative_to()` + `is_file()` guard is security, not
tidiness: `full_path` is user-controlled, and without the confinement
`/..%2F.env` reads the app's own credentials. `docs/testing.md` names the test
that keeps it, and the fixture that makes that test bite.

Rejected:

- **Special-casing the icon paths** - `/favicon.svg`, `/favicon.ico`,
  `/robots.txt` and whatever comes next. A list somebody has to remember to
  extend, with the same silent failure each time a file is added to
  `frontend/public/`.
- **Mounting the whole dist as `StaticFiles` with `html=True`.** It serves the
  files, but hands the client-route fallback to Starlette and with it the
  `/api` and `/health` 404 guards this app cannot give up.
