// Frontend: the three states every list and detail page owes the reader.
//
// Named components, so that forgetting one is visible in the code rather than
// a page that renders nothing and looks broken while it is merely empty.

export function Loading({ children = '載入中…' }) {
  return (
    <p role="status" className="py-10 text-center text-sm text-text-muted">
      {children}
    </p>
  )
}

export function ErrorNote({ error, children }) {
  return (
    <p
      role="alert"
      className="rounded-md border border-danger/50 bg-surface px-3 py-2 text-sm text-danger"
    >
      {children || error?.message || '出了點問題，請重新整理再試一次。'}
    </p>
  )
}

// An empty state is a direction, not a mood: `action` - a link or a button to
// add the first one - is what turns "nothing here" into the next step.
export function Empty({ children, action }) {
  return (
    <div className="space-y-3 py-10 text-center">
      <p className="font-display text-base text-text-muted">{children}</p>
      {action ? <div className="flex justify-center">{action}</div> : null}
    </div>
  )
}
