import * as React from "react"
import { File01Icon, Folder01Icon, Note01Icon } from "@hugeicons/core-free-icons"

import type { MainMenuItem, VaultNode } from "@/components/sympose"
import { stripMdExtension } from "@/lib/utils"
import { VAULT_FOLDERS } from "@/lib/vault-folders"

/** Curated name → icon map, so known folders keep their glyph when the menu is
 *  driven by the live vault instead of the static `VAULT_FOLDERS` list. */
const FOLDER_ICONS = new Map(VAULT_FOLDERS.map((f) => [f.name, f.icon]))

/** Icon for a top-level vault entry surfaced on the main menu. */
function menuIconFor(node: VaultNode) {
  if (node.type === "note")
    return node.name.endsWith(".md") ? Note01Icon : File01Icon
  return FOLDER_ICONS.get(node.name) ?? Folder01Icon
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
