# A recipe line's alternatives

A line may list alternatives - substitutes across families: 雞腿 or 雞胸肉, 米酒
or 清酒, a homemade sauce or a bought one. Varieties already cover close
substitutes (a line naming 醬油 accepts its varieties), so an alternative is
only for what a variety cannot say. The owner confirmed an alternative may
carry its own amount; blank means the line's.

- **A child table, `recipe_line_alternative`, not an "alternative of" line.**
  An alternative is not a separate requirement. Made a line of its own it
  would take a recipe-wide position, sit in a group, carry a meaningless
  可省略, and count in `written_up` and the line count - and every future
  "what does this recipe need" (the shopping list, "what can I cook") would
  have to filter it back out, the kind of rule that is forgotten once. As a
  child of its line it has none of those by construction.
- **An alternative names what a line names, by the line's code.**
  `AlternativeIn` and `LineIn` share one base and one CHECK shape, and the
  save resolves new names for lines and alternatives in one pass
  (`recipes._targets`), so a name typed on both is one stub, and the own-dish
  rule and the cycle guard see both. A dish named as an alternative is an
  edge of the nesting graph.
- **Redundant alternatives are dropped, not refused.** One naming its line's
  own target or repeating an earlier alternative says nothing more, and a new
  name may only turn out to be one after it is resolved - by which point the
  save has started writing, and a refusal would leave rows behind. So every
  recipe save and an ingredient merge apply one rule,
  `recipes.distinct_alternatives`: the first is kept.
- **Position is unique per line**, unlike `tbd_link.position`: alternatives
  are never replaced in place - a save replaces the lines and the
  alternatives go with them - so the unique only ever sees new rows.
- **No drag to reorder alternatives.** The lines already sit in a drag board
  across groups; a second sortable inside each row is the costly part, and
  the order of two or three substitutes rarely matters.

"What used in counts" (`2026-10-02-what-used-in-counts.md`) says how they are
counted.
