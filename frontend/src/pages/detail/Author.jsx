// Frontend: one author, /authors/:id - who a recipe came from, and every
// recipe of theirs in the library.
//
// One reading column, as the other detail pages: the pictures; the names;
// the links, each opening in a new tab; the 備註 with its line breaks; then
// 食譜 - the recipes whose sources name this author, as covers (the recipe
// library's cards), with 「在食譜庫篩選」 to the recipe library filtered to the
// author, where the rest of the sidebar can narrow it further. The one place
// an author's links, 備註 and pictures are read; a recipe source's author
// links here.
import { Link, useParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import CoverGrid from '../../components/layout/CoverGrid'
import { DetailActions, DetailStatus, Prose } from '../../components/layout/Detail'
import Gallery from '../../components/ui/Gallery'
import { Badge, LinkButton, Section } from '../../components/ui/primitives'
import { Empty } from '../../components/ui/states'
import { useApiQuery } from '../../hooks/useApi'
import { linkText } from '../../lib/format'

// A recipe as a cover card: its own name (its dish's when it has none), its
// dish under it when the two differ, and its status.
const recipeCard = (recipe) => ({
  cover: recipe.cover,
  title: recipe.display_name,
  subtitle: recipe.dish.display_name !== recipe.display_name ? recipe.dish.display_name : null,
  meta: recipe.status?.display_name ?? null,
  badges: recipe.written_up ? null : <Badge kind="bookmark" />,
})

export default function Author() {
  const { id } = useParams()
  const query = useApiQuery(endpoints.authors.detail(id))
  const author = query.data

  if (!author) {
    return (
      <DetailStatus
        query={query}
        missing="找不到這位作者。"
        back={<LinkButton to="/authors">回到作者庫</LinkButton>}
      />
    )
  }

  const otherNames = [author.name_cn, author.name_en].filter(
    (name) => name && name !== author.display_name,
  )

  return (
    <article className="mx-auto max-w-2xl space-y-8">
      <Gallery images={author.images} title={author.display_name} />

      <header className="space-y-3">
        <p className="text-sm text-text-muted">
          <Link to="/authors" className="hover:text-brand">
            作者
          </Link>
        </p>
        <h1 className="text-3xl font-bold leading-tight">{author.display_name}</h1>
        {otherNames.length ? <p className="text-text-muted">{otherNames.join(' · ')}</p> : null}
        {author.links.length ? (
          <ul aria-label="連結" className="flex flex-wrap gap-x-4 gap-y-1 text-sm">
            {author.links.map((link, index) => (
              <li key={index} className="min-w-0 truncate">
                <a
                  href={link.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-brand hover:underline"
                >
                  {link.label ?? linkText(link.url)} ↗
                </a>
              </li>
            ))}
          </ul>
        ) : null}
      </header>

      <Prose>{author.notes}</Prose>

      <Section
        title="食譜"
        actions={
          author.recipes.length ? (
            <LinkButton to={`/recipes?author=${author.id}`} size="sm">
              在食譜庫篩選
            </LinkButton>
          ) : null
        }
      >
        {author.recipes.length ? (
          <CoverGrid items={author.recipes} itemTo={(recipe) => `/recipes/${recipe.id}`} card={recipeCard} />
        ) : (
          <Empty>還沒有食譜的來源寫著這位作者。</Empty>
        )}
      </Section>

      <DetailActions
        kind="author"
        id={author.id}
        name={author.display_name}
        editTo={`/edit/authors/${author.id}`}
      />
    </article>
  )
}
