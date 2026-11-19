# An author's links are TBD's link shape

- **A child table in `tbd_link`'s shape.** An author has any number of links,
  each named and ordered by the owner, which TBD had already settled: a row per
  link with a `position`, a NOT NULL url a CHECK refuses blank, an optional
  label, CASCADE from the owner, and a save that replaces the rows wholesale.
  Rejected: **a column per platform** (`youtube_url`, `ig_url`) - the owner
  names the links and the next platform would be a migration; **a JSONB
  list** - the database could no longer refuse a blank url, and the two link
  lists would differ for no reason.
- **The link rules are inherited, not copied.** `AuthorLinkIn` subclasses
  `TbdLinkIn`, so the `https://` default and the refusal of every other scheme
  - what keeps a `javascript:` link off a public page - cannot drift apart.
