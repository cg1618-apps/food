// Frontend: the "add one" line under each section of 設定 - the two name
// slots and a button. Either name will do; the server refuses neither-name
// with a 422 and a duplicate with a 409, and that sentence is shown here,
// under the boxes that caused it.
//
//   onAdd     async ({ name_cn, name_en }) => void
//   label     the button's words ("新增標籤")
//   autoFocus for the add-a-child form, which opens where it was asked for
//   onCancel  shows a 取消 button (the add-a-child form can be closed)
import { useState } from 'react'

import { Button, Input } from '../ui/primitives'

export default function AddNameForm({ onAdd, label, autoFocus = false, onCancel }) {
  const [nameCn, setNameCn] = useState('')
  const [nameEn, setNameEn] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await onAdd({ name_cn: nameCn.trim() || null, name_en: nameEn.trim() || null })
      setNameCn('')
      setNameEn('')
    } catch (caught) {
      setError(caught?.message || '新增失敗。')
    } finally {
      setBusy(false)
    }
  }

  return (
    <form
      onSubmit={submit}
      onKeyDown={(event) => {
        if (event.key === 'Escape' && onCancel) onCancel()
      }}
      className="space-y-1"
      aria-label={label}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Input
          aria-label={`${label}：中文名`}
          placeholder="中文名"
          value={nameCn}
          onChange={(e) => setNameCn(e.target.value)}
          className="w-36 flex-1"
          autoFocus={autoFocus}
        />
        <Input
          aria-label={`${label}：英文名`}
          placeholder="English"
          value={nameEn}
          onChange={(e) => setNameEn(e.target.value)}
          className="w-36 flex-1"
        />
        <div className="flex gap-1">
          <Button type="submit" size="sm" disabled={busy || !(nameCn.trim() || nameEn.trim())}>
            ＋ {label}
          </Button>
          {onCancel ? (
            <Button size="sm" kind="ghost" onClick={onCancel}>
              取消
            </Button>
          ) : null}
        </div>
      </div>
      {error ? (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      ) : null}
    </form>
  )
}
