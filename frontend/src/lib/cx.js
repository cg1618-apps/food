// Frontend: join class names, dropping the falsy ones.
//
// Every primitive appends the caller's className to its own base classes with
// this, rather than letting it replace them - the defect the old Input/Select
// had, where passing `className="sm:col-span-2"` silently lost the border and
// the padding.
export function cx(...parts) {
  return parts.filter(Boolean).join(' ')
}
