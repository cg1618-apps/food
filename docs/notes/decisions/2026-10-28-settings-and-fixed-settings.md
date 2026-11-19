# The vocabularies are split between 設定 and 未來固定設定

Some vocabularies are system options rather than the owner's data - 食材分類,
常用食材, 類別, 狀態, 難易度, 材料分組, 步驟分組, 做法 - and are expected to be
fixed in code eventually; they stay editable only because the app is still
changing a lot. The owner wanted them on a page of their own, named for that,
so 設定 holds only what stays theirs to grow: 標籤, 地區, 來源, 作者 and 器材,
beside the way into 圖片.

- **One component over one set of tab definitions**
  (`components/settings/SettingsPage.jsx`, `settingsTabs.jsx`), not two
  copies, so moving a vocabulary between the pages - or fixing one later - is a
  line moved between two lists.
- **Tab ids are shared by both pages**, and a `?tab=` naming the other page's
  tab redirects there with `replace`, so any link to a tab still lands and
  Back does not bounce through the redirect.

Rejected: **a second section in the navigation**, which would spend a phone
column on pages visited rarely and by one person. 未來固定設定 belongs to
設定's section, reached by a button from 設定.
