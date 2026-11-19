# A name typed into a form reuses only an exact match

A new ingredient on a recipe line, a new dish (`new_dish`) and a new author
(`new_author`) are all resolved by one rule: a name equal to an existing row's
name slot or alias, ignoring case, means that row; anything else is created.
Names already resolved in the same save count, so one new name typed twice is
one row rather than a unique violation.

A near match is never guessed at. The typeahead shows near matches while a
person is there to choose; the save folds only exact ones.
