# A closed list in code, or a vocabulary the owner edits

The line between the two: **a value the code branches on is a closed list; a
value that is only displayed and filtered by is a vocabulary.**

- **Closed lists** are a `String` column validated against a list in
  `app/constants.py`, never a Postgres enum: dish `kind` (`DISH_KINDS` - a
  dish typed into a line is created a sauce, a sauce carries a 醬料 chip),
  `STEP_KINDS` (whether a step is numbered and how it is drawn),
  `MEAL_SLOTS`, `LABEL_SCOPES` and the preservation states. A kind the owner
  added in 設定 would have no behaviour to give it.
- **Vocabularies** are factory tables the owner edits: courses, region,
  recipe status, source platform and the rest. Recipe status (想試 / 可煮 /
  常煮) and source platform began as closed lists and became vocabularies
  when the owner wanted to add 冷凍好 or IG, rename or reorder - nothing in the
  app branched on either. A value in use refuses its delete
  (`RESTRICT`, the usual 409 and count).

`docs/data-model.md`, "The managed vocabularies", lists them.
