// Frontend: the tabs of the two settings pages - 設定 (pages/edit/Settings.jsx)
// and 未來固定設定 (pages/edit/FixedSettings.jsx) - defined once, so a
// vocabulary moved from one page to the other is a line moved between the
// two lists at the bottom and nothing else.
//
// Every vocabulary the rest of the app is filed by is a tab on one of them.
// 未來固定設定 holds the system options expected to become fixed later and
// editable now only because the app is still changing; 設定 holds what stays
// the owner's to grow. A tab's `id` is what `?tab=` carries and must not
// change once links to it exist - it stayed the same across the split, which
// is what lets an old link be redirected (components/settings/SettingsPage.jsx).
//
// What a change here makes stale is named per vocabulary: a renamed course or
// region is shown on every dish and on its recipes' pages, a renamed status,
// difficulty, source platform, author or 材料分組 / 步驟分組 on every recipe, a
// renamed method on recipes and on ingredient heating rows, a renamed label on
// all three kinds of owner - ingredients, dishes and notes - and on the
// recipes that show their dish's. 標籤 is its own editor (LabelEditor): a
// section per library a label can belong to, and a label moved between them
// while unused. 常用食材 is not a vocabulary but an ordered pick of ingredients
// - the recipe form's chips - and makes only its own list stale.
//
// 作者 is a factory vocabulary with more than names, but its tab is a plain
// list like the rest - add, rename, delete. Its links, 備註 and pictures are
// edited on the author's own form, and each row's 編輯 goes there
// (/edit/authors/:id): one editor for them, not two.
import { endpoints } from '../../api/endpoints'
import { LinkButton } from '../ui/primitives'
import CategoryEditor from './CategoryEditor'
import CommonIngredientsEditor from './CommonIngredientsEditor'
import FactoryEditor from './FactoryEditor'
import LabelEditor from './LabelEditor'

export const SETTINGS_PATH = '/edit/settings'
export const FIXED_SETTINGS_PATH = '/edit/fixed-settings'

const DISHES = endpoints.dishes.list()
const RECIPES = endpoints.recipes.list()
const INGREDIENTS = endpoints.ingredients.list()

// An author's row links to the author's form, where its links, 備註 and
// pictures are edited.
const authorEditLink = (row) => (
  <LinkButton
    kind="ghost"
    size="sm"
    to={`/edit/authors/${row.id}`}
    aria-label={`編輯「${row.display_name}」`}
  >
    編輯
  </LinkButton>
)

// The ten factory vocabularies: one shape, one count (`usage_count`, the
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
    key: 'difficulties',
    title: '難易度',
    hint: '食譜做起來難不難：簡單、普通、困難…。食譜可以不選；表單和篩選依這裡的順序列出。',
    addLabel: '新增難易度',
    invalidate: [endpoints.difficulties.list(), RECIPES],
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
    hint: '食譜來源的作者，依名稱排列。在食譜表單打一個還沒有的名字，存檔時也會加進來。按「編輯」到作者的頁面加連結、備註和圖片。',
    addLabel: '新增作者',
    ordered: false,
    rowActions: authorEditLink,
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

// Every tab, by id: what the tab bar shows and what its panel renders.
const TAB_BY_ID = Object.fromEntries([
  ['categories', { id: 'categories', label: '食材分類', render: () => <CategoryEditor /> }],
  [
    'common-ingredients',
    { id: 'common-ingredients', label: '常用食材', render: () => <CommonIngredientsEditor /> },
  ],
  ['labels', { id: 'labels', label: '標籤', render: () => <LabelEditor /> }],
  ...FACTORY.map(({ key, vocabulary = key, ...section }) => [
    key,
    {
      id: key,
      label: section.title,
      render: () => <FactoryEditor vocabulary={vocabulary} {...section} />,
    },
  ]),
])

const pick = (ids) => ids.map((id) => TAB_BY_ID[id])

// The two pages' tabs, in order; the first entry is each page's default.
export const SETTINGS_TABS = pick(['labels', 'regions', 'platforms', 'authors', 'equipment'])

export const FIXED_SETTINGS_TABS = pick([
  'categories',
  'common-ingredients',
  'courses',
  'statuses',
  'difficulties',
  'line-groups',
  'step-groups',
  'methods',
])
