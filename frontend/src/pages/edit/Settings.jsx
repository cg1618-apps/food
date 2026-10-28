// Frontend: 設定, /edit/settings - the vocabularies that stay the owner's to
// grow (標籤, 地區, 來源, 作者, 器材), a tab each, and the ways into the image
// library and 未來固定設定 (pages/edit/FixedSettings.jsx).
//
// The page's shape is components/settings/SettingsPage.jsx's and the tabs are
// components/settings/settingsTabs.jsx's; why the vocabularies are split
// across two pages is in docs/notes/decisions.md.
import SettingsPage from '../../components/settings/SettingsPage'
import {
  FIXED_SETTINGS_PATH,
  FIXED_SETTINGS_TABS,
  SETTINGS_TABS,
} from '../../components/settings/settingsTabs'
import { LinkButton } from '../../components/ui/primitives'

export default function Settings() {
  return (
    <SettingsPage
      title="設定"
      tabs={SETTINGS_TABS}
      elsewhere={{ path: FIXED_SETTINGS_PATH, tabs: FIXED_SETTINGS_TABS }}
      actions={
        <>
          <LinkButton to={FIXED_SETTINGS_PATH} size="sm">
            未來固定設定
          </LinkButton>
          <LinkButton to="/edit/images" size="sm">
            圖片庫
          </LinkButton>
        </>
      }
    />
  )
}
