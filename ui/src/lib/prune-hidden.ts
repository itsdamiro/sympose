import type { VaultNode } from "@/components/sympose"

/**
 * The tree the user sees: everything the server marked `hidden` (by the user,
 * or a folder definition note while those are not shown) left out, children
 * included. The full tree is kept beside it for resolving `[[wikilinks]]`
 * and embeds, which must still find a hidden note to know not to open it
 * (docs/decisions/037).
 */
export function pruneHidden(nodes: VaultNode[]): VaultNode[] {
  return nodes
    .filter((node) => !node.hidden)
    .map((node) =>
      node.children ? { ...node, children: pruneHidden(node.children) } : node
    )
}

/** The node at `path` in the full tree is hidden by the user — not to be
 *  opened from anywhere. A path the tree does not know is not hidden. */
export function isHiddenByUser(
  tree: VaultNode[],
  path: string | undefined
): boolean {
  if (!path) return false
  for (const node of tree) {
    if (node.path === path) return node.hidden === "user"
    if (node.children && path.startsWith(`${node.path}/`)) {
      return isHiddenByUser(node.children, path)
    }
  }
  return false
}
