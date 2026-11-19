# name_cn leads display, with no per-row override

A divergence from `media`, whose catalogue entities lead with English and carry
a `display_name_field` column naming the winner. food has one user reading
Chinese first, and a rule statable in a sentence beats a column every row has
to fill in. `name_cn` leading is a platform-wide convention rather than a food
one; `travel` and `art` follow it too.

If a per-row order is ever wanted, it is a column plus a fallback in
`NameFallbackMixin` (`app/models/base.py`), not a special case.
