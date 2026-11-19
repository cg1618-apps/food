# Kitchen inventory is presence, not stock

An inventory item is `in_stock` with a free-text quantity and notes.

Rejected: **quantities decremented as you cook.** That demands every meal,
snack and spill be recorded or the numbers silently stop being true - the
feature most likely to be abandoned, taking the app's credibility with it.
The accepted consequence: "what can I cook" answers on presence and will never
say "not enough flour".

**A row that runs out stays, marked out of stock**, with an `is_staple` marker
for the things always kept. That is what feeds the shopping list, and it keeps
the notes written about an item instead of losing them each time the jar
empties.
