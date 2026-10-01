import * as React from "react"

import type { VaultNode } from "@/components/sympose"
import { findNodeByPath } from "@/lib/find-node-by-path"

/**
 * What the content panel lists for the section in view.
 *
 * - `activeNode` is the top-level menu entry; the panel shows its *contents*: a
 *   folder's own subtree (`panelNodes`), or a single root note, not the whole
 *   vault tree.
 * - **Pinned** is scoped to that *root* folder (`activeRootFolder`, `activeNode`
 *   itself, since the panel never changes which top-level entry it shows just
 *   because a nested subfolder inside it is expanded or collapsed), not
 *   vault-wide and not the immediate parent folder either: a note pinned anywhere
 *   under "Daily" shows while browsing Daily regardless of how deep it lives, but
 *   never mixes in with "Code"'s own. A stale path (renamed or deleted since) or
 *   anything that resolves to a folder is silently dropped rather than shown
 *   broken. A pinned row shown outside the folder it lives in needs its full path
 *   spelled out only when that root folder has nested subfolders
 *   (`pinnedShowPath`); a flat root folder's bare filenames are unambiguous.
 * - **Recent**, unlike Pinned, is genuinely vault-wide: each path is resolved
 *   against the full tree wherever it lives.
 */
export function useFolderView({
  vaultTree,
  resolvedActive,
  pinnedPaths,
  recentPaths,
}: {
  vaultTree: VaultNode[]
  resolvedActive: string
  pinnedPaths: string[]
  recentPaths: string[]
}) {
  const activeNode = vaultTree.find((n) => n.path === resolvedActive)
  const panelNodes: VaultNode[] = React.useMemo(
    () =>
      activeNode?.type === "folder"
        ? (activeNode.children ?? [])
        : activeNode
          ? [activeNode]
          : [],
    [activeNode]
  )

  const activeRootFolder = activeNode?.type === "folder" ? activeNode : undefined
  const pinnedNodes = React.useMemo(
    () =>
      activeRootFolder
        ? pinnedPaths
            .filter((path) => path.startsWith(`${activeRootFolder.path}/`))
            .map((path) => findNodeByPath(vaultTree, path))
            .filter((node): node is VaultNode => node?.type === "note")
        : [],
    [activeRootFolder, pinnedPaths, vaultTree]
  )
  const pinnedShowPath = React.useMemo(
    () => activeRootFolder?.children?.some((n) => n.type === "folder") ?? false,
    [activeRootFolder]
  )

  const recentNodes = React.useMemo(
    () =>
      recentPaths
        .map((path) => findNodeByPath(vaultTree, path))
        .filter((node): node is VaultNode => node?.type === "note"),
    [recentPaths, vaultTree]
  )

  return { activeNode, panelNodes, activeRootFolder, pinnedNodes, pinnedShowPath, recentNodes }
}
