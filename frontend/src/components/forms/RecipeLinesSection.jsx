// Frontend: 材料 - a recipe's ingredient lines in their groups, as the recipe
// form and the template form both edit them.
//
// Above the lines sit the 常用 chips, one per 設定's 常用食材, in its order
// (CommonIngredientChips). A tap appends a line naming that ingredient to the
// ungrouped lines and puts the cursor in its 份量, so the amount is typed
// next; a chip whose ingredient is already on a line is marked used and still
// adds. No chips, no row.
//
// The lines sit in groups (GroupedRowEditor): the ungrouped ones first, then
// a box per group, picked from 設定's 材料分組 or named here only. A line's
// ingredient or dish is picked with the Typeahead, searching both libraries.
// With `allowNew` - the recipe form - 「新增」 makes the line name an
// ingredient that does not exist yet, shown with 待補 until the save creates
// it as a stub, and 「新增料理」 a dish, a 醬料, made by the save the same way.
// Without it - the template form, which never creates rows - only what is
// already in the libraries is offered.
//
//   value          the grouped lines (lib/groupedRows.js)
//   setValue       next value, or (previous) => next: the typed-but-unpicked
//                  text of a line is set from the latest state, because a
//                  pick calls onSelect and then reports '' in the same tick
//   allowNew       offer 新增 / 新增料理 (default true)
//   excludeDishes  dish ids never offered - a recipe's own dish
import { useEffect, useRef, useState } from 'react'

import { endpoints } from '../../api/endpoints'
import { fixedLabel, useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { UNGROUPED, flatRows, groupedReducer, updateRowByKey } from '../../lib/groupedRows'
import { emptyLine, isStub, targetFromOption } from '../../lib/recipeLines'
import { Input, Section } from '../ui/primitives'
import CommonIngredientChips from './CommonIngredientChips'
import GroupedRowEditor from './GroupedRowEditor'
import Typeahead, { Picked } from './Typeahead'

export default function RecipeLinesSection({ value, setValue, allowNew = true, excludeDishes = [] }) {
  const lineGroups = useApiQuery(endpoints.lineGroups.list())
  const common = useApiQuery(endpoints.commonIngredients.list())
  const fixed = useFixedVocabularies()
  const kindWord = (kind) => fixedLabel(fixed.data?.dish_kinds, kind)

  // The line a 常用 chip just added, whose 份量 takes the focus once drawn.
  const [focusAmountOf, setFocusAmountOf] = useState(null)
  const amountInputs = useRef(new Map())
  useEffect(() => {
    if (focusAmountOf) amountInputs.current.get(focusAmountOf)?.focus()
  }, [focusAmountOf])

  const setLinePending = (key, pending) => setValue((previous) => updateRowByKey(previous, key, { pending }))

  function addCommonLine(ingredient) {
    const row = {
      ...emptyLine(),
      target: {
        type: 'ingredient',
        id: ingredient.id,
        label: ingredient.display_name,
        needsDetail: ingredient.needs_detail,
      },
    }
    setValue((previous) =>
      groupedReducer(previous, { type: 'rows', container: UNGROUPED, action: { type: 'add', row } }),
    )
    setFocusAmountOf(row._key)
  }
  const usedIngredients = new Set(
    flatRows(value)
      .filter((line) => line.target?.type === 'ingredient')
      .map((line) => line.target.id),
  )

  return (
    <Section title="材料">
      <CommonIngredientChips
        ingredients={(common.data ?? []).map((row) => row.ingredient)}
        usedIds={usedIngredients}
        onAdd={addCommonLine}
      />
      <GroupedRowEditor
        value={value}
        onChange={setValue}
        values={lineGroups.data}
        newRow={() => emptyLine()}
        addLabel="加一行材料"
        itemLabel="材料"
        groupLabel="材料分組"
      >
        {(line, { update, number }) => (
          <div className="grid gap-2 sm:grid-cols-6">
            <div className="sm:col-span-3">
              {line.target ? (
                <Picked
                  label={line.target.label}
                  stub={isStub(line.target)}
                  tag={
                    line.target.type === 'dish'
                      ? kindWord(line.target.kind)
                      : line.target.type === 'new-dish'
                        ? `新${kindWord(line.target.kind)}`
                        : null
                  }
                  onClear={() => update({ target: null, pending: '' })}
                />
              ) : (
                <Typeahead
                  allowNew={allowNew}
                  allowNewDish={allowNew}
                  label={`材料 ${number}`}
                  placeholder="食材或料理（醬料）…"
                  exclude={{ dish: excludeDishes }}
                  onSelect={(option) => update({ target: targetFromOption(option) })}
                  onQueryChange={(text) => setLinePending(line._key, text)}
                />
              )}
            </div>
            <Input
              ref={(element) => {
                if (element) amountInputs.current.set(line._key, element)
                else amountInputs.current.delete(line._key)
              }}
              aria-label="份量"
              placeholder="份量"
              value={line.amount}
              onChange={(event) => update({ amount: event.target.value })}
              className="sm:col-span-1"
            />
            <Input
              aria-label="材料備註"
              placeholder="備註，例如 切絲"
              value={line.note}
              onChange={(event) => update({ note: event.target.value })}
              className="sm:col-span-2"
            />
            <label className="flex items-center gap-1.5 text-sm">
              <input
                type="checkbox"
                checked={line.is_optional}
                onChange={(event) => update({ is_optional: event.target.checked })}
              />
              可省略
            </label>
          </div>
        )}
      </GroupedRowEditor>
    </Section>
  )
}
