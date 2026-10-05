import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Delete02Icon, Edit01Icon, FolderEditIcon, ViewOffIcon } from "@hugeicons/core-free-icons"

import { ContextMenu, ContextMenuContent, ContextMenuTrigger } from "@/components/ui/context-menu"
import { DropdownMenuItem } from "@/components/ui/dropdown-menu"
import { useVaultNoteActions } from "@/lib/use-vault-note-actions"

/** The row of a main-menu item, as the menu builds it. */
interface MenuItemLike {
  id: string
  label: string
  type?: string
}

/**
 * A main-menu row's right-click menu: Define folder, Rename folder (an inline field over the row, the same one a tree
 * row has, docs/decisions/073), Hide from view and Delete folder, each only when the shell wires it. `row` is the
 * row's own button, which the menu hangs off.
 */
export function MainMenuRowMenu<T extends MenuItemLike>({
  item,
  row,
  persona,
  onDefineItem,
  onRenameFolder,
  onBeforeRenameFolder,
  onHideItem,
  onDeleteItem,
}: {
  item: T
  row: React.ReactNode
  /** The persona the rename is made as; Rename is offered only with this and `onRenameFolder`. */
  persona?: string
  onDefineItem?: (item: T) => void
  /** A root folder was renamed: its old path and its new one. */
  onRenameFolder?: (oldPath: string, newPath: string) => void
  /** Before the rename request: save what is unsaved; `false` holds the rename back. */
  onBeforeRenameFolder?: () => Promise<boolean>
  onHideItem?: (item: T) => void
  onDeleteItem?: (item: T) => void
}) {
  const isFolder = item.type !== "note"
  const canRename = isFolder && !!persona && !!onRenameFolder
  const { renaming, setRenaming, setPendingRename, busy, inputRef, onMenuOpenChangeComplete, handleInputFocus, handleInputBlur, handleInputKeyDown } =
    useVaultNoteActions({
      kind: "folder",
      path: item.id,
      persona: persona ?? "",
      stem: item.label,
      onRenamed: (newPath) => onRenameFolder?.(item.id, newPath),
      onDeleted: () => {},
      beforeRename: onBeforeRenameFolder,
    })

  return (
    <ContextMenu onOpenChangeComplete={onMenuOpenChangeComplete}>
      <ContextMenuTrigger className="relative block">
        {row}
        {renaming !== null && (
          <input
            ref={inputRef}
            value={renaming}
            disabled={busy}
            aria-label={`Rename ${item.label}`}
            onChange={(e) => setRenaming(e.target.value)}
            onFocus={handleInputFocus}
            onBlur={handleInputBlur}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              e.stopPropagation()
              handleInputKeyDown(e)
            }}
            className="absolute inset-y-0 right-1 left-(--menu-slot) my-auto h-7 rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
          />
        )}
      </ContextMenuTrigger>
      <ContextMenuContent className="duration-thumb ease-snappy">
        {isFolder && onDefineItem && (
          <DropdownMenuItem onClick={() => onDefineItem(item)}>
            <HugeiconsIcon icon={FolderEditIcon} />
            Define folder
          </DropdownMenuItem>
        )}
        {canRename && (
          <DropdownMenuItem onClick={() => setPendingRename(true)}>
            <HugeiconsIcon icon={Edit01Icon} />
            Rename folder
          </DropdownMenuItem>
        )}
        {onHideItem && (
          <DropdownMenuItem onClick={() => onHideItem(item)}>
            <HugeiconsIcon icon={ViewOffIcon} />
            Hide from view
          </DropdownMenuItem>
        )}
        {isFolder && onDeleteItem && (
          <DropdownMenuItem variant="destructive" onClick={() => onDeleteItem(item)}>
            <HugeiconsIcon icon={Delete02Icon} />
            Delete folder
          </DropdownMenuItem>
        )}
      </ContextMenuContent>
    </ContextMenu>
  )
}
