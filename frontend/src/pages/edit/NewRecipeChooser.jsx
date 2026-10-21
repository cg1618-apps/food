// Frontend: how a new recipe starts - /edit/recipes/new before a choice.
//
// Two ways, one section each: 空白, the empty form; 複製另一份食譜, any
// recipe, found with the Typeahead over the recipe library. A choice is
// written into the URL (lib/newRecipe.js) - ?blank=1, ?from=<id> - and RecipeForm
// opens the form on it; Back comes here again. ?dish=<id>, from a dish page's
// 「＋ 新增食譜」, is kept through whichever is chosen, and said here.
import { useNavigate, useSearchParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import Typeahead from '../../components/forms/Typeahead'
import { Button, Section } from '../../components/ui/primitives'
import { useApiQuery } from '../../hooks/useApi'
import { chosenSearch, newRecipeStart } from '../../lib/newRecipe'

export default function NewRecipeChooser() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { dish: dishId } = newRecipeStart(searchParams)
  const dish = useApiQuery(endpoints.dishes.detail(dishId), null, { enabled: dishId !== null })

  const choose = (choice) => navigate({ search: chosenSearch(searchParams, choice) })

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <header className="space-y-1">
        <h1 className="font-display text-2xl font-bold">新增食譜</h1>
        <p className="text-sm text-text-muted">
          從哪裡開始？
          {dish.data ? <>這份食譜會放在「{dish.data.display_name}」底下。</> : null}
        </p>
      </header>

      <Section title="空白">
        <p className="text-sm text-text-muted">一張空白的表單。</p>
        <div>
          <Button kind="primary" onClick={() => choose({ blank: true })}>
            空白食譜
          </Button>
        </div>
      </Section>

      <Section title="複製另一份食譜">
        <p className="text-sm text-text-muted">
          帶入那份食譜的材料、步驟、做法、器材、份量、時間、保存和筆記；名稱、來源、狀態和圖片不複製。
        </p>
        <Typeahead
          sources={['recipe']}
          label="要複製的食譜"
          placeholder="輸入食譜或料理名稱…"
          onSelect={(option) => choose({ from: option.id })}
          className="sm:max-w-md"
        />
      </Section>
    </div>
  )
}
