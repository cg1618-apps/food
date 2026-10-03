// Frontend: add or edit a recipe template, /edit/templates/new and
// /edit/templates/:id.
//
// A template is the skeleton a new recipe starts from (the new-recipe
// chooser's 從範本): a name, 份量 and 時間, 材料 and 步驟 in their groups,
// 做法 and 器材. Those sections are the recipe form's own
// (RecipeLinesSection, RecipeStepsSection, RecipeMethodsSection), with one
// difference: a template line picks an ingredient or a dish that already
// exists - no 「新增」 - because a template never creates rows, and the
// server refuses one that tries.
//
// A saved template the server read back with references that no longer exist
// says how many it left out; saving writes what the form now holds, which
// drops them for good. POST and PATCH both send the whole body, which
// replaces what was stored. Saving, and 取消, go back to 設定's 範本 tab,
// where templates are listed, ordered, renamed and deleted.
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import FormActions from '../../components/forms/FormActions'
import RecipeLinesSection from '../../components/forms/RecipeLinesSection'
import RecipeMethodsSection from '../../components/forms/RecipeMethodsSection'
import RecipeStepsSection from '../../components/forms/RecipeStepsSection'
import { Field, Input, Section } from '../../components/ui/primitives'
import { ErrorNote, Loading } from '../../components/ui/states'
import { useApiMutation, useApiQuery } from '../../hooks/useApi'
import { emptyStructure, structureFromResponse, structurePayload } from '../../lib/recipeStructure'
import { blankToNull } from '../../lib/rowList'

const INVALIDATE = [endpoints.templates.list()]
const BACK = '/edit/settings?tab=templates'

const empty = () => ({ name: '', ...emptyStructure() })

export default function TemplateForm() {
  const { id } = useParams()
  const isNew = id === undefined
  const navigate = useNavigate()
  const existing = useApiQuery(endpoints.templates.detail(id), null, { enabled: !isNew })
  const save = useApiMutation({ method: isNew ? 'POST' : 'PATCH', invalidate: INVALIDATE })

  const [form, setForm] = useState(empty)
  const [loaded, setLoaded] = useState(null)
  const [error, setError] = useState(null)

  // As the recipe form: keyed on the id, so a refetch never throws away what
  // is being typed.
  if (!isNew && existing.data && loaded?.id !== existing.data.id) {
    setLoaded(existing.data)
    setForm({ name: existing.data.name, ...structureFromResponse(existing.data.body) })
  }

  const setField = (field, value) => setForm((previous) => ({ ...previous, [field]: value }))
  const set = (field) => (event) => setField(field, event.target.value)
  const setter = (field) => (next) =>
    setForm((previous) => ({ ...previous, [field]: typeof next === 'function' ? next(previous[field]) : next }))

  async function submit(event) {
    event.preventDefault()
    setError(null)
    const name = blankToNull(form.name)
    if (!name) {
      setError(new Error('範本要有名稱。'))
      return
    }
    try {
      // Inside the try: the payload refuses a line typed and never picked.
      const body = { name, body: structurePayload(form) }
      await save.mutateAsync({ url: isNew ? endpoints.templates.create() : endpoints.templates.update(id), body })
      navigate(BACK)
    } catch (caught) {
      setError(caught)
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl font-bold">{isNew ? '新增範本' : '編輯範本'}</h1>
        <p className="text-sm text-text-muted">新增食譜時可以從範本開始，帶入這裡的材料、步驟、做法和器材。</p>
        {existing.data?.dropped ? (
          <p role="status" className="text-sm text-danger">
            範本裡有 {existing.data.dropped} 個項目已不存在，已略過；儲存後就不會再出現。
          </p>
        ) : null}
      </header>

      {!isNew && existing.isPending ? <Loading /> : null}
      {!isNew && existing.error ? <ErrorNote error={existing.error} /> : null}

      {isNew || existing.data ? (
        <>
          <Section title="範本">
            <div className="grid gap-3 sm:grid-cols-3">
              <Field label="名稱" className="sm:col-span-3">
                <Input value={form.name} onChange={set('name')} placeholder="例如 基本炒青菜" />
              </Field>
              <Field label="份量">
                <Input value={form.servings} onChange={set('servings')} placeholder="例如 2 人份" />
              </Field>
              <Field label="時間">
                <Input value={form.time} onChange={set('time')} placeholder="例如 30 分鐘" />
              </Field>
            </div>
          </Section>

          <RecipeLinesSection value={form.lines} setValue={setter('lines')} allowNew={false} />
          <RecipeStepsSection value={form.steps} setValue={setter('steps')} />
          <RecipeMethodsSection methodIds={form.method_ids} equipmentIds={form.equipment_ids} onChange={setField} />

          <FormActions saving={save.isPending} error={error} onCancel={() => navigate(BACK)} />
        </>
      ) : null}
    </form>
  )
}
