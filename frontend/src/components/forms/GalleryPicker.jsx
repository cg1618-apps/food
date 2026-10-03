// Frontend: an owner's picture gallery, edited inside its form.
//
// Modelled on media's ImagePicker + FocusPicker, and diverging from it on
// purpose (docs/notes/decisions.md): media's picker holds ONE image per role,
// and food's recipes, ingredients and notes each hold an ordered gallery whose
// first picture is the cover. So this is a list: upload (several files at
// once), choose from the library, reorder by dragging a tile's handle
// (components/ui/Sortable.jsx), set each picture's focus, remove.
//
// It is controlled and saves nothing itself. `value` is lib/gallery.js's
// `[{ image_id, url, thumb_url, focus }]`; the form PUTs it with the rest of
// its save (galleryPayload) - after the first save for a new owner, because
// until then there is no id to put it under. Uploading DOES reach the server
// at once - the picture goes into the library - but attaching it waits for
// Save, so a cancelled form leaves an unused picture and changes no owner.
import { keepPreviousData } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'

import { endpoints } from '../../api/endpoints'
import { useApiQuery, useUpload } from '../../hooks/useApi'
import { addToGallery } from '../../lib/gallery'
import { focusStyle } from '../../lib/images'
import { rowsReducer } from '../../lib/rowList'
import Dialog from '../ui/Dialog'
import { Button, Chip } from '../ui/primitives'
import { ErrorNote, Loading } from '../ui/states'
import { DragHandle, SortableItem, SortableList } from '../ui/Sortable'
import FocusPicker from './FocusPicker'

const PAGE_SIZE = 30

export default function GalleryPicker({ value, onChange }) {
  const items = value ?? []
  const [libraryOpen, setLibraryOpen] = useState(false)
  const [focusing, setFocusing] = useState(null)
  const [errors, setErrors] = useState([])
  const [uploading, setUploading] = useState(0)
  const fileInput = useRef(null)
  const upload = useUpload()
  // Uploads finish one after another, each appending to the gallery as it
  // stood after the previous one - not to the render that started the loop.
  const latest = useRef(items)
  useEffect(() => {
    latest.current = value ?? []
  }, [value])

  const move = (from, to) => onChange(rowsReducer(items, { type: 'move', from, to }))
  const remove = (index) => onChange(rowsReducer(items, { type: 'remove', index }))

  async function onFiles(fileList) {
    const files = [...(fileList ?? [])]
    if (!files.length) return
    setErrors([])
    setUploading(files.length)
    const failed = []
    // One at a time, so one bad file fails alone with its own message.
    for (const file of files) {
      try {
        const image = await upload.mutateAsync(file)
        latest.current = addToGallery(latest.current, [image])
        onChange(latest.current)
      } catch (error) {
        failed.push(`${file.name}：${error.message}`)
      }
      setUploading((n) => n - 1)
    }
    setErrors(failed)
    if (fileInput.current) fileInput.current.value = ''
  }

  return (
    <div className="space-y-3">
      {items.length ? (
        <SortableList ids={items.map((item) => item.image_id)} onMove={move} layout="grid">
          <ol className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
            {items.map((item, index) => (
              <SortableItem
                key={item.image_id}
                id={item.image_id}
                as="li"
                aria-label={`圖片 ${index + 1}`}
                className="overflow-hidden rounded-md border border-border bg-surface"
              >
                <div className="relative aspect-[4/3] bg-surface-2">
                  <img
                    loading="lazy"
                    src={item.thumb_url}
                    alt=""
                    draggable={false}
                    className="h-full w-full object-cover"
                    style={focusStyle(item.focus)}
                  />
                  {index === 0 ? (
                    <Chip tone="brand" className="absolute left-1.5 top-1.5">
                      封面
                    </Chip>
                  ) : null}
                </div>
                <div className="flex flex-wrap items-center gap-0.5 p-1">
                  <DragHandle label={`圖片 ${index + 1}`} />
                  <IconButton label={`調整圖片 ${index + 1} 的焦點`} onClick={() => setFocusing(index)}>
                    焦點
                  </IconButton>
                  <IconButton label={`移除圖片 ${index + 1}`} danger onClick={() => remove(index)}>
                    移除
                  </IconButton>
                </div>
              </SortableItem>
            ))}
          </ol>
        </SortableList>
      ) : (
        <p className="text-sm text-text-faint">還沒有圖片。第一張會是封面。</p>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <label className="inline-flex cursor-pointer items-center rounded-md border border-border-strong bg-surface px-2.5 py-1 text-xs font-medium text-text hover:border-text focus-within:ring-2 focus-within:ring-brand">
          {uploading ? `上傳中…（剩 ${uploading}）` : '上傳圖片'}
          <input
            ref={fileInput}
            type="file"
            accept="image/*"
            multiple
            aria-label="上傳圖片"
            className="sr-only"
            disabled={uploading > 0}
            onChange={(event) => onFiles(event.target.files)}
          />
        </label>
        <Button size="sm" onClick={() => setLibraryOpen(true)}>
          從圖庫選
        </Button>
      </div>

      {errors.length ? (
        <ErrorNote>
          {errors.map((line) => (
            <span key={line} className="block">
              {line}
            </span>
          ))}
        </ErrorNote>
      ) : null}

      {libraryOpen ? (
        <LibraryDialog
          held={items}
          onToggle={(image, holding) =>
            onChange(
              holding
                ? items.filter((item) => item.image_id !== image.id)
                : addToGallery(items, [image]),
            )
          }
          onClose={() => setLibraryOpen(false)}
        />
      ) : null}

      {focusing !== null && items[focusing] ? (
        <FocusPicker
          src={items[focusing].url}
          focus={items[focusing].focus}
          onCancel={() => setFocusing(null)}
          onDone={(focus) => {
            onChange(rowsReducer(items, { type: 'update', index: focusing, patch: { focus } }))
            setFocusing(null)
          }}
        />
      ) : null}
    </div>
  )
}

function IconButton({ label, danger = false, onClick, children }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={`rounded-sm px-1.5 py-0.5 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
        danger ? 'text-text-muted hover:text-danger' : 'text-text-muted hover:text-text'
      }`}
    >
      {children}
    </button>
  )
}

// The library, opened from a form. Unused pictures first: when filling a
// gallery the picture wanted is almost always the one just uploaded, not one
// already on some other recipe. The filter is a chip, so it can be turned off
// to see everything. Several can be added before 完成; a picture already in
// this gallery is marked, and clicking it again takes it out.
function LibraryDialog({ held, onToggle, onClose }) {
  const [unused, setUnused] = useState(true)
  const [page, setPage] = useState(0)
  const images = useApiQuery(
    endpoints.images.list(),
    { unused: unused ? 'true' : undefined, limit: PAGE_SIZE, offset: page * PAGE_SIZE },
    { placeholderData: keepPreviousData },
  )
  const heldIds = new Set(held.map((item) => item.image_id))
  const rows = images.data ?? []

  return (
    <Dialog
      title="從圖庫選"
      size="lg"
      onClose={onClose}
      footer={
        <Button kind="primary" onClick={onClose}>
          完成
        </Button>
      }
    >
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <button
            type="button"
            aria-pressed={unused}
            onClick={() => {
              setUnused((on) => !on)
              setPage(0)
            }}
            className="rounded-full focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            <Chip tone={unused ? 'brand' : 'neutral'}>只看未使用</Chip>
          </button>
          <span className="text-xs text-text-faint">已選 {held.length} 張</span>
        </div>

        {images.isPending ? <Loading /> : null}
        {images.error ? <ErrorNote error={images.error} /> : null}
        {!images.isPending && !images.error && rows.length === 0 ? (
          <p className="py-6 text-center text-sm text-text-muted">
            {unused ? '沒有未使用的圖片。關掉「只看未使用」可以看全部。' : '圖庫是空的。'}
          </p>
        ) : null}

        <div className="grid grid-cols-3 gap-2 sm:grid-cols-5">
          {rows.map((image) => {
            const holding = heldIds.has(image.id)
            return (
              <button
                key={image.id}
                type="button"
                aria-pressed={holding}
                aria-label={image.original_filename || `圖片 ${image.id}`}
                onClick={() => onToggle(image, holding)}
                className={`relative aspect-square overflow-hidden rounded-sm border-2 bg-surface-2 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand ${
                  holding ? 'border-brand' : 'border-transparent hover:border-border-strong'
                }`}
              >
                <img
                  loading="lazy"
                  src={image.thumb_url}
                  alt=""
                  className="h-full w-full object-cover"
                  // A library thumbnail: a focus belongs to an attachment,
                  // not to the file.
                  data-focus="none"
                />
                {holding ? (
                  <Chip tone="brand" className="absolute right-1 top-1">
                    已選
                  </Chip>
                ) : null}
              </button>
            )
          })}
        </div>

        {page > 0 || rows.length === PAGE_SIZE ? (
          <div className="flex items-center justify-between">
            <Button size="sm" disabled={page === 0} onClick={() => setPage((p) => Math.max(0, p - 1))}>
              上一頁
            </Button>
            <span className="text-xs text-text-faint">第 {page + 1} 頁</span>
            {/* The list answers a bare array with no total, so a full page is
                the only sign there may be another. */}
            <Button size="sm" disabled={rows.length < PAGE_SIZE} onClick={() => setPage((p) => p + 1)}>
              下一頁
            </Button>
          </div>
        ) : null}
      </div>
    </Dialog>
  )
}
