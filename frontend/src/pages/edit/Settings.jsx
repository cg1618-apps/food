// Frontend: 設定, /edit/settings - every vocabulary the rest of the app is
// filed by, a tab each, and the way into the image library.
//
// One page with tabs rather than one page per vocabulary: each is a short
// list maintained the same way, and a route each would be a page per handful
// of rows. Tabs rather than one long column, because the column grows with
// every vocabulary added and the one you meant ends up a long scroll away.
// The tab is in the URL (`?tab=courses`, hooks/useUrlTab.js); a missing or
// unknown one is the first. Only the selected tab's editor is mounted, so
// only its query runs, and one vocabulary failing to load blanks nothing
// else.
//
// TABS is the whole list: a new vocabulary is one entry there - an id for the
// URL, the label, and what its panel renders.
//
// What a change here makes stale is named per vocabulary: a renamed course or
// region is shown on every dish and on its recipes' pages, a renamed status,
// source platform, author or 材料分組 / 步驟分組 on every recipe, a renamed
// method on recipes and on ingredient heating rows, a renamed label on all
// three kinds of owner - ingredients, dishes and notes - and on the recipes
// that show their dish's. 常用食材 is not a vocabulary but an ordered pick of ingredients -
// the recipe form's chips - and makes only its own list stale.
import { endpoints } from '../../api/endpoints'
import CategoryEditor from '../../components/settings/CategoryEditor'
import CommonIngredientsEditor from '../../components/settings/CommonIngredientsEditor'
import VocabularyEditor from '../../components/settings/VocabularyEditor'
import { LinkButton, Tabs } from '../../components/ui/primitives'
import { useUrlTab } from '../../hooks/useUrlTab'
import { inUseMessage } from '../../lib/vocabulary'

const DISHES = endpoints.dishes.list()
const RECIPES = endpoints.recipes.list()
const INGREDIENTS = endpoints.ingredients.list()
const NOTES = endpoints.notes.list()

// The nine factory vocabularies: one shape, one count (`usage_count`, the
// RESTRICT references that would stop a delete). Authors are listed by name
// like labels, so they have no order to move by. `key` is the tab id and,
// unless `vocabulary` says otherwise, the api/endpoints.js group.
const FACTORY = [
  {
    key: 'courses',
    title: '類別',
    hint: '料理放在哪一類：主菜、湯、甜點…',
    addLabel: '新增類別',
    invalidate: [endpoints.courses.list(), DISHES, RECIPES],
  },
  {
    key: 'regions',
    title: '地區',
    hint: '料理是哪裡的菜：台式、中式、日式…。料理表單和篩選依這裡的順序列出。',
    addLabel: '新增地區',
    invalidate: [endpoints.regions.list(), DISHES, RECIPES],
  },
  {
    key: 'statuses',
    title: '狀態',
    hint: '食譜做到哪一步：想試、可煮、常煮…。新食譜預設排第一的那個。',
    addLabel: '新增狀態',
    invalidate: [endpoints.statuses.list(), RECIPES],
  },
  {
    key: 'platforms',
    title: '來源',
    hint: '食譜是在哪裡看到的：YouTube、網站、書…',
    addLabel: '新增來源',
    invalidate: [endpoints.platforms.list(), RECIPES],
  },
  {
    key: 'authors',
    title: '作者',
    hint: '食譜來源的作者，依名稱排列。在食譜表單打一個還沒有的名字，存檔時也會加進來。',
    addLabel: '新增作者',
    ordered: false,
    invalidate: [endpoints.authors.list(), RECIPES],
  },
  {
    key: 'line-groups',
    vocabulary: 'lineGroups',
    title: '材料分組',
    hint: '食譜的材料可以分組：主料、配料、調味料…。食譜表單加分組時，會先列出這裡的，依這裡的順序。',
    addLabel: '新增材料分組',
    invalidate: [endpoints.lineGroups.list(), RECIPES],
  },
  {
    key: 'step-groups',
    vocabulary: 'stepGroups',
    title: '步驟分組',
    hint: '食譜的步驟可以分組：備料、烹飪、醬汁…。食譜表單加分組時，會先列出這裡的，依這裡的順序。',
    addLabel: '新增步驟分組',
    invalidate: [endpoints.stepGroups.list(), RECIPES],
  },
  {
    key: 'methods',
    title: '做法',
    hint: '炒、蒸、烤…，食譜和食材的加熱方式共用這一份。',
    addLabel: '新增做法',
    invalidate: [endpoints.methods.list(), RECIPES, INGREDIENTS],
  },
  {
    key: 'equipment',
    title: '器材',
    hint: '食譜要用到的鍋具和機器。',
    addLabel: '新增器材',
    invalidate: [endpoints.equipment.list(), RECIPES],
  },
]

const usageMeta = (row) => (row.usage_count ? `用在 ${row.usage_count} 個地方` : '沒有使用')

function LabelEditor() {
  return (
    <VocabularyEditor
      title="標籤"
      endpoints={endpoints.labels}
      invalidate={[endpoints.labels.list(), INGREDIENTS, DISHES, RECIPES, NOTES]}
      ordered={false}
      hint="跨分類的標記，食材、料理和筆記都可以貼。依名稱排列。"
      addLabel="新增標籤"
      meta={(row) =>
        row.usage_count
          ? `食材 ${row.ingredient_count} · 料理 ${row.dish_count} · 筆記 ${row.note_count}`
          : '沒有使用'
      }
      confirmText={(row) =>
        row.usage_count
          ? `它會從 ${row.usage_count} 個項目上拿掉；那些項目本身不受影響。`
          : '沒有任何項目貼著它。'
      }
      refusal={(_row, error) => error?.message}
    />
  )
}

function FactoryEditor({ vocabulary, ...section }) {
  return (
    <VocabularyEditor
      endpoints={endpoints[vocabulary]}
      {...section}
      meta={usageMeta}
      confirmText={(row) =>
        row.usage_count
          ? `「${row.display_name}」還用在 ${row.usage_count} 個地方，刪除會被拒絕；先把那些改掉。`
          : '沒有任何地方使用它。'
      }
      refusal={(row, error) => inUseMessage(row.display_name, error)}
    />
  )
}

// The tabs, in order. `id` is what `?tab=` carries and must not change once
// links to it exist; the first entry is the default.
const TABS = [
  { id: 'categories', label: '食材分類', render: () => <CategoryEditor /> },
  { id: 'common-ingredients', label: '常用食材', render: () => <CommonIngredientsEditor /> },
  { id: 'labels', label: '標籤', render: () => <LabelEditor /> },
  ...FACTORY.map(({ key, vocabulary = key, ...section }) => ({
    id: key,
    label: section.title,
    render: () => <FactoryEditor vocabulary={vocabulary} {...section} />,
  })),
]

export default function Settings() {
  const [selected, select] = useUrlTab(TABS)
  const tab = TABS.find(({ id }) => id === selected)

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-bold">設定</h1>
        <LinkButton to="/edit/images" size="sm">
          圖片庫
        </LinkButton>
      </div>

      <Tabs label="設定" tabs={TABS} selected={selected} onSelect={select}>
        {/* Keyed by tab, so switching tabs never carries an editor's local
            state - an open rename, a half-typed add - into another. */}
        <div key={tab.id}>{tab.render()}</div>
      </Tabs>
    </div>
  )
}
