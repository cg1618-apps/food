# The theme toggle is in a slim top bar on a phone

A divergence from `media`, which puts the toggle in the header strip on a
desktop and as a row in its menu drawer below `lg`. food has no drawer: its
phone navigation is the bottom bar, one column per section, which at 360px has
no room for a column that is a control rather than a destination - and a
choice made once per device does not earn a place under the thumb. So the
desktop's top bar stays on a phone, showing only 食, the search icon and the
toggle, not sticky, so it scrolls away and costs the page no height.

Rejected:

- **A floating button**, which would sit over each page's own top-right
  actions.
- **Putting it on 設定**, which is behind Access and so out of reach of a
  reader who is not the owner.

The storage key is `cg1618:food:theme`, not media's `cg1618:theme`: every app
is its own origin on its own hostname, so a shared name would share nothing,
and food's keys are all `cg1618:food:<thing>`.
