# Line and step groups are rows, not labels

- **Groups are real per-recipe rows** (`recipe_line_group`,
  `recipe_step_group`), not a free-text section on each row. A label grouped
  by equal text cannot be empty, is renamed by editing every row, takes the
  order of whichever row came first, and makes 醬汁 and "醬汁 " two groups.
  Rejected for all four.
- **A group is a 未來固定設定 value or a one-off name, exactly one.** Most
  recipes reuse a few groups (主料, 調味料 / 備料, 烹飪), which should be one tap
  and one spelling; a few need their own (漢堡醬, 醃料), which should not have to
  be added to the vocabulary first. A name matching a value is stored as the
  value, so "the same group" has one representation and the uniques can
  refuse it twice in one recipe.
- **Two lists, not one.** What groups ingredients (主料, 配料) is rarely what
  groups the method (備料, 烹飪, 醬汁 - a stage, not a pile of ingredients).
- **A row's `group_id` is `SET NULL`.** A group going never takes its rows
  with it, which is what 移除分組 says, and no other path can quietly delete
  steps. `RESTRICT` would have made the save order carry the rule.
- **Positions run through the whole recipe, in display order**, so
  `recipe.lines` and `recipe.steps` stay the whole list in reading order for
  every reader that does not care about groups.
- **The wire keeps `lines` and `steps` as the ungrouped rows**, with
  `line_groups` and `step_groups` beside them. Nesting every row would need a
  synthetic "no group" group the owner never made.
- **A PATCH replaces a pair together; one half alone is a 422.** Keeping the
  stored groups would leave lines the client did not send; dropping them would
  let a client that never heard of groups delete rows it never saw. Refusing is
  the only answer that does not guess.
- **One drag system, extended.** `Sortable.jsx`'s `SortableBoard` is dnd-kit's
  multiple-containers shape, joined by the existing `SortableList`, so every
  handle, its keyboard path and its focus rule stay one implementation. The
  keyboard crossing a group's edge is what lets a row change group without a
  pointer.
