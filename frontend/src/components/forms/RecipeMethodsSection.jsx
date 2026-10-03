// Frontend: 做法、器材 - the cooking methods and equipment a recipe uses, as
// the recipe form and the template form both pick them: chips from 設定's
// lists, in their order.
//
//   methodIds, equipmentIds   the chosen ids
//   onChange                  (field, ids) => void, field being 'method_ids'
//                             or 'equipment_ids' - the payload's names
import { endpoints } from '../../api/endpoints'
import { useApiQuery } from '../../hooks/useApi'
import { Section } from '../ui/primitives'
import ChipPicker from './ChipPicker'

export default function RecipeMethodsSection({ methodIds, equipmentIds, onChange }) {
  const methods = useApiQuery(endpoints.methods.list())
  const equipment = useApiQuery(endpoints.equipment.list())
  return (
    <Section title="做法、器材">
      <div className="space-y-1">
        <span className="text-sm font-medium text-text-muted">做法</span>
        <ChipPicker
          label="做法"
          options={methods.data}
          value={methodIds}
          onChange={(value) => onChange('method_ids', value)}
          empty="還沒有做法，可以在設定裡新增。"
        />
      </div>
      <div className="space-y-1">
        <span className="text-sm font-medium text-text-muted">器材</span>
        <ChipPicker
          label="器材"
          options={equipment.data}
          value={equipmentIds}
          onChange={(value) => onChange('equipment_ids', value)}
          empty="還沒有器材，可以在設定裡新增。"
        />
      </div>
    </Section>
  )
}
