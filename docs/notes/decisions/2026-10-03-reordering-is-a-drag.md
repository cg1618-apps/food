# Reordering is a drag, as it is in media

Every reorderable list - the form lists, the gallery, the ordered vocabularies
and the category tree - is reordered by dragging a handle, through
`components/ui/Sortable.jsx`, ported from `media`'s.

- **Drag rather than ▲ / ▼ step buttons.** A button costs one click per place,
  so moving the twentieth step of a recipe to the top is nineteen clicks.
- **dnd-kit's pointer events rather than native HTML5 drag.** A native drag
  does nothing on a touch screen, and this app is used on a phone; it also
  swallows the mouse wheel on Windows, so a row could only be dropped
  somewhere already on screen.
- **The keyboard path stays.** Up / Down on a focused handle moves the row one
  place and focus follows it, so nothing needs a pointer. It is also what the
  tests drive.
- **A move that saves at once freezes its list until it settles**, media's
  rule: 設定's reorders build their PATCHes from the order on screen, so a
  second drag sent before the first lands would be computed from a stale
  order.
- **The category tree is nested lists.** A drag needs each sibling group
  contiguous on screen, and dragging a parent should carry its children; a
  flat indented list can do neither.
