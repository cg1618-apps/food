// Frontend: how a new recipe starts - /edit/recipes/new before a choice.
//
// Three ways, one section each: 空白, the empty form; 從範本, one of the
// templates 設定 keeps, in their order; 複製另一份食譜, any recipe, found with
// the Typeahead over the recipe library. A choice is written into the URL
// (lib/newRecipe.js) - ?blank=1, ?template=<id>, ?from=<id> - and RecipeForm
// opens the form on it; Back comes here again. ?dish=<id>, from a dish page's
// 「＋ 新增食譜」, is kept through whichever is chosen, and said here.
import { useNavigate, useSearchParams } from 'react-router-dom'

import { endpoints } from '../../api/endpoints'
import Typeahead from '../../components/forms/Typeahead'
import { Button, LinkButton, Section } from '../../components/ui/primitives'
import { Empty, ErrorNote, Loading } from '../../components/ui/states'
import { useApiQuery } from '../../hooks/useApi'
import { chosenSearch, newRecipeStart } from '../../lib/newRecipe'

export default function NewRecipeChooser() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { dish: dishId } = newRecipeStart(searchParams)
  const dish = useApiQuery(endpoints.dishes.detail(dishId), null, { enabled: dishId !== null })
  const templates = useApiQuery(endpoints.templates.list())

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

      <Section title="從範本">
        <p className="text-sm text-text-muted">帶入範本的材料、步驟、做法、器材、份量和時間。</p>
        {templates.isPending ? <Loading /> : null}
        {templates.error ? <ErrorNote error={templates.error} /> : null}
        {templates.data?.length === 0 ? (
          <Empty
            action={
              <LinkButton to="/edit/settings?tab=templates" size="sm">
                到設定管理範本
              </LinkButton>
            }
          >
            還沒有範本。可以在設定的「範本」新增，或在食譜頁「存成範本」。
          </Empty>
        ) : null}
        {templates.data?.length ? (
          <ul aria-label="範本" className="grid gap-2 sm:grid-cols-2">
            {templates.data.map((template) => (
              <li key={template.id}>
                <button
                  type="button"
                  onClick={() => choose({ template: template.id })}
                  className="w-full rounded-md border border-border bg-surface px-3 py-2 text-left hover:border-brand hover:text-brand focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
                >
                  <span className="block font-medium">{template.name}</span>
                  <span className="block text-xs text-text-faint">
                    材料 {template.line_count} · 步驟 {template.step_count}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}
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
