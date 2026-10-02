// Frontend: the recipe library, /recipes - the app's front page.
//
// A placeholder until the library scaffold lands.
import Placeholder from '../../components/layout/Placeholder'
import { LinkButton } from '../../components/ui/primitives'

export default function RecipeLibrary() {
  return (
    <Placeholder
      title="食譜"
      note="食譜庫還在整理中。"
      action={
        <LinkButton kind="primary" to="/edit/recipes/new">
          新增食譜
        </LinkButton>
      }
    />
  )
}
