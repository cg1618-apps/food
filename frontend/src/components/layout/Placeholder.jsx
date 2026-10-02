// Frontend: the body of a page whose real version has not landed yet.
//
// Every route is registered from the start so the navigation, the redirects
// and every link work end to end, and so each later page touches only its own
// file. Until then the route renders this: the page's heading and an empty
// note, with the way onward when there is one. A real component, not a
// redirect - a link to a recipe should land on the recipe's route.
import { Empty } from '../ui/states'

export default function Placeholder({ title, note = '這一頁還在整理中。', action }) {
  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold">{title}</h1>
      <Empty action={action}>{note}</Empty>
    </div>
  )
}
