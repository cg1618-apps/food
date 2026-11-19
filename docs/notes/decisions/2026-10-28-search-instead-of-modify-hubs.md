# Search instead of modify hubs

**One search box finds anything, and it is how an entry is edited from
anywhere.** `media` has "modify" hubs, a page per type listing every entry for
editing. The owner decided food does not: every library here already has a
page per entry with an 編輯 button, so a hub would add only the finding. The
universal search finds across every kind at once, and each row on `/search`
links straight to the entry's edit page.

**media's NavSearch and `/api/search` are the reference; food keeps the shape
and drops the rest.** Kept: one debounced request answering a bucket per kind,
a dropdown in the top bar, Enter for the full page, Escape and a click outside
to close, the phone's search as a row opened from an icon. Dropped: the scope
menu and the gated types, since food has no auth; and the quota-and-round-robin
merge, because food's kinds are few enough to show grouped under their labels,
three rows each, and a phone scrolls rather than losing a kind to a quota. One
uniform row shape rather than media's full entity per bucket: a row needs four
things, and a shape per kind is a chance per kind for the dropdown and the
page to read different fields.

- **A bucket matches by its library's own clauses** (`<library>.matches`), so
  the top bar never finds a row the library's own box would not. A TBD link's
  url is not searched: every one contains "https".
- **Ranking is tiers in SQL** - `contains`, `prefix`, `exact` from the same
  matcher, then the display name, then id - so one definition of "matches"
  serves the filter and every tier, aliases included. It is in SQL because the
  `limit` is: ranked in Python, an exact match eleventh by name would be cut
  before it could be floated (media's reason too). Rejected: **trigram
  similarity**, which ranks typos better but needs an extension and a
  migration, for catalogues small enough that substring tiers put the right
  row first.
- **A blank term answers empty buckets**, 200 rather than 422: an empty box is
  not a request for every row in the app, and a client clearing its box needs
  no error path.
- **加熱 and TBD rows open the list at the entry** (`hooks/useHashTarget.js`),
  since neither has a page per entry; the browser cannot do it, because the
  list arrives after the page and a client-side navigation does not update
  `:target`. Their 編輯 opens the edit page at the top: each card holds its own
  form state, and reaching into one from a URL is more than the case is worth.
- **Below `lg` the box is an icon that opens a row in the flow**, not a field
  in the bar, which would squeeze to nothing at 360px. Rejected: an overlay,
  which covers the page's own top-right actions.
