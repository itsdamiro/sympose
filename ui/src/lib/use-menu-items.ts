import * as React from "react"
import { File01Icon, Note01Icon } from "@hugeicons/core-free-icons"

import type { MainMenuItem, VaultNode } from "@/components/sympose"
import { stripMdExtension } from "@/lib/utils"
import { folderIconFor } from "@/lib/vault-folders"

/** Icon for a top-level vault entry surfaced on the main menu. */
function menuIconFor(node: VaultNode) {
  if (node.type === "note")
    return node.name.endsWith(".md") ? Note01Icon : File01Icon
  return folderIconFor(node.name, node.icon)
}

/**
 * The main menu is the vault's surface: its top-level folders and root notes
 * (README.md), in the tree's own order, with curated icons where the folder name
 * is known. The footer rows (Settings, Persona, Bin) are not part of it.
 * `noteIds` are the root notes, which a menu pick opens in the editor as well.
 */
export function useMenuItems(vaultTree: VaultNode[], hideExtension: boolean) {
  const menuItems: MainMenuItem[] = React.useMemo(
    () =>
      vaultTree.map((node) => ({
        id: node.path,
        label: hideExtension ? stripMdExtension(node.name) : node.name,
        icon: menuIconFor(node),
        type: node.type,
      })),
    [vaultTree, hideExtension]
  )
  const noteIds = React.useMemo(
    () => new Set(vaultTree.filter((n) => n.type === "note").map((n) => n.path)),
    [vaultTree]
  )
  return { menuItems, noteIds }
}
