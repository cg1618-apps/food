# 設定's tab is in the URL, and the bar is ARIA tabs

A divergence from `media`, whose admin pages hold the active tab in component
state and mark it with `aria-current`.

- **In the URL**, so a tab can be linked to and survives a reload - the
  library filters' reason.
- **A tab click replaces the history entry**, where a filter click pushes. A
  filtered list is a result you may want to come back to; a tab is a view of
  one page, and Back should leave 設定 rather than replay every tab opened on
  the way.
- **`role="tablist"`/`"tab"`/`"tabpanel"` with the arrow keys** is the
  standard pattern for a tab bar, which `aria-current` (a link in a set of
  links) is not.

The look and the wrapping row are media's `AdminTabBar`'s.
