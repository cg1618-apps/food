// Frontend: one dish, /dishes/:id - 照燒雞腿排 in general, and every recipe
// that makes it.
//
// One reading column, as the recipe's page is: the pictures; kind, course,
// region and what else it serves as; the names; the labels; the description;
// then 食譜 - the dish's recipes as covers (the recipe library's cards), with
// 「＋ 新增食譜」 opening the recipe form with this dish already chosen
// (`?dish=<id>`); and 用在 - the recipes whose lines use this dish, which is
// what a sauce's page is mostly for. Every section with nothing in it is left
// out, except 食譜, whose add button is the way to give a new dish a recipe.
import { Link, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import CoverGrid from '../../components/layout/CoverGrid'
import { DetailActions, DetailStatus, LabelLinks, Prose, RecipeLinks } from '../../components/layout/Detail'
import Gallery from '../../components/ui/Gallery'
import { Badge, Chip, LinkButton, Section } from '../../components/ui/primitives'
import { fixedLabel, useApiQuery, useFixedVocabularies } from '../../hooks/useApi'

const names = (refs) => (refs?.length ? refs.map((ref) => ref.display_name).join('、') : null)

// A recipe of this dish as a cover card: its own name when it has one (its
// display name is the dish's otherwise), its authors and status.
const recipeCard = (recipe) => ({
  cover: recipe.cover,
  title: recipe.display_name,
  meta: [names(recipe.authors), recipe.status?.display_name].filter(Boolean).join(' · '),
  badges: recipe.written_up ? null : <Badge kind="bookmark" />,
})

export default function Dish() {
  const { id } = useParams()
  const query = useApiQuery(endpoints.dishes.detail(id))
  const fixed = useFixedVocabularies()
  const dish = query.data

  if (!dish) {
    return (
      <DetailStatus
        query={query}
        missing="找不到這道料理。"
        back={<LinkButton to="/dishes">回到料理庫</LinkButton>}
      />
    )
  }

  const otherNames = [dish.name_cn, dish.name_en, dish.name_alt].filter(
    (name) => name && name !== dish.display_name,
  )

  return (
    <article className="mx-auto max-w-2xl space-y-8">
      <Gallery images={dish.images} title={dish.display_name} />

      <header className="space-y-3">
        <p className="flex flex-wrap items-center gap-2 text-sm text-text-muted">
          <Chip tone={dish.kind === 'sauce' ? 'brand' : 'neutral'}>
            {fixedLabel(fixed.data?.dish_kinds, dish.kind)}
          </Chip>
          {dish.course ? (
            <Link to={`/dishes?course=${dish.course.id}`} className="hover:text-brand">
              {dish.course.display_name}
            </Link>
          ) : null}
          {dish.region ? (
            <Link to={`/dishes?region=${dish.region.id}`} className="hover:text-brand">
              {dish.region.display_name}
            </Link>
          ) : null}
          {dish.serves_as.length ? <span>也可以當作 {names(dish.serves_as)}</span> : null}
        </p>
        <h1 className="text-3xl font-bold leading-tight">{dish.display_name}</h1>
        {otherNames.length ? <p className="text-text-muted">{otherNames.join(' · ')}</p> : null}
        <LabelLinks labels={dish.labels} to={(label) => `/dishes?label=${label.id}`} />
      </header>

      <Prose>{dish.description}</Prose>

      <Section
        title="食譜"
        actions={
          <LinkButton to={`/edit/recipes/new?dish=${dish.id}`} size="sm">
            ＋ 新增食譜
          </LinkButton>
        }
      >
        {dish.recipes.length ? (
          <CoverGrid items={dish.recipes} itemTo={(recipe) => `/recipes/${recipe.id}`} card={recipeCard} />
        ) : (
          <p className="text-sm text-text-faint">還沒有食譜。</p>
        )}
      </Section>

      {dish.used_in.length ? (
        <Section title="用在">
          <RecipeLinks recipes={dish.used_in} />
        </Section>
      ) : null}

      <DetailActions kind="dish" id={dish.id} name={dish.display_name} editTo={`/edit/dishes/${dish.id}`} />
    </article>
  )
}
