// Frontend: any path no route claims. Said plainly, with the way back, rather
// than silently redirected - a mistyped link should look like one.
import Placeholder from '../components/layout/Placeholder'
import { LinkButton } from '../components/ui/primitives'

export default function NotFound() {
  return (
    <Placeholder
      title="找不到這一頁"
      note="這個網址沒有對應的頁面。"
      action={
        <LinkButton kind="primary" to="/recipes">
          回到食譜
        </LinkButton>
      }
    />
  )
}
