# The cycle guard walks the stored graph breadth first

The nesting graph is a graph of dishes: dish A uses dish B when a recipe of A
names B. The guard walks it one query per level and refuses past `MAX_DEPTH`
rather than stopping short - a walk that gave up early would let a cycle
through. A recursive CTE would be one query instead of a few, for a graph a
person builds by hand; not worth it.
