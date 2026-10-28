// Frontend: 未來固定設定, /edit/fixed-settings - the system options the app
// is built around (食材分類, 常用食材, 類別, 狀態, 難易度, 材料分組, 步驟分組,
// 做法), a tab each. They are expected to become fixed later and stay
// editable here only while the app is still changing a lot.
//
// The page's shape is components/settings/SettingsPage.jsx's and the tabs are
// components/settings/settingsTabs.jsx's; the reason for the page is in
// docs/notes/decisions.md.
import SettingsPage from '../../components/settings/SettingsPage'
import {
  FIXED_SETTINGS_TABS,
  SETTINGS_PATH,
  SETTINGS_TABS,
} from '../../components/settings/settingsTabs'
import { LinkButton } from '../../components/ui/primitives'

export default function FixedSettings() {
  return (
    <SettingsPage
      title="未來固定設定"
      intro="這些是系統的選項，之後會固定下來；現在 app 還在常常調整，所以先留在這裡可以編輯。"
      tabs={FIXED_SETTINGS_TABS}
      elsewhere={{ path: SETTINGS_PATH, tabs: SETTINGS_TABS }}
      actions={
        <LinkButton to={SETTINGS_PATH} size="sm">
          回到設定
        </LinkButton>
      }
    />
  )
}
