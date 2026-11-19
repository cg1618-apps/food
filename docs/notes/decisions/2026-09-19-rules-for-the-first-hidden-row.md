# Rules for the day food first hides a row

food hides nothing today: no row is discontinued, archived or restricted.
These go live with the first hiding flag, which is exactly when nobody will
remember them.

- **Hidden must be indistinguishable from missing** - 404 rather than 403 - so
  the status cannot be used to work out which ids name real rows.
- **Whatever parameter drives the filtering gets no default.** `media`'s own
  documentation says so and its entity routers gave one anyway, producing
  write responses whose counts disagree with a GET of the same object. A
  required parameter fails loudly; an optional one fails as a wrong number
  nobody notices.
- The filter itself runs in SQL before the page is cut - already a convention,
  in `docs/api.md`, "Conventions".
