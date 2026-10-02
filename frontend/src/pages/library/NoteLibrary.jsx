// Frontend: the kitchen-notes library, /notes.
//
// A placeholder until the library scaffold lands.
import Placeholder from '../../components/layout/Placeholder'
import { LinkButton } from '../../components/ui/primitives'

export default function NoteLibrary() {
  return (
    <Placeholder
      title="筆記"
      note="筆記庫還在整理中。"
      action={
        <LinkButton kind="primary" to="/edit/notes/new">
          新增筆記
        </LinkButton>
      }
    />
  )
}
