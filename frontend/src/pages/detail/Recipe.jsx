// Frontend: one recipe, /recipes/:id.
//
// A placeholder until the detail pages land.
import Placeholder from '../../components/layout/Placeholder'
import { LinkButton } from '../../components/ui/primitives'

export default function Recipe() {
  return <Placeholder title="食譜" action={<LinkButton to="/recipes">回到食譜庫</LinkButton>} />
}
