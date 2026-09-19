// Flatten a nested category tree into an indented list for a <select>.
//
// Depth is carried rather than recomputed by the caller, because a select
// option is a flat string and the indentation is the only thing left saying
// where a node sits.
export function flatten(nodes, depth = 0, out = []) {
  for (const node of nodes) {
    out.push({ ...node, depth })
    flatten(node.children ?? [], depth + 1, out)
  }
  return out
}

// Every descendant id of a node, including its own. Used when a delete or a
// re-parent has to know what moves with it.
export function subtreeIds(node, out = []) {
  out.push(node.id)
  for (const child of node.children ?? []) subtreeIds(child, out)
  return out
}
