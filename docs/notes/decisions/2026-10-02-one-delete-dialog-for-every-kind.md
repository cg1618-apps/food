# One delete dialog for every kind

One `DeleteDialog`, configured per kind in `lib/deleteTargets.js`, where
`media` has a dialog per page. Every delete here has the same contract -
cascade counts echoed back, `field`/`actual` on a stale 409, `used_in` on a
refusal - so the differences are data, not code.
