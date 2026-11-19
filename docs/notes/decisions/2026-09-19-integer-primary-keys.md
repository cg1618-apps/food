# Integer primary keys, and no second public id

A divergence from `media`, which has a `system_id` UUID join key plus a short
`public_id` from a per-table sequence under a deferrable unique constraint.
That machinery exists so media's Google Sheets restore can permute ids inside
one transaction. food has no such channel, so it would be two ids and a
sequence serving nothing.
