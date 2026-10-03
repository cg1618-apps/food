// Frontend: 步驟 - a recipe's steps in their groups, as the recipe form and
// the template form both edit them.
//
// Each step row has a kind switch - 步驟 / 可省略 / 備註, the fixed
// `step_kinds` list - beside its number. Only an ordinary step shows a
// number, counted through every group as the recipe's page counts them; a
// 備註 row's box is ruled and tinted the way the page draws a note. The rows'
// accessible names (「步驟 3」) keep a running index, so every row has a
// unique one whatever its kind.
//
// The steps sit in groups (GroupedRowEditor), picked from 設定's 步驟分組 or
// named here only. 「貼上多行」 takes a pasted block too: it is split into one
// step per line, the numbering stripped (lib/steps.js), and the steps added
// to the group chosen in the dialog, or to the ungrouped steps, each an
// ordinary step.
//
//   value     the grouped steps (lib/groupedRows.js)
//   setValue  (nextValue) => void
import { useState } from 'react'

import { endpoints } from '../../api/endpoints'
import { useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { UNGROUPED, flatRows, rowsOf, setRows } from '../../lib/groupedRows'
import { NOTE, splitSteps, stepNumbers, stepRow } from '../../lib/steps'
import Dialog from '../ui/Dialog'
import { Button, Field, Section, Select, TextArea, Toggle } from '../ui/primitives'
import GroupedRowEditor from './GroupedRowEditor'

export default function RecipeStepsSection({ value, setValue }) {
  const stepGroups = useApiQuery(endpoints.stepGroups.list())
  const fixed = useFixedVocabularies()
  const stepKinds = fixed.data?.step_kinds ?? []
  const [pasting, setPasting] = useState(false)

  // The number each ordinary step row shows, by its key, counted through
  // every group as the page counts them; an optional step or a note has none.
  const stepRows = flatRows(value)
  const stepNumber = new Map(
    stepNumbers(stepRows)
      .map((number, index) => [stepRows[index]._key, number])
      .filter(([, number]) => number !== null),
  )

  return (
    <Section title="步驟">
      <GroupedRowEditor
        value={value}
        onChange={setValue}
        values={stepGroups.data}
        newRow={() => stepRow()}
        addLabel="加一個步驟"
        itemLabel="步驟"
        groupLabel="步驟分組"
        actions={
          <Button size="sm" onClick={() => setPasting(true)}>
            貼上多行
          </Button>
        }
      >
        {(row, { update, number }) => {
          const note = row.kind === NOTE
          return (
            <div className="flex gap-2">
              <span className="w-6 shrink-0 pt-1 text-right font-display font-bold text-text-faint">
                {stepNumber.has(row._key) ? <span data-testid="step-number">{stepNumber.get(row._key)}</span> : null}
              </span>
              <div className="min-w-0 flex-1 space-y-1.5">
                {stepKinds.length ? (
                  <Toggle
                    label={`步驟 ${number} 的種類`}
                    options={stepKinds}
                    value={row.kind}
                    onChange={(kind) => update({ kind })}
                  />
                ) : null}
                <div className={note ? 'rounded-md border-l-4 border-border-strong bg-surface-2 p-1.5' : undefined}>
                  <TextArea
                    aria-label={`步驟 ${number}`}
                    rows={2}
                    placeholder={note ? '備註：火候、替換、提醒' : undefined}
                    value={row.body}
                    onChange={(event) => update({ body: event.target.value })}
                  />
                </div>
              </div>
            </div>
          )
        }}
      </GroupedRowEditor>

      {pasting ? (
        <PasteSteps
          groups={value.groups}
          onClose={() => setPasting(false)}
          onAdd={(bodies, container) => {
            const rows = [...rowsOf(value, container), ...bodies.map((body) => stepRow({ body }))]
            setValue(setRows(value, container, rows))
            setPasting(false)
          }}
        />
      ) : null}
    </Section>
  )
}

// 「貼上多行」: one step per line, numbering stripped, previewed by count
// before anything is added - at the end of the chosen group, 不分組 unless
// another is picked.
function PasteSteps({ groups, onAdd, onClose }) {
  const [text, setText] = useState('')
  const [container, setContainer] = useState(UNGROUPED)
  const bodies = splitSteps(text)
  return (
    <Dialog
      title="貼上多行步驟"
      size="md"
      onClose={onClose}
      footer={
        <>
          <Button onClick={onClose}>取消</Button>
          <Button kind="primary" disabled={!bodies.length} onClick={() => onAdd(bodies, container)}>
            加入 {bodies.length} 個步驟
          </Button>
        </>
      }
    >
      <Field label="一行一個步驟" hint="開頭的編號（1.、1)、①、一、、第一步）會自動拿掉。">
        <TextArea rows={10} value={text} onChange={(event) => setText(event.target.value)} autoFocus />
      </Field>
      <Field label="加到">
        <Select value={container} onChange={(event) => setContainer(event.target.value)}>
          <option value={UNGROUPED}>不分組</option>
          {groups.map((group, index) => (
            <option key={group._key} value={group._key}>
              {group.name.trim() || `第 ${index + 1} 組`}
            </option>
          ))}
        </Select>
      </Field>
    </Dialog>
  )
}
