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
// Under each line, 「＋替代」 adds an alternative (或): something that may
// stand in for the line's target, picked with the same Typeahead and the same
// 新增 / 新增料理, with its own 份量 (blank is "the same as the line") and
// 備註, and ✕ to remove it. Alternatives keep the order they were added in;
// they are not dragged.
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
import { emptyAlternative, emptyLine, isStub, targetFromOption } from '../../lib/recipeLines'
import { Button, Input, Section } from '../ui/primitives'
import CommonIngredientChips from './CommonIngredientChips'
import GroupedRowEditor from './GroupedRowEditor'
import Typeahead, { Picked } from './Typeahead'

/** A line's or an alternative's target: the pick, or the search for one. */
function TargetPicker({ row, label, allowNew, excludeDishes, kindWord, onPick, onClear, onQueryChange }) {
  if (row.target) {
    return (
      <Picked
        label={row.target.label}
        stub={isStub(row.target)}
        tag={
          row.target.type === 'dish'
            ? kindWord(row.target.kind)
            : row.target.type === 'new-dish'
              ? `新${kindWord(row.target.kind)}`
              : null
        }
        onClear={onClear}
      />
    )
  }
  return (
    <Typeahead
      allowNew={allowNew}
      allowNewDish={allowNew}
      label={label}
      placeholder="食材或料理（醬料）…"
      exclude={{ dish: excludeDishes }}
      onSelect={(option) => onPick(targetFromOption(option))}
      onQueryChange={onQueryChange}
    />
  )
}

export default function RecipeLinesSection({ value, setValue, allowNew = true, excludeDishes = [] }) {
  const lineGroups = useApiQuery(endpoints.lineGroups.list())
  const common = useApiQuery(endpoints.commonIngredients.list())
  const fixed = useFixedVocabularies()
  const kindWord = (kind) => fixedLabel(fixed.data?.dish_kinds, kind)

  // A line's alternatives, changed from the latest state - the typed text
  // arrives right after a pick, as a line's own does.
  const setAlternatives = (lineKey, change) =>
    setValue((previous) => {
      const line = flatRows(previous).find((row) => row._key === lineKey)
      return line ? updateRowByKey(previous, lineKey, { alternatives: change(line.alternatives ?? []) }) : previous
    })
  const updateAlternative = (lineKey, key, patch) =>
    setAlternatives(lineKey, (rows) => rows.map((row) => (row._key === key ? { ...row, ...patch } : row)))

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
          <div className="space-y-2">
            <div className="grid gap-2 sm:grid-cols-6">
              <div className="sm:col-span-3">
                <TargetPicker
                  row={line}
                  label={`材料 ${number}`}
                  allowNew={allowNew}
                  excludeDishes={excludeDishes}
                  kindWord={kindWord}
                  onPick={(target) => update({ target })}
                  onClear={() => update({ target: null, pending: '' })}
                  onQueryChange={(text) => setLinePending(line._key, text)}
                />
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
            {(line.alternatives ?? []).map((alternative, index) => {
              const name = `材料 ${number} 的替代 ${index + 1}`
              return (
                <div
                  key={alternative._key}
                  role="group"
                  aria-label={name}
                  className="flex items-start gap-2 border-l-2 border-border pl-3"
                >
                  <span className="mt-1.5 shrink-0 text-sm text-text-muted">或</span>
                  <div className="grid min-w-0 flex-1 gap-2 sm:grid-cols-6">
                    <div className="sm:col-span-3">
                      <TargetPicker
                        row={alternative}
                        label={name}
                        allowNew={allowNew}
                        excludeDishes={excludeDishes}
                        kindWord={kindWord}
                        onPick={(target) => updateAlternative(line._key, alternative._key, { target })}
                        onClear={() => updateAlternative(line._key, alternative._key, { target: null, pending: '' })}
                        onQueryChange={(text) => updateAlternative(line._key, alternative._key, { pending: text })}
                      />
                    </div>
                    <Input
                      aria-label="替代份量"
                      placeholder="份量（空白同上）"
                      value={alternative.amount}
                      onChange={(event) => updateAlternative(line._key, alternative._key, { amount: event.target.value })}
                      className="sm:col-span-1"
                    />
                    <Input
                      aria-label="替代備註"
                      placeholder="備註"
                      value={alternative.note}
                      onChange={(event) => updateAlternative(line._key, alternative._key, { note: event.target.value })}
                      className="sm:col-span-2"
                    />
                  </div>
                  <button
                    type="button"
                    aria-label={`移除${name}`}
                    title="移除替代"
                    onClick={() =>
                      setAlternatives(line._key, (rows) => rows.filter((row) => row._key !== alternative._key))
                    }
                    className="shrink-0 rounded-sm px-1.5 py-1 text-text-faint hover:bg-surface-2 hover:text-danger focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                  >
                    ✕
                  </button>
                </div>
              )
            })}
            <Button
              size="sm"
              onClick={() => setAlternatives(line._key, (rows) => [...rows, emptyAlternative()])}
            >
              ＋替代
            </Button>
          </div>
        )}
      </GroupedRowEditor>
    </Section>
  )
}
