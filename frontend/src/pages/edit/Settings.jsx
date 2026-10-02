// Frontend: 設定, /edit/settings - the vocabularies everything else is filed
// by, and the way into the image library.
//
// For now it hosts the existing categories-and-labels editor unchanged, so
// nothing that worked under /edit/vocabularies stops working. The full page -
// courses, cooking methods and equipment too, with rename and reorder -
// replaces it.
import { LinkButton } from '../../components/ui/primitives'
import Vocabularies from './Vocabularies'

export default function Settings() {
  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-3xl font-bold">設定</h1>
        <LinkButton to="/edit/images" size="sm">
          圖片庫
        </LinkButton>
      </div>
      <Vocabularies />
    </div>
  )
}
