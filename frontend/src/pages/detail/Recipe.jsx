// Frontend: one recipe, /recipes/:id.
//
// One reading column, in the order a cook reads it: the pictures; the dish
// it makes - a link, with the dish's kind, course, region, serves-as and
// labels shown read-only, since they are the dish's and edited there; the
// recipe's name and a meta line (servings, time, methods, equipment); the
// status, changeable here; where it came from; 其他版本, the dish's other
// recipes; the ingredients and the steps, each in its groups
// (lib/recipeGroups.js) - the ungrouped rows first, then a block per group
// under its name, ordinary steps numbered through every group, an optional
// step marked 可省略 and a 備註 drawn as a callout; storage and notes. A line
// naming a dish links to the dish. Every section with nothing in it is left
// out, so a recipe saved as a bookmark is a short page rather than a page of
// empties.
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
import { cx } from '../../lib/cx'
import { linkHost } from '../../lib/format'
import { lineBlocks, stepBlocks } from '../../lib/recipeGroups'
import { NOTE } from '../../lib/steps'

const names = (refs) => (refs?.length ? refs.map((ref) => ref.display_name).join('、') : null)

// A status change moves this recipe's reads and the library's status filter
// and column - all under the recipes prefix - the statuses' usage counts, and
// the dish page's list of its recipes.
const STATUS_INVALIDATE = [endpoints.recipes.list(), endpoints.statuses.list(), endpoints.dishes.list()]

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
  if (line.sub_dish) {
    return (
      <Link to={`/dishes/${line.sub_dish.id}`} className="text-brand hover:underline">
        {line.sub_dish.display_name}
      </Link>
    )
  }
  return null
}

function Lines({ blocks }) {
  return blocks.map((group) => (
    <div key={group.key} className="space-y-1">
      {group.heading ? <h3 className="text-sm font-bold text-text-muted">{group.heading}</h3> : null}
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

// One block per group, as the lines are. An ordinary step has its number in
// a disc; an optional one a 可省略 chip in that place and slightly muted
// text; a note is a ruled, tinted callout with no number at all
// (lib/steps.js). `kindLabel` is the fixed list's label for a kind.
function Steps({ blocks, kindLabel }) {
  return blocks.map((group) => (
    <div key={group.key} className="space-y-2">
      {group.heading ? <h3 className="text-sm font-bold text-text-muted">{group.heading}</h3> : null}
      <ol className="space-y-3">
        {group.rows.map((step) =>
          step.kind === NOTE ? (
            <li key={step.id} className="space-y-0.5 rounded-md border-l-4 border-border-strong bg-surface-2 px-3 py-2">
              <p className="text-xs font-bold text-text-muted">{kindLabel(NOTE)}</p>
              <p className="whitespace-pre-line text-sm leading-relaxed">{step.body}</p>
            </li>
          ) : (
            <li key={step.id} className="flex gap-3">
              {step.number ? (
                <span
                  aria-hidden="true"
                  className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-brand-soft font-display text-sm font-bold text-brand"
                >
                  {step.number}
                </span>
              ) : (
                <Chip className="mt-0.5 shrink-0">{kindLabel(step.kind)}</Chip>
              )}
              <p className={cx('whitespace-pre-line leading-relaxed', !step.number && 'text-text-muted')}>
                {step.number ? <span className="sr-only">第 {step.number} 步：</span> : null}
                {step.body}
              </p>
            </li>
          ),
        )}
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

  const { dish } = recipe
  const meta = [
    recipe.servings ? `份量 ${recipe.servings}` : null,
    recipe.time ? `時間 ${recipe.time}` : null,
    names(recipe.methods),
    names(recipe.equipment),
  ].filter(Boolean)
  const lines = lineBlocks(recipe)
  const steps = stepBlocks(recipe)

  return (
    <article className="mx-auto max-w-2xl space-y-8">
      <Gallery images={recipe.images} title={recipe.display_name} />

      <header className="space-y-3">
        <p className="flex flex-wrap items-center gap-2 text-sm text-text-muted">
          <Link to={`/dishes/${dish.id}`} className="font-medium text-brand hover:underline">
            {dish.display_name}
          </Link>
          {dish.kind === 'sauce' ? <Chip tone="brand">{fixedLabel(fixed.data?.dish_kinds, dish.kind)}</Chip> : null}
          {dish.course ? (
            <Link to={`/recipes?course=${dish.course.id}`} className="hover:text-brand">
              {dish.course.display_name}
            </Link>
          ) : null}
          {dish.region ? <span>{dish.region.display_name}</span> : null}
          {dish.serves_as.length ? <span>也可以當作 {names(dish.serves_as)}</span> : null}
          {recipe.written_up ? null : <Badge kind="bookmark" />}
        </p>
        <h1 className="text-3xl font-bold leading-tight">{recipe.display_name}</h1>
        {recipe.name ? <p className="text-text-muted">{dish.display_name} 的一份食譜</p> : null}
        {meta.length ? <p className="text-sm text-text-muted">{meta.join(' · ')}</p> : null}
        <StatusControl recipe={recipe} />
        <LabelLinks labels={dish.labels} to={(label) => `/recipes?label=${label.id}`} />
      </header>

      {recipe.sources.length ? (
        <Section title="來源">
          <Sources sources={recipe.sources} />
        </Section>
      ) : null}

      {recipe.other_recipes.length ? (
        <Section title="其他版本">
          <RecipeLinks recipes={recipe.other_recipes} />
        </Section>
      ) : null}

      {lines.length ? (
        <Section title="材料">
          <div className="space-y-4">
            <Lines blocks={lines} />
          </div>
        </Section>
      ) : null}

      {steps.length ? (
        <Section title="步驟">
          <div className="space-y-5">
            <Steps blocks={steps} kindLabel={(kind) => fixedLabel(fixed.data?.step_kinds, kind)} />
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

      <DetailActions
        kind="recipe"
        id={recipe.id}
        name={recipe.display_name}
        editTo={`/edit/recipes/${recipe.id}`}
      />
    </article>
  )
}
