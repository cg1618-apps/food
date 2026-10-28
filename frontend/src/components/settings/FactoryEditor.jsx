// Frontend: one factory vocabulary's tab on 設定 or 未來固定設定 - a
// VocabularyEditor whose rows carry `usage_count`, the RESTRICT references
// that would stop a delete, said in the row, in the delete dialog and in the
// refusal. The sections themselves are components/settings/settingsTabs.jsx's.
//
//   vocabulary   the api/endpoints.js group
//   ...section   the rest of VocabularyEditor's props (title, hint, addLabel,
//                invalidate, ordered, details)
import { endpoints } from '../../api/endpoints'
import { inUseMessage } from '../../lib/vocabulary'
import VocabularyEditor from './VocabularyEditor'

const usageMeta = (row) => (row.usage_count ? `用在 ${row.usage_count} 個地方` : '沒有使用')

export default function FactoryEditor({ vocabulary, ...section }) {
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
