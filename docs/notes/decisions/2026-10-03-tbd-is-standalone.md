# TBD is standalone, on purpose

The owner asked for "a page with links or text … pure notes", with no relation
to the rest of the app. So an entry references no ingredient, recipe, label or
image, and nothing references it: it is somewhere to drop a thing before
deciding what it is, and the day it becomes something it is re-entered where
it belongs.

Rejected:

- **Links from an entry to a recipe**, which would make TBD a second
  kitchen-notes module.
- **Folding it into kitchen notes.** A note is a titled bookmark with a kind,
  a body, labels, pictures and a filtered library; a TBD entry is an optional
  name and several links in a hand-set order, read as one short page. Folding
  one into the other would make every field of each optional for the other's
  sake.

The rules that follow:

- **Name or link, enforced by the service.** A CHECK cannot see the child
  table, and a PATCH sending only `links: []` is right or wrong depending on
  the stored name.
- **A link without a scheme is given `https://`**, because refusing
  `example.com/x` would be pedantry about something the app can fix. Any
  scheme but `http` and `https` is refused: a `javascript:` link rendered on a
  public page is an XSS. A colon followed by a digit is a port, so
  `localhost:8000` is a bare host.
- **Saved per entry, reordered in one call.** An edit to one entry never
  rewrites another; the order is one `PUT` of every id, which must be exactly
  the current entries - a stale tab's order is refused rather than merged.
