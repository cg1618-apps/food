// Frontend: add or edit a kitchen note, /edit/notes/new and /edit/notes/:id.
//
// A placeholder until the forms land.
import { useParams } from 'react-router-dom'

import Placeholder from '../../components/layout/Placeholder'

export default function NoteForm() {
  const { id } = useParams()
  return <Placeholder title={id ? '編輯筆記' : '新增筆記'} note="筆記表單還在整理中。" />
}
