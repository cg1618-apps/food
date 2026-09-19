// The shared primitives. Hand-rolled rather than a component library, and
// every colour here is a semantic token - see index.css and theme-tokens.test.js.

export function Button({ variant = 'default', className = '', ...props }) {
  const styles = {
    default: 'bg-surface border-border hover:bg-brand-soft',
    primary: 'bg-brand border-brand text-canvas hover:opacity-90',
    danger: 'bg-surface border-danger text-danger hover:bg-warn-soft',
  }[variant]
  return (
    <button
      className={`rounded border px-3 py-1.5 text-sm transition disabled:opacity-50 ${styles} ${className}`}
      {...props}
    />
  )
}

export function Field({ label, hint, children }) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint ? <span className="block text-xs text-text-muted">{hint}</span> : null}
    </label>
  )
}

export function Input(props) {
  return (
    <input
      className="w-full rounded border border-border bg-surface px-2 py-1.5 text-sm"
      {...props}
    />
  )
}

export function TextArea(props) {
  return (
    <textarea
      rows={4}
      className="w-full rounded border border-border bg-surface px-2 py-1.5 text-sm"
      {...props}
    />
  )
}

export function Select({ children, ...props }) {
  return (
    <select
      className="w-full rounded border border-border bg-surface px-2 py-1.5 text-sm"
      {...props}
    >
      {children}
    </select>
  )
}

export function Card({ className = '', ...props }) {
  return (
    <div
      className={`rounded-lg border border-border bg-surface p-4 ${className}`}
      {...props}
    />
  )
}

export function Pill({ children, tone = 'default' }) {
  const styles = {
    default: 'bg-brand-soft text-text',
    warn: 'bg-warn-soft text-text',
  }[tone]
  return <span className={`rounded-full px-2 py-0.5 text-xs ${styles}`}>{children}</span>
}

// The three states every list and detail page owes the reader. Named so that
// forgetting one is visible, rather than a page that renders nothing and looks
// broken while it is merely empty.
export function Loading() {
  return <p className="py-8 text-center text-sm text-text-muted">Loading…</p>
}

export function ErrorNote({ error }) {
  return (
    <p className="rounded border border-danger bg-warn-soft px-3 py-2 text-sm text-danger">
      {error?.message || 'Something went wrong.'}
    </p>
  )
}

export function Empty({ children }) {
  return <p className="py-8 text-center text-sm text-text-muted">{children}</p>
}
