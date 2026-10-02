// Frontend: the pieces the three detail pages share.
//
// Each page is one reading column - a header, then titled sections, every
// section hidden when there is nothing in it - and ends the same way: an edit
// link and a delete. What is shared lives here so a recipe, an ingredient and
// a note read as one product:
//
//   DetailStatus   loading, a missing row (404 - a link to the library), or
//                  any other error; renders nothing once there is data
//   Prose          a block of written notes, line breaks kept
//   LabelLinks     a row's labels, each a link to its library filtered by it
//   RecipeLinks    a short list of recipes as links ("used in", versions)
//   DetailActions  編輯 and 刪除, the latter through the one DeleteDialog
import { useState } from 'react'
import { Link } from 'react-router-dom'

import DeleteDialog from '../forms/DeleteDialog'
import { Button, Chip, LinkButton } from '../ui/primitives'
import { Empty, ErrorNote, Loading } from '../ui/states'

export function DetailStatus({ query, missing, back }) {
  if (query.isPending) return <Loading />
  if (query.error?.status === 404) {
    return <Empty action={back}>{missing}</Empty>
  }
  if (query.error) return <ErrorNote error={query.error} />
  return null
}

// whitespace-pre-line, not a markdown renderer: notes are written as short
// lines and read on a phone, and a renderer is a dependency these pages have
// not earned.
export function Prose({ children }) {
  if (!children) return null
  return <p className="whitespace-pre-line leading-relaxed text-text">{children}</p>
}

// `to(label)` is the library URL filtered by that label.
export function LabelLinks({ labels, to }) {
  if (!labels?.length) return null
  return (
    <div className="flex flex-wrap gap-1">
      {labels.map((label) => (
        <Link key={label.id} to={to(label)} className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand">
          <Chip className="hover:border-brand hover:text-brand">{label.display_name}</Chip>
        </Link>
      ))}
    </div>
  )
}

// `describe(recipe)` adds a faint word after a name, e.g. 原版.
export function RecipeLinks({ recipes, describe }) {
  return (
    <ul className="flex flex-wrap gap-x-4 gap-y-1">
      {recipes.map((recipe) => (
        <li key={recipe.id}>
          <Link to={`/recipes/${recipe.id}`} className="text-brand hover:underline">
            {recipe.display_name}
          </Link>
          {describe?.(recipe) ? <span className="ml-1 text-xs text-text-faint">{describe(recipe)}</span> : null}
        </li>
      ))}
    </ul>
  )
}

export function DetailActions({ kind, id, name, editTo, children }) {
  const [deleting, setDeleting] = useState(false)
  return (
    <div className="flex flex-wrap items-center gap-2 border-t border-border pt-4">
      <LinkButton to={editTo} kind="primary">
        編輯
      </LinkButton>
      {children}
      <Button kind="danger" className="ml-auto" onClick={() => setDeleting(true)}>
        刪除
      </Button>
      {deleting ? (
        <DeleteDialog kind={kind} id={id} name={name} onClose={() => setDeleting(false)} />
      ) : null}
    </div>
  )
}
