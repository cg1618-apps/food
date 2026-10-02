// Frontend: 設定, /edit/settings - every vocabulary the rest of the app is
// filed by, on one page, and the way into the image library.
//
// One page rather than one per vocabulary: each is a short list maintained
// the same way, and five screens with six rows each would be five places to
// look for the one you meant. Each section is its own query with its own
// loading, error and empty state, so one vocabulary failing to load does not
// blank the others.
//
// What a change here makes stale is named per section: a renamed course is
// shown on every recipe, a renamed method on recipes and on ingredient
// heating rows, a renamed label on all three kinds of owner.
import { endpoints } from '../../api/endpoints'
import CategoryEditor from '../../components/settings/CategoryEditor'
import VocabularyEditor from '../../components/settings/VocabularyEditor'
import { LinkButton } from '../../components/ui/primitives'
import { inUseMessage } from '../../lib/vocabulary'

const RECIPES = endpoints.recipes.list()
const INGREDIENTS = endpoints.ingredients.list()
const NOTES = endpoints.notes.list()

// The three factory vocabularies: one shape, one count (`usage_count`, the
// RESTRICT references that would stop a delete).
const FACTORY = [
  {
    key: 'courses',
    title: '類別',
    hint: '食譜放在哪一類：主菜、湯、甜點…',
    addLabel: '新增類別',
    invalidate: [endpoints.courses.list(), RECIPES],
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

export default function Settings() {
  return (
    <div className="space-y-10">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-bold">設定</h1>
        <LinkButton to="/edit/images" size="sm">
          圖片庫
        </LinkButton>
      </div>

      <CategoryEditor />

      <VocabularyEditor
        title="標籤"
        endpoints={endpoints.labels}
        invalidate={[endpoints.labels.list(), INGREDIENTS, RECIPES, NOTES]}
        ordered={false}
        hint="跨分類的標記，食材、食譜和筆記都可以貼。依名稱排列。"
        addLabel="新增標籤"
        meta={(row) =>
          row.usage_count
            ? `食材 ${row.ingredient_count} · 食譜 ${row.recipe_count} · 筆記 ${row.note_count}`
            : '沒有使用'
        }
        confirmText={(row) =>
          row.usage_count
            ? `它會從 ${row.usage_count} 個項目上拿掉；那些項目本身不受影響。`
            : '沒有任何項目貼著它。'
        }
        refusal={(_row, error) => error?.message}
      />

      {FACTORY.map(({ key, ...section }) => (
        <VocabularyEditor
          key={key}
          endpoints={endpoints[key]}
          {...section}
          meta={usageMeta}
          confirmText={(row) =>
            row.usage_count
              ? `「${row.display_name}」還用在 ${row.usage_count} 個地方，刪除會被拒絕；先把那些改掉。`
              : '沒有任何地方使用它。'
          }
          refusal={(row, error) => inUseMessage(row.display_name, error)}
        />
      ))}
    </div>
  )
}
