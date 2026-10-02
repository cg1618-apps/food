// Frontend: set the point of an image that stays in frame when it is cropped.
//
// media's FocusPicker, drawn in food's Dialog shell (which supplies Escape
// and the press-starts-and-ends-on-the-backdrop rule). The WHOLE image is
// shown with a marker; a click or a drag moves it, and the arrow keys nudge
// it by 1% (10% with Shift) while the marker has focus. Beside it, the two
// crops the image is most drawn in - a cover card and a square thumbnail -
// preview the effect before it is kept.
//
// The value is the "X% Y%" string the API stores (lib/images.js); the centre
// is null.
import { useRef, useState } from 'react'

import { focusStyle, formatFocus, parseFocus } from '../../lib/images'
import Dialog from '../ui/Dialog'
import { Button } from '../ui/primitives'

const NUDGE = 1
const NUDGE_SHIFT = 10
const ARROWS = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }

const clamp = (n) => Math.min(100, Math.max(0, Math.round(n)))

export default function FocusPicker({ src, focus, onDone, onCancel }) {
  const [point, setPoint] = useState(() => parseFocus(focus))
  const frame = useRef(null)
  const dragging = useRef(false)
  const current = formatFocus(point)

  function pointFrom(event) {
    const rect = frame.current.getBoundingClientRect()
    if (!rect.width || !rect.height) return null
    return {
      x: clamp(((event.clientX - rect.left) / rect.width) * 100),
      y: clamp(((event.clientY - rect.top) / rect.height) * 100),
    }
  }

  function onPointerDown(event) {
    if (event.button !== undefined && event.button !== 0) return
    const next = pointFrom(event)
    if (!next) return
    event.preventDefault()
    dragging.current = true
    event.currentTarget.setPointerCapture?.(event.pointerId)
    setPoint(next)
  }

  function onPointerMove(event) {
    if (!dragging.current) return
    const next = pointFrom(event)
    if (next) setPoint(next)
  }

  function onMarkerKey(event) {
    const direction = ARROWS[event.key]
    if (!direction) return
    event.preventDefault()
    const step = event.shiftKey ? NUDGE_SHIFT : NUDGE
    setPoint((p) => ({ x: clamp(p.x + direction[0] * step), y: clamp(p.y + direction[1] * step) }))
  }

  return (
    <Dialog
      title="調整焦點"
      size="lg"
      onClose={onCancel}
      footer={
        <>
          <Button kind="ghost" size="sm" className="mr-auto" onClick={() => setPoint(parseFocus(null))}>
            回到中央
          </Button>
          <Button size="sm" onClick={onCancel}>
            取消
          </Button>
          <Button kind="primary" size="sm" onClick={() => onDone(current)}>
            完成
          </Button>
        </>
      }
    >
      <div className="flex flex-col gap-5 sm:flex-row">
        <div className="flex min-w-0 flex-1 flex-col items-center gap-2">
          <div
            ref={frame}
            data-testid="focus-frame"
            className="relative inline-block cursor-crosshair touch-none select-none border border-border bg-surface-2"
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={() => (dragging.current = false)}
            onPointerCancel={() => (dragging.current = false)}
          >
            <img
              loading="lazy"
              src={src}
              alt="整張圖片"
              draggable={false}
              className="block max-h-[55vh] max-w-full"
            />
            <button
              type="button"
              aria-label={`焦點，橫 ${point.x}%，直 ${point.y}%`}
              title="方向鍵移動 1%，Shift + 方向鍵 10%"
              onKeyDown={onMarkerKey}
              className="absolute h-6 w-6 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-on-brand bg-brand/40 ring-2 ring-brand focus-visible:outline-none focus-visible:ring-4"
              style={{ left: `${point.x}%`, top: `${point.y}%` }}
            />
          </div>
          <p className="text-xs text-text-muted">點一下或拖曳，選出裁切時要留在畫面裡的地方。</p>
        </div>

        <div className="flex shrink-0 flex-row gap-4 sm:flex-col">
          <Preview src={src} focus={current} frame="aspect-[4/3]" caption="封面" />
          <Preview src={src} focus={current} frame="aspect-square" caption="縮圖" />
          <p className="text-xs tabular-nums text-text-muted" aria-live="polite">
            {point.x}% {point.y}%
          </p>
        </div>
      </div>
    </Dialog>
  )
}

function Preview({ src, focus, frame, caption }) {
  return (
    <figure className="space-y-1">
      <div className={`${frame} w-28 overflow-hidden rounded-sm border border-border bg-surface-2`}>
        <img loading="lazy" src={src} alt="" className="h-full w-full object-cover" style={focusStyle(focus)} />
      </div>
      <figcaption className="text-xs text-text-faint">{caption}</figcaption>
    </figure>
  )
}
