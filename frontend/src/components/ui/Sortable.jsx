// Frontend: drag-to-reorder - the one reorder control every list in the app
// uses: the rows of every form list, the gallery, and the ordered
// vocabularies and the category tree on 設定.
//
// media's components/ui/Sortable.jsx, ported. Built on dnd-kit's pointer
// events rather than native HTML5 drag, because a native drag swallows the
// mouse wheel on Windows and does nothing on a touch screen; with dnd-kit the
// page keeps scrolling while a row is held, and a finger drags as a mouse
// does. A row is picked up only by its DragHandle, so the inputs inside it
// stay usable. The handle also moves its row one place with the arrow keys -
// the keyboard path, and what the tests drive, since jsdom cannot drag.
//
//   <SortableList ids={ids} onMove={(from, to) => ...}>
//     {rows.map((row, i) => (
//       <SortableItem key={ids[i]} id={ids[i]} className="flex gap-2">
//         <DragHandle label={row.name} />
//         ...
//       </SortableItem>
//     ))}
//   </SortableList>
//
// `ids` must be unique and in render order. `onMove(from, to)` fires once per
// drop or key press, with indexes into `ids`; the caller builds the new order
// (lib/rowList.js's 'move', or lib/vocabulary.js's reorderPatches).
import { DndContext, PointerSensor, closestCenter, useSensor, useSensors } from '@dnd-kit/core'
import {
  SortableContext,
  rectSortingStrategy,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { createContext, useContext, useEffect, useRef } from 'react'

import { cx } from '../../lib/cx'

const ListContext = createContext(null)
const ItemContext = createContext(null)

// A press has to travel a few pixels before it becomes a drag, so a plain
// click or tap on the handle does nothing.
const ACTIVATION = { distance: 4 }

const lockToVerticalAxis = ({ transform }) => ({ ...transform, x: 0 })

const SCREEN_READER = { draggable: '拖曳可以排序，或按方向鍵移一格。' }

// A vertical list moves by Up / Down; a grid reads left to right, so Left and
// Right move a tile too.
const KEY_DELTAS = {
  vertical: { ArrowUp: -1, ArrowDown: 1 },
  grid: { ArrowUp: -1, ArrowDown: 1, ArrowLeft: -1, ArrowRight: 1 },
}

/**
 * The list. `layout="grid"` lets tiles move in both directions; the default
 * locks the drag to the vertical axis. `disabled` freezes every handle, for a
 * list whose last move is still being saved.
 */
export function SortableList({ ids, onMove, disabled = false, layout = 'vertical', children }) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: ACTIVATION }))
  const handles = useRef(new Map())
  const focusAfterMove = useRef(null)

  // A keyboard move re-renders the row somewhere else; put focus back on the
  // handle at the row's new index so a held arrow key keeps moving the same
  // row.
  useEffect(() => {
    const index = focusAfterMove.current
    if (index == null) return
    focusAfterMove.current = null
    handles.current.get(ids[index])?.focus()
  })

  // Not memoised: every caller passes a fresh `ids` and `onMove` each render.
  const list = {
    disabled,
    keyDeltas: KEY_DELTAS[layout] ?? KEY_DELTAS.vertical,
    registerHandle(id, el) {
      if (el) handles.current.set(id, el)
      else handles.current.delete(id)
    },
    moveByKey(id, delta) {
      const from = ids.indexOf(id)
      const to = from + delta
      if (disabled || from < 0 || to < 0 || to >= ids.length) return
      focusAfterMove.current = to
      onMove(from, to)
    },
  }

  const onDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return
    const from = ids.indexOf(active.id)
    const to = ids.indexOf(over.id)
    if (from >= 0 && to >= 0) onMove(from, to)
  }

  return (
    <ListContext.Provider value={list}>
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        modifiers={layout === 'grid' ? undefined : [lockToVerticalAxis]}
        accessibility={{ screenReaderInstructions: SCREEN_READER }}
        onDragEnd={onDragEnd}
      >
        <SortableContext
          items={ids}
          strategy={layout === 'grid' ? rectSortingStrategy : verticalListSortingStrategy}
          disabled={disabled}
        >
          {children}
        </SortableContext>
      </DndContext>
    </ListContext.Provider>
  )
}

/** One row. Renders `as` (default div) and carries the drag transform. */
export function SortableItem({ id, as: Tag = 'div', className, style, children, ...rest }) {
  const sortable = useSortable({ id })
  const { setNodeRef, transform, transition, isDragging } = sortable
  return (
    <ItemContext.Provider value={{ id, ...sortable }}>
      <Tag
        ref={setNodeRef}
        className={cx(className, isDragging ? 'relative z-10 opacity-80' : null)}
        style={{ ...style, transform: CSS.Translate.toString(transform), transition }}
        {...rest}
      >
        {children}
      </Tag>
    </ItemContext.Provider>
  )
}

/**
 * The grip a row is dragged by. `label` names the row for screen readers
 * (「排序 材料 2」). Must sit inside a SortableItem.
 */
export function DragHandle({ label, className }) {
  const list = useContext(ListContext)
  const { id, attributes, listeners, setActivatorNodeRef, isDragging } = useContext(ItemContext)

  const ref = (el) => {
    setActivatorNodeRef(el)
    list.registerHandle(id, el)
  }

  const onKeyDown = (event) => {
    const delta = list.keyDeltas[event.key]
    if (!delta) return
    event.preventDefault()
    list.moveByKey(id, delta)
  }

  return (
    <button
      type="button"
      ref={ref}
      {...attributes}
      {...listeners}
      onKeyDown={onKeyDown}
      disabled={list.disabled}
      aria-label={`排序 ${label}`}
      title="拖曳排序"
      className={cx(
        'shrink-0 touch-none select-none rounded-sm px-1 text-sm leading-5 text-text-faint hover:text-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand disabled:opacity-30',
        isDragging ? 'cursor-grabbing' : 'cursor-grab',
        className,
      )}
    >
      <span aria-hidden="true">⠿</span>
    </button>
  )
}
