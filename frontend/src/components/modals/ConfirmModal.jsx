// Frontend: a yes/no question in the app's own dialog chrome.
//
// media's ConfirmModal, on food's Dialog shell. For a destructive action that
// has nothing to count; a delete that has cascades to show uses the delete
// dialog instead. `danger` styles the confirming button as destructive.
// Escape and Cancel both cancel; while `busy`, neither button can be pressed
// twice.
import { Button } from '../ui/primitives'
import Dialog from '../ui/Dialog'

export default function ConfirmModal({
  title,
  children,
  confirmLabel = '確定',
  cancelLabel = '取消',
  danger = false,
  busy = false,
  onConfirm,
  onCancel,
}) {
  return (
    <Dialog
      title={title}
      onClose={onCancel}
      footer={
        <>
          <Button onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button kind={danger ? 'danger' : 'primary'} onClick={onConfirm} disabled={busy} autoFocus>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="text-text-muted">{children}</div>
    </Dialog>
  )
}
