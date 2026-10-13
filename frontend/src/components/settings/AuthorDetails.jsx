// Frontend: what an author's row on 設定 opens beyond its two names - its
// links and its 備註.
//
// The links are TBD's link editor (components/forms/RowEditor.jsx): a row
// each of 名稱 (YouTube, IG, 部落格 - optional) and 連結, dragged to reorder,
// ✕ to remove, ＋ to add. The 備註 is one multi-line box, line breaks kept.
// lib/authors.js turns the stored author into the draft and the draft into
// the PATCH; Settings.jsx hands all three to VocabularyEditor as `details`.
import RowEditor from '../forms/RowEditor'
import { Input, TextArea } from '../ui/primitives'

export default function AuthorDetails({ name, draft, setDraft }) {
  return (
    <div className="basis-full space-y-2">
      <div className="space-y-1">
        <p className="text-sm font-medium text-text-muted">連結</p>
        <RowEditor
          rows={draft.links}
          onChange={(links) => setDraft({ ...draft, links })}
          newRow={() => ({ label: '', url: '' })}
          addLabel="新增連結"
          itemLabel="連結"
        >
          {(row, { number, update }) => (
            <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,2fr)]">
              <Input
                aria-label={`連結 ${number} 名稱`}
                value={row.label}
                onChange={(event) => update({ label: event.target.value })}
                placeholder="名稱：YouTube、IG…（可留空）"
              />
              <Input
                aria-label={`連結 ${number} 網址`}
                value={row.url}
                onChange={(event) => update({ url: event.target.value })}
                placeholder="網址"
                inputMode="url"
              />
            </div>
          )}
        </RowEditor>
      </div>
      <TextArea
        aria-label={`${name} 的備註`}
        placeholder="備註"
        rows={3}
        value={draft.notes}
        onChange={(event) => setDraft({ ...draft, notes: event.target.value })}
      />
    </div>
  )
}
