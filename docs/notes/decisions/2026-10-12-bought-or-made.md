# Bought or made: an ingredient links its homemade dish

**Two rows, linked.** Caramel, 雞高湯 and 油蔥酥 can be bought or made. The
bought thing is an ingredient - stocked, bought, cited on a line - and the
homemade one is a dish, usually a 醬料, with recipes of its own;
`ingredient.homemade_dish_id` names the dish. Rejected: **one row that is
both**, which would give every ingredient a recipe list or every dish a stock
flag, each empty for almost every row.

- **Not unique, and any kind.** Making 油蔥酥 also yields 紅蔥油, so one dish
  may be the homemade version of several ingredients; `kind` is how the
  library files a dish, not a permission.
- **`ON DELETE SET NULL`, not `RESTRICT`.** The link is a cross-reference, not
  a usage: nothing about the ingredient stops being true when the dish goes,
  and deleting a dish should not require unlinking it in another library
  first. The delete dialog still says how many ingredients lose the link.
- **A merge keeps the target's link**, as for a prose field.

How "what can I cook" reads the link is in `2026-09-19-what-can-i-cook.md`.
