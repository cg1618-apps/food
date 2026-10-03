// Frontend: one recipe, /recipes/:id.
//
// One reading column, in the order a cook reads it: the pictures; course,
// names and a meta line (servings, time, methods, equipment); the status,
// changeable here; where it came from; other versions; the ingredients and
// the steps, each grouped by section (lib/sections.js); notes; and for a base,
// the recipes that use it. Every section with nothing in it is left out, so a
// recipe saved as a bookmark is a short page rather than a page of empties.
//
// The status is the one thing changed in place: 想試 -> 可煮 -> 常煮 is what
// happens after cooking, standing at the stove with the page open, and a
// round trip through the form for it would be the form's whole job. The
// choices are the statuses 設定 manages, in their order. It is a PATCH of
// `status_id` alone; the control shows the chosen value while the
// request runs, then the recipe the PATCH answers with (put straight into the
// detail read's cache), and goes back, with the server's sentence, if it
// fails.
import { Link, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import { DetailActions, DetailStatus, LabelLinks, Prose, RecipeLinks } from '../../components/layout/Detail'
import Gallery from '../../components/ui/Gallery'
import { Badge, Chip, LinkButton, Section, Toggle } from '../../components/ui/primitives'
import { ErrorNote } from '../../components/ui/states'
import { fixedLabel, useApiMutation, useApiQuery, useFixedVocabularies } from '../../hooks/useApi'
import { linkHost } from '../../lib/format'
import { groupBySection, numberedStepGroups } from '../../lib/sections'
import { otherVersions } from '../../lib/versions'

const names = (refs) => (refs?.length ? refs.map((ref) => ref.display_name).join('、') : null)

// A status change moves this recipe's reads and the library's status filter
// and column - all under the recipes prefix - and the statuses' usage counts.
const STATUS_INVALIDATE = [endpoints.recipes.list(), endpoints.statuses.list()]

function StatusControl({ recipe }) {
  const statuses = useApiQuery(endpoints.statuses.list())
  const mutation = useApiMutation({
    method: 'PATCH',
    invalidate: STATUS_INVALIDATE,
    // The PATCH answers with the whole recipe: shown at once, and kept if the
    // refetch after it fails.
    onSaved: (saved, _variables, queryClient) =>
      queryClient.setQueryData([endpoints.recipes.detail(recipe.id), null], saved),
  })
  const shown = mutation.isPending ? mutation.variables.body.status_id : recipe.status.id
  const options = (statuses.data ?? []).map((status) => ({ value: status.id, label: status.display_name }))

  return (
    <div className="space-y-2">
      <Toggle
        label="狀態"
        options={options}
        value={shown}
        onChange={(statusId) => {
          if (mutation.isPending) return
          mutation.mutate({ url: endpoints.recipes.update(recipe.id), body: { status_id: statusId } })
        }}
      />
      {mutation.error ? (
        <ErrorNote error={mutation.error}>狀態沒有改成：{mutation.error.message}</ErrorNote>
      ) : null}
    </div>
  )
}

// Each source: its platform, its author (a link to the library filtered by
// them, as the course is), and its title - the link out when there is a URL,
// the URL's host standing in for a missing title.
function Sources({ sources }) {
  if (!sources.length) return null
  return (
    <ul className="space-y-1 text-sm">
      {sources.map((source) => {
        const words = source.title || (source.url ? linkHost(source.url) : null)
        return (
          <li key={source.id} className="flex flex-wrap items-baseline gap-2">
            <Chip>{source.platform.display_name}</Chip>
            {source.author ? (
              <Link to={`/recipes?author=${source.author.id}`} className="hover:text-brand hover:underline">
                {source.author.display_name}
              </Link>
            ) : null}
            {source.author && words ? <span className="text-text-faint">·</span> : null}
            {source.url ? (
              <a href={source.url} target="_blank" rel="noreferrer" className="text-brand hover:underline">
                {words} ↗
              </a>
            ) : words ? (
              <span>{words}</span>
            ) : null}
          </li>
        )
      })}
    </ul>
  )
}

function LineTarget({ line }) {
  if (line.ingredient) {
    return (
      <>
        <Link to={`/ingredients/${line.ingredient.id}`} className="text-text hover:text-brand hover:underline">
          {line.ingredient.display_name}
        </Link>
        {line.ingredient.needs_detail ? <Badge kind="stub" /> : null}
      </>
    )
  }
  if (line.sub_recipe) {
    return (
      <Link to={`/recipes/${line.sub_recipe.id}`} className="text-brand hover:underline">
        {line.sub_recipe.display_name}
      </Link>
    )
  }
  return null
}

function Lines({ lines }) {
  return groupBySection(lines).map((group) => (
    <div key={group.section ?? ''} className="space-y-1">
      {group.section ? <h3 className="text-sm font-bold text-text-muted">{group.section}</h3> : null}
      <ul className="divide-y divide-border">
        {group.rows.map((line) => (
          <li
            key={line.id}
            className={`flex items-baseline gap-3 py-1.5 ${line.is_optional ? 'text-text-faint' : ''}`}
          >
            <span className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-2 gap-y-1">
              <LineTarget line={line} />
              {line.is_optional ? <span className="text-xs">（可省略）</span> : null}
              {line.note ? <span className="text-xs text-text-muted">{line.note}</span> : null}
            </span>
            {line.amount ? <span className="shrink-0 tabular-nums">{line.amount}</span> : null}
          </li>
        ))}
      </ul>
    </div>
  ))
}

function Steps({ steps }) {
  return numberedStepGroups(steps).map((group) => (
    <div key={group.section ?? ''} className="space-y-2">
      {group.section ? <h3 className="text-sm font-bold text-text-muted">{group.section}</h3> : null}
      <ol className="space-y-3">
        {group.rows.map((step) => (
          <li key={step.id} className="flex gap-3">
            <span
              aria-hidden="true"
              className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-soft font-display text-sm font-bold text-brand"
            >
              {step.number}
            </span>
            <p className="whitespace-pre-line leading-relaxed">
              <span className="sr-only">第 {step.number} 步：</span>
              {step.body}
            </p>
          </li>
        ))}
      </ol>
    </div>
  ))
}

export default function Recipe() {
  const { id } = useParams()
  const query = useApiQuery(endpoints.recipes.detail(id))
  const fixed = useFixedVocabularies()
  const recipe = query.data

  if (!recipe) {
    return (
      <DetailStatus
        query={query}
        missing="找不到這道食譜。"
        back={<LinkButton to="/recipes">回到食譜庫</LinkButton>}
      />
    )
  }

  const otherNames = [recipe.name_cn, recipe.name_en, recipe.name_alt].filter(
    (name) => name && name !== recipe.display_name,
  )
  const meta = [
    recipe.servings ? `份量 ${recipe.servings}` : null,
    recipe.time ? `時間 ${recipe.time}` : null,
    names(recipe.methods),
    names(recipe.equipment),
  ].filter(Boolean)
  const versions = otherVersions(recipe)
  const isBase = recipe.kind === 'base'

  return (
    <article className="mx-auto max-w-2xl space-y-8">
      <Gallery images={recipe.images} title={recipe.display_name} />

      <header className="space-y-3">
        <p className="flex flex-wrap items-center gap-2 text-sm text-text-muted">
          {recipe.course ? (
            <Link to={`/recipes?course=${recipe.course.id}`} className="hover:text-brand">
              {recipe.course.display_name}
            </Link>
          ) : null}
          {isBase ? <Chip tone="brand">{fixedLabel(fixed.data?.recipe_kinds, recipe.kind)}</Chip> : null}
          {recipe.serves_as.length ? <span>也可以當作 {names(recipe.serves_as)}</span> : null}
          {recipe.written_up ? null : <Badge kind="bookmark" />}
        </p>
        <h1 className="text-3xl font-bold leading-tight">{recipe.display_name}</h1>
        {otherNames.length ? <p className="text-text-muted">{otherNames.join(' · ')}</p> : null}
        {meta.length ? <p className="text-sm text-text-muted">{meta.join(' · ')}</p> : null}
        <StatusControl recipe={recipe} />
        <LabelLinks labels={recipe.labels} to={(label) => `/recipes?label=${label.id}`} />
      </header>

      <Prose>{recipe.description}</Prose>

      {recipe.sources.length ? (
        <Section title="來源">
          <Sources sources={recipe.sources} />
        </Section>
      ) : null}

      {versions.length ? (
        <Section title="其他版本">
          <RecipeLinks recipes={versions} describe={(v) => (v.original ? '原版' : null)} />
        </Section>
      ) : null}

      {recipe.lines.length ? (
        <Section title="材料">
          <div className="space-y-4">
            <Lines lines={recipe.lines} />
          </div>
        </Section>
      ) : null}

      {recipe.steps.length ? (
        <Section title="步驟">
          <div className="space-y-5">
            <Steps steps={recipe.steps} />
          </div>
        </Section>
      ) : null}

      {recipe.storage_notes ? (
        <Section title="保存">
          <Prose>{recipe.storage_notes}</Prose>
        </Section>
      ) : null}

      {recipe.notes ? (
        <Section title="筆記">
          <Prose>{recipe.notes}</Prose>
        </Section>
      ) : null}

      {recipe.used_in.length ? (
        <Section title="用在">
          <RecipeLinks recipes={recipe.used_in} />
        </Section>
      ) : null}

      <DetailActions
        kind="recipe"
        id={recipe.id}
        name={recipe.display_name}
        editTo={`/edit/recipes/${recipe.id}`}
      />
    </article>
  )
}
