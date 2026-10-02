// Frontend: add or edit a recipe, /edit/recipes/new and /edit/recipes/:id.
//
// A placeholder until the forms land.
import { useParams } from 'react-router-dom'

import Placeholder from '../../components/layout/Placeholder'

export default function RecipeForm() {
  const { id } = useParams()
  return <Placeholder title={id ? '編輯食譜' : '新增食譜'} note="食譜表單還在整理中。" />
}
