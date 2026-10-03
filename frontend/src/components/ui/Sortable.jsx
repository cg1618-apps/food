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
//
// Several lists whose rows move BETWEEN them - a recipe's groups - share one
// SortableBoard. Inside a board a SortableList names its `container` and
// opens no drag area of its own; the board is the one drag area, and the
// containers themselves can be reordered too, by a handle of their own, when
// they are drawn in a SortableContainers:
//
//   <SortableBoard
//     containers={[{ id: 'ungrouped', items: ids }, { id: groupKey, items: ids }]}
//     onMoveItem={(from, to) => ...}       // { container, index } each
//     onMoveContainer={(from, to) => ...}  // indexes into SortableContainers' ids
//   >
//     <SortableList container="ungrouped" ids={ids}>…rows…</SortableList>
//     <SortableContainers ids={groupKeys}>
//       <SortableItem id={groupKey}>
//         <DragHandle label="分組 醬汁" />
//         <SortableList container={groupKey} ids={ids}>…rows…</SortableList>
//       </SortableItem>
//     </SortableContainers>
//   </SortableBoard>
//
// `containers` is every list in display order; every row id and container
// id must be unique across the whole board. The keyboard path works as in a
// single list, and at a container's edge it crosses: Up from a container's
// first row puts the row at the end of the container above, Down from its
// last at the start of the one below (lib/boardMoves.js). An empty container is
// still a drop target.
import {
  DndContext,
  PointerSensor,
  closestCenter,
  useDroppable,
  useSensor,
  useSensors,
} from '@dnd-kit/core'
import {
  SortableContext,
  rectSortingStrategy,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { createContext, useContext, useEffect, useRef } from 'react'

import { neighbourPlace, placeOf } from '../../lib/boardMoves'
import { cx } from '../../lib/cx'

const ListContext = createContext(null)
const ItemContext = createContext(null)
const BoardContext = createContext(null)

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
export function SortableList({ ids, onMove, disabled = false, layout = 'vertical', container, className, children }) {
  const board = useContext(BoardContext)
  if (board && container != null) {
    return (
      <BoardList container={container} ids={ids} className={className}>
        {children}
      </BoardList>
    )
  }
  return (
    <SingleList ids={ids} onMove={onMove} disabled={disabled} layout={layout}>
      {children}
    </SingleList>
  )
}

function SingleList({ ids, onMove, disabled, layout, children }) {
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

const typeOf = (entry) => entry?.data?.current?.type

// A container dragged only meets containers; a row meets rows, and the drop
// zone of an empty container (a non-empty one's zone is disabled, so its
// rows are what a row lands among).
function boardCollisions(args) {
  const dragging = typeOf(args.active)
  const wanted = dragging === 'container' ? ['container'] : ['item', 'zone']
  return closestCenter({
    ...args,
    droppableContainers: args.droppableContainers.filter((c) => wanted.includes(typeOf(c))),
  })
}

/** The one drag area several SortableLists share. See the header. */
export function SortableBoard({ containers, onMoveItem, onMoveContainer, disabled = false, children }) {
  const sensors = useSensors(useSensor(PointerSensor, { activationConstraint: ACTIVATION }))
  const handles = useRef(new Map())
  const containerIds = useRef([])
  const focusAfterMove = useRef(null)

  // After a keyboard move the row or container is drawn somewhere else -
  // possibly in another list - so focus is put back by id, not by index.
  useEffect(() => {
    const id = focusAfterMove.current
    if (id == null) return
    focusAfterMove.current = null
    handles.current.get(id)?.focus()
  })

  const board = {
    disabled,
    registerHandle(id, el) {
      if (el) handles.current.set(id, el)
      else handles.current.delete(id)
    },
    setContainerIds(ids) {
      containerIds.current = ids
    },
    moveItemByKey(id, delta) {
      const from = placeOf(containers, id)
      const to = from && neighbourPlace(containers, from, delta)
      if (disabled || !to) return
      focusAfterMove.current = id
      onMoveItem(from, to)
    },
    moveContainerByKey(id, delta) {
      const ids = containerIds.current
      const from = ids.indexOf(id)
      const to = from + delta
      if (disabled || !onMoveContainer || from < 0 || to < 0 || to >= ids.length) return
      focusAfterMove.current = id
      onMoveContainer(from, to)
    },
  }

  const onDragEnd = ({ active, over }) => {
    if (!over || active.id === over.id) return
    if (typeOf(active) === 'container') {
      const ids = containerIds.current
      const from = ids.indexOf(active.id)
      const to = ids.indexOf(over.id)
      if (onMoveContainer && from >= 0 && to >= 0) onMoveContainer(from, to)
      return
    }
    const from = placeOf(containers, active.id)
    if (!from) return
    let to
    if (typeOf(over) === 'zone') {
      to = { container: over.data.current.container, index: 0 }
    } else {
      to = placeOf(containers, over.id)
      if (!to) return
      // Into another container: before the row it was dropped on, or after
      // it when dropped on its lower half.
      if (to.container !== from.container) {
        const dragged = active.rect.current.translated
        if (dragged && dragged.top > over.rect.top + over.rect.height / 2) to.index += 1
      }
    }
    onMoveItem(from, to)
  }

  return (
    <BoardContext.Provider value={board}>
      <DndContext
        sensors={sensors}
        collisionDetection={boardCollisions}
        modifiers={[lockToVerticalAxis]}
        accessibility={{ screenReaderInstructions: SCREEN_READER }}
        onDragEnd={onDragEnd}
      >
        {children}
      </DndContext>
    </BoardContext.Provider>
  )
}

// One container's rows inside a board: a SortableContext of its own (so a
// drop inside it reorders it), and a drop zone that is live only while the
// container is empty.
function BoardList({ container, ids, className, children }) {
  const board = useContext(BoardContext)
  const { setNodeRef } = useDroppable({
    id: `zone:${container}`,
    data: { type: 'zone', container },
    disabled: ids.length > 0,
  })
  const list = {
    disabled: board.disabled,
    keyDeltas: KEY_DELTAS.vertical,
    itemData: { type: 'item', container },
    registerHandle: board.registerHandle,
    moveByKey: board.moveItemByKey,
  }
  return (
    <ListContext.Provider value={list}>
      <div ref={setNodeRef} className={className}>
        <SortableContext id={container} items={ids} strategy={verticalListSortingStrategy} disabled={board.disabled}>
          {children}
        </SortableContext>
      </div>
    </ListContext.Provider>
  )
}

/**
 * The containers of a board, reorderable: each child is a SortableItem whose
 * id is a container id, with a DragHandle of its own. Up / Down on that
 * handle moves the whole container one place.
 */
export function SortableContainers({ ids, children }) {
  const board = useContext(BoardContext)
  board.setContainerIds(ids)
  const list = {
    disabled: board.disabled,
    keyDeltas: KEY_DELTAS.vertical,
    itemData: { type: 'container' },
    registerHandle: board.registerHandle,
    moveByKey: board.moveContainerByKey,
  }
  return (
    <ListContext.Provider value={list}>
      <SortableContext id="containers" items={ids} strategy={verticalListSortingStrategy} disabled={board.disabled}>
        {children}
      </SortableContext>
    </ListContext.Provider>
  )
}

/** One row. Renders `as` (default div) and carries the drag transform. */
export function SortableItem({ id, as: Tag = 'div', className, style, children, ...rest }) {
  const list = useContext(ListContext)
  const sortable = useSortable({ id, data: list?.itemData })
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
