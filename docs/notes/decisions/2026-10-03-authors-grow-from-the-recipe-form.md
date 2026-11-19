# A source's author is a vocabulary that grows from the recipe form

Authors are rows, not free text on a source, so a name is renamed once rather
than per source and filtered by as a row rather than an exact string - 詹姆士
and a mistyped 詹姆斯 stop being two people.

But an author, unlike a platform, is met while entering a recipe: a new
channel is the usual case. Stopping to visit 設定 first is the friction that
pushes the name into the title instead. So the source row picks from the list
and offers 「新增 'xxx'」, and the save creates the author exactly as a line
creates a stub ingredient - after validation, in the same transaction, an
exact name reused.

Rejected:

- **Free text with a derived author list** - renaming would still be per
  source.
- **Creating authors on blur from the form** - an abandoned save would leave
  authors nobody used.

**Authors are listed by name, not by hand.** Every author is created with
`sort_order` 0 and 設定 shows them with no drag handle: dozens of names have no
meaningful order but the alphabet, which the factory's (sort_order, name)
order already gives.
