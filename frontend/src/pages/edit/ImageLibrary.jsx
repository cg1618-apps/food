// Frontend: the image library, /edit/images - every uploaded picture, which
// owners use it, and delete for the unused ones.
//
// A placeholder until 設定 and 圖片 land.
import Placeholder from '../../components/layout/Placeholder'
import { LinkButton } from '../../components/ui/primitives'

export default function ImageLibrary() {
  return (
    <Placeholder
      title="圖片"
      note="圖片庫還在整理中。"
      action={<LinkButton to="/edit/settings">回到設定</LinkButton>}
    />
  )
}
