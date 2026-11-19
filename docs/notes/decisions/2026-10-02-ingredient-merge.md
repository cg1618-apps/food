# Merge is the fix for a duplicate, and the target wins

Merge, not delete, is how a duplicate ingredient is fixed: every catalogue
entity in `media` has one, and deleting a duplicate instead is on media's own
list of mistakes.

**The target wins.** Whatever only the source has moves; whatever collides is
the target's and the source's is dropped, and the preview lists every drop.
The source's name slots become aliases on the target, never names: the
target's names are what the user chose to keep. Single values - category,
parent, rating, `needs_detail` - are not merged at all: the user is merging
INTO the row whose values they want. Moved rows are numbered after the
target's own, so a merged list keeps the target's order and appends.

**The preview and the merge are one function's output**, so the preview cannot
describe a different merge from the one that runs.

**A merge carries its preview's fingerprint, and a changed plan is a 409.**
One function closes the gap between what the code shows and what it runs, but
not between what the user READ and what runs: the preview can sit in a tab
while the source is edited elsewhere. A merge is more destructive than a
delete, so it gets the stale-tab guard deletes have. Counts were not enough -
an edited note moves different content under the same count - so the
fingerprint is a SHA-256 of the canonical JSON of the rows the plan moves and
drops, and the 409 carries the fresh preview so the dialog redraws without a
reload. Required rather than optional: an optional guard is one a client
forgets.

Merging into a descendant is refused, since the source's children would move
under their own descendant.
