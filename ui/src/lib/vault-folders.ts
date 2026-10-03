import { Folder01Icon } from "@hugeicons/core-free-icons"
import type { IconSvgElement } from "@hugeicons/react"

import { iconByName } from "@/lib/persona-icons"

/**
 * Curated folder-name → icon-name map, the fallback for a top-level folder whose definition note names no icon
 * (docs/decisions/064): the icon is a name in the shared icon set (`persona-icons.ts`). Not a fixed list of folders
 * every vault must have: a folder not in this list is drawn with the generic icon. The vault health offers to write
 * these names into the definitions (`sympose/folder_looks.py` holds the same list), after which this list can go.
 */
export interface VaultFolder {
  /** Folder name — also the route id and vault-relative path. */
  name: string
  /** The name of its icon in the icon set. */
  icon: string
}

export const VAULT_FOLDERS: VaultFolder[] = [
  { name: "Projects", icon: "folder-library" },
  { name: "Code", icon: "source-code" },
  { name: "Daily", icon: "calendar" },
  { name: "Drawings", icon: "paintbrush-2" },
  { name: "General", icon: "folder" },
  { name: "Limbo", icon: "hourglass" },
  { name: "Movies", icon: "film-roll" },
  { name: "People", icon: "users" },
  { name: "Quotes", icon: "quote" },
  { name: "Reading", icon: "book-open" },
  { name: "Recipes", icon: "chef-hat" },
  { name: "Templates", icon: "copy" },
  { name: "Writing", icon: "pencil-edit" },
]

const FOLDER_ICONS = new Map(VAULT_FOLDERS.map((f) => [f.name, f.icon]))

/** The glyph for a folder: the icon its definition note names (`icon`, from the tree), else the curated one for its
 *  name, else the generic folder; a name the icon set does not have counts as none. The main menu and the list's
 *  "Notes in …" caption both draw the folder with this, so they always agree. */
export function folderIconFor(name: string, icon?: string | null): IconSvgElement {
  return iconByName(icon) ?? iconByName(FOLDER_ICONS.get(name)) ?? Folder01Icon
}
