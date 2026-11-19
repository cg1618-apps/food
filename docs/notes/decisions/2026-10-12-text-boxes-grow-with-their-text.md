# Text boxes grow with their text

Every multi-line field is the shared `TextArea`, which fits its height to its
text (`hooks/useAutoGrow.js`), so a long recipe step is read and edited whole
rather than through a two-line slot.

- **The fitting is media's.** `AutoGrowTextarea` collapses the box to `auto`,
  reads `scrollHeight` and adds the border back, in a layout effect on the
  value; food does the same. It is a hook inside `TextArea` rather than a
  second component, so no field can be left on a fixed box by importing the
  wrong one.
- **No height cap**, where media stops at `max-h-80` and scrolls inside. A
  long step read through an inner scrollbar is exactly what this avoids. So
  `overflow-y: hidden`, and `resize: none` because the height always fits and
  the next keystroke would undo a drag.
- **A ResizeObserver re-fits on a change of width**, which media lacks: the
  same text wraps onto more lines when a phone rotates or a window narrows,
  and a box hidden on its first render (a collapsed section) gets its real
  height the moment it is shown. Height changes are ignored, since fitting
  makes them and re-fitting on them would loop.

Rejected: **CSS `field-sizing: content`.** It does the job in one line where it
is supported, but iOS Safari and Firefox do not support it reliably, and a
phone in a shop is where this app is read. Adding it on top as an enhancement
was rejected too: two mechanisms setting one height would disagree about
`rows` as the floor.
