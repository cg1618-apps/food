// Frontend: the foot of every form - the error, then Save, Cancel, Delete.
//
// The error sits directly above the save button, with the server's own
// sentence (a 409's or a 422's `detail`, joined by api/client.js), because
// that is where the eye is when the save did not work. A message at the top of
// a long recipe form is a message nobody scrolled up to.
import { ErrorNote } from '../ui/states'
import { Button } from '../ui/primitives'

export default function FormActions({ saving, error, onCancel, onDelete }) {
  return (
    <div className="space-y-3 border-t border-border pt-4">
      {error ? <ErrorNote error={error} /> : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" kind="primary" disabled={saving}>
          {saving ? '儲存中…' : '儲存'}
        </Button>
        <Button onClick={onCancel} disabled={saving}>
          取消
        </Button>
        {onDelete ? (
          <Button kind="danger" className="ml-auto" onClick={onDelete} disabled={saving}>
            刪除
          </Button>
        ) : null}
      </div>
    </div>
  )
}
