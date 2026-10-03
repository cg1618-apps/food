// Frontend: search the library as you type, and pick one.
//
// Diverges from media's ComboBox on purpose (docs/notes/decisions.md): that
// one filters a list it was handed, which here would mean downloading every
// ingredient and dish for every line of a recipe. This one asks the server
// - the list endpoints' `q`, which matches every name slot and alias - after
// the typing settles, and is driven from the keyboard: Up / Down move through
// the options, Enter picks, Escape closes. Handed `items` - a list small
// enough to hold whole, the authors - it filters that in the browser instead
// and asks nothing.
//
// It only PICKS. What a pick means - a recipe line's target, a recipe's dish,
// a merge target - is the caller's, through `onSelect(option)`; the box
// clears itself afterwards. Options are lib/typeahead.js's:
// { type: 'ingredient' | 'dish' | 'recipe' | 'item' | 'new' | 'new-dish', id,
// label, detail, needsDetail, kind }.
//
//   sources      which libraries to search: ['ingredient'], ['dish'] or both;
//                or ['recipe'] - the new-recipe chooser's 複製另一份食譜
//   items        rows ({ id, display_name, name_cn, name_en }) to filter in
//                the browser instead of searching; options are type 'item'
//   onSelect     (option) => void
//   allowNew     offer 「新增 'xxx'」 when nothing matches exactly
//   newHint      the words beside 「新增」, saying what the save will make
//   allowNewDish offer 「新增料理 'xxx'」 as well - a recipe line, which may
//                name a dish (a 醬料) that does not exist yet
//   newDishHint  the words beside that one
//   exclude      { ingredient: [ids], dish: [ids] } never offered
//   onQueryChange (text) => void - what is typed and not yet picked, '' after
//                a pick. A caller that refuses to save over unpicked text
//                (a line naming nothing, a parent nobody chose) needs it: the
//                box is otherwise the only thing that knows the text is there.
//   label        the input's accessible name
//   disabled     turns the box off (a list still saving its last change)
//   placeholder, autoFocus, className
import { keepPreviousData } from '@tanstack/react-query'
import { useId, useState } from 'react'

import { endpoints } from '../../api/endpoints'
import { useApiQuery } from '../../hooks/useApi'
import { useDebouncedValue } from '../../hooks/useDebouncedValue'
import { cx } from '../../lib/cx'
import { localResults, mergeResults, stepActive } from '../../lib/typeahead'
import { Badge, Chip, Input } from '../ui/primitives'

const TYPE_WORDS = { ingredient: '食材', dish: '料理', recipe: '食譜' }

/**
 * What a typeahead chose, shown in its place: the name (a link when `to` is
 * given), 待補 when it is still only a name, and 更換 to search again. Every
 * caller that holds one pick - a line's target, "version of", a parent, a
 * merge target - draws it with this, so a choice looks the same everywhere.
 */
export function Picked({ label, stub = false, tag, onClear, clearLabel = '更換', className }) {
  return (
    <div
      className={cx(
        'flex min-h-[2.125rem] items-center gap-2 rounded-md border border-brand/40 bg-brand-soft px-2.5 py-1 text-sm',
        className,
      )}
    >
      <span className="min-w-0 flex-1 truncate font-medium text-text">{label}</span>
      {stub ? <Badge kind="stub" /> : null}
      {tag ? <span className="shrink-0 text-xs text-text-faint">{tag}</span> : null}
      {onClear ? (
        <button
          type="button"
          onClick={onClear}
          className="shrink-0 rounded-sm px-1 text-xs text-text-muted hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
        >
          {clearLabel}
        </button>
      ) : null}
    </div>
  )
}

export default function Typeahead({
  sources = ['ingredient', 'dish'],
  items,
  onSelect,
  onQueryChange,
  allowNew = false,
  newHint = '（存檔時建立待補食材）',
  allowNewDish = false,
  newDishHint = '（存檔時建立醬料）',
  exclude,
  label = '搜尋',
  placeholder = '輸入名稱搜尋…',
  autoFocus = false,
  disabled = false,
  className,
}) {
  const listId = useId()
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState(-1)
  const settled = useDebouncedValue(query.trim(), 250)

  const local = items !== undefined
  const searchIngredients = !local && sources.includes('ingredient') && settled !== ''
  const searchDishes = !local && sources.includes('dish') && settled !== ''
  const searchRecipes = !local && sources.includes('recipe') && settled !== ''
  const ingredients = useApiQuery(
    endpoints.ingredients.list(),
    { q: settled },
    { enabled: searchIngredients, placeholderData: keepPreviousData },
  )
  const dishes = useApiQuery(
    endpoints.dishes.list(),
    { q: settled },
    { enabled: searchDishes, placeholderData: keepPreviousData },
  )
  const recipes = useApiQuery(
    endpoints.recipes.list(),
    { q: settled },
    { enabled: searchRecipes, placeholderData: keepPreviousData },
  )

  const typed = query.trim()
  const searching =
    !local &&
    (typed !== settled ||
      (searchIngredients && ingredients.isFetching) ||
      (searchDishes && dishes.isFetching) ||
      (searchRecipes && recipes.isFetching))
  // 「新增」 waits for the search to answer: offered before it, a quick Enter
  // makes a stub named after something the library already has.
  let options = []
  if (typed && local) {
    options = localResults({ items, query: typed, allowNew })
  } else if (typed) {
    options = mergeResults({
      ingredients: searchIngredients ? ingredients.data : [],
      dishes: searchDishes ? dishes.data : [],
      recipes: searchRecipes ? recipes.data : [],
      query: typed,
      exclude,
      allowNew: allowNew && !searching,
      allowNewDish: allowNewDish && !searching,
    })
  }
  const showList = open && typed !== ''
  const activeIndex = active < options.length ? active : -1

  function changeQuery(text) {
    setQuery(text)
    onQueryChange?.(text)
  }

  function pick(option) {
    onSelect(option)
    changeQuery('')
    setOpen(false)
    setActive(-1)
  }

  function onKeyDown(event) {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault()
      setOpen(true)
      setActive(stepActive(activeIndex, event.key === 'ArrowDown' ? 1 : -1, options.length))
    } else if (event.key === 'Enter') {
      // Never submits the form around it: Enter in a search box means "this
      // one", and a half-typed name saved as the recipe is not what was asked.
      event.preventDefault()
      const option = options[activeIndex] ?? (options.length === 1 ? options[0] : null)
      if (showList && option) pick(option)
    } else if (event.key === 'Escape' && showList) {
      // Closes the list, not the dialog this box may be sitting in.
      event.preventDefault()
      event.stopPropagation()
      setOpen(false)
      setActive(-1)
    }
  }

  return (
    <div className={cx('relative', className)}>
      <Input
        type="text"
        role="combobox"
        aria-label={label}
        aria-autocomplete="list"
        aria-expanded={showList}
        aria-controls={listId}
        aria-activedescendant={activeIndex >= 0 ? `${listId}-${activeIndex}` : undefined}
        autoComplete="off"
        autoFocus={autoFocus}
        disabled={disabled}
        placeholder={placeholder}
        value={query}
        onChange={(event) => {
          changeQuery(event.target.value)
          setOpen(true)
          setActive(-1)
        }}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        onKeyDown={onKeyDown}
      />

      {showList ? (
        <ul
          id={listId}
          role="listbox"
          aria-label={label}
          className="absolute z-40 mt-1 max-h-64 w-full overflow-y-auto rounded-md border border-border bg-surface py-1 shadow-lg"
        >
          {options.length === 0 ? (
            <li className="px-3 py-2 text-sm text-text-faint">{searching ? '搜尋中…' : '找不到'}</li>
          ) : (
            options.map((option, index) => (
              <li
                key={option.key}
                id={`${listId}-${index}`}
                role="option"
                aria-selected={index === activeIndex}
                // mousedown would blur the input and close the list before
                // the click lands.
                onMouseDown={(event) => event.preventDefault()}
                onClick={() => pick(option)}
                onMouseEnter={() => setActive(index)}
                className={cx(
                  'flex cursor-pointer items-center gap-2 px-3 py-1.5 text-sm',
                  index === activeIndex ? 'bg-brand-soft text-brand' : 'text-text',
                )}
              >
                {option.type === 'new' || option.type === 'new-dish' ? (
                  <span>
                    {option.type === 'new-dish' && allowNew ? '新增料理' : '新增'}「<strong>{option.label}</strong>」
                    <span className="ml-1 text-xs text-text-faint">
                      {option.type === 'new-dish' ? newDishHint : newHint}
                    </span>
                  </span>
                ) : (
                  <>
                    <span className="min-w-0 flex-1 truncate">
                      {option.label}
                      {option.detail ? (
                        <span className="ml-2 text-xs text-text-faint">{option.detail}</span>
                      ) : null}
                    </span>
                    {option.needsDetail ? <Badge kind="stub" /> : null}
                    {option.kind === 'sauce' ? <Chip>醬料</Chip> : null}
                    {!local && sources.length > 1 ? (
                      <span className="shrink-0 text-xs text-text-faint">{TYPE_WORDS[option.type]}</span>
                    ) : null}
                  </>
                )}
              </li>
            ))
          )}
        </ul>
      ) : null}
    </div>
  )
}
