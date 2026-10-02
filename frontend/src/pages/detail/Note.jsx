// Frontend: one kitchen note, /notes/:id.
//
// A placeholder until the detail pages land.
import Placeholder from '../../components/layout/Placeholder'
import { LinkButton } from '../../components/ui/primitives'

export default function Note() {
  return <Placeholder title="筆記" action={<LinkButton to="/notes">回到筆記庫</LinkButton>} />
}
