# Single-column unique name indexes use the default null handling

Not a divergence from `media`, though it reads like one. media's lesson is
real: `uq_person_name` spans several name columns, and there a NULL in any of
them makes the whole constraint inert, which shipped duplicates three times.
Its fix, `NULLS NOT DISTINCT`, applied to a *single-column* index inverts the
lesson: NULL then equals NULL, so the table may hold exactly one row with that
slot empty. Most ingredients here have only a Chinese name, so the second one
inserted would be refused.

`test_any_number_of_ingredients_may_leave_a_name_slot_empty` refuses the change
if someone applies the lesson again.
