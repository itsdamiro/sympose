import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Cancel01Icon,
  Delete02Icon,
  Edit01Icon,
  NoteAddIcon,
  PaintBoardIcon,
  PinIcon,
  PinOffIcon,
  ViewOffIcon,
} from "@hugeicons/core-free-icons"
import { cn } from "@/lib/utils"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"
import { createVaultNote, deleteVaultFolder } from "@/lib/vault-note-api"
import { fetchFolderColor } from "@/lib/folder-color-api"
import { FolderColorDialog } from "@/components/sympose/folder-color-dialog"
import { confirm } from "@/lib/confirm-store"
import { notify } from "@/lib/notify"
import { RowActionsTrigger } from "@/components/sympose/row-actions"
import { useVaultNoteActions } from "@/lib/use-vault-note-actions"
import type { VaultNode } from "@/components/sympose/vault-tree"

/**
 * The interactive line of a vault tree row plus its two ways in to the same
 * actions:
 *
 *   - the `⋯` button, revealed on row hover / focus
 *   - a right-click (fine pointer) or ~450ms long-press (touch / pen) anywhere
 *     on the row, opening a pointer-anchored context menu
 *
 * Both carry the same rows — **note**: Pin / Unpin (local-only, no vault
 * write, no round-trip), "Remove from recents" (only when the row
 * is rendered inside the vault-wide "Recent" group), Rename (an
 * inline field overlaid on the row) and Delete (asks first via `confirm()`
 * per the Notifications preference, then moved to `.trash/`, recoverable
 * from the Bin); both kinds also get Hide from view (`onHide`, display only —
 * docs/decisions/037); **folder**: New note here
 * (`Folder/Untitled`, auto-numbered) and Delete — an empty folder
 * goes straight away (nothing to lose), a folder with anything in it asks
 * first via `confirm()` same as a note, then moves as one unit to `.trash/`;
 * every note inside is still individually recoverable from the Bin. This
 * component owns the API calls and the rename field; the row's own visual
 * content is passed as `children`.
 */
function VaultRowMenu({
  node,
  persona,
  paddingLeft,
  className,
  children,
  onRenamed,
  onFolderRenamed,
  onBeforeFolderRename,
  onDeleted,
  onFolderColored,
  onCreated,
  pinned = false,
  onTogglePin,
  onRemoveFromRecents,
  onHide,
}: {
  node: VaultNode
  persona: string
  /** Left inset of the row, so the inline rename field lines up with the label. */
  paddingLeft: number
  /** Extra classes for the row line (e.g. the `role="treeitem"` semantics). */
  className?: string
  /** The row's visual content — the disclosure / select `<button>`. */
  children: React.ReactNode
  /** A note row was renamed: its old path and the new vault-relative path. */
  onRenamed: (oldPath: string, newPath: string) => void
  /** A folder row was renamed (docs/decisions/073): its old path and its new vault-relative path. Omit to leave
   *  Rename out of a folder's menu. */
  onFolderRenamed?: (oldPath: string, newPath: string) => void
  /** Before a folder's rename request: save what is unsaved; `false` holds the rename back. */
  onBeforeFolderRename?: () => Promise<boolean>
  /** A note row was moved to trash. */
  onDeleted: (path: string) => void
  /** A subfolder's colour was saved (docs/decisions/090). Omit to leave "Folder colour" out of a subfolder's menu. */
  onFolderColored?: () => void
  /** A new note was created (from a folder row): its vault-relative path. */
  onCreated: (path: string) => void
  /** Is this note currently pinned. */
  pinned?: boolean
  /** Toggle this note's pinned state. Omit to hide the Pin/Unpin row entirely
   *  (e.g. the showcase's bare-tree demo, which wires no persona either). */
  onTogglePin?: (path: string) => void
  /** This row is rendered inside the "Recent" group specifically — drop just
   *  this one path out of the history. Omit outside that group. */
  onRemoveFromRecents?: () => void
  /** Hide this note or folder from view (docs/decisions/037) — display only,
   *  the persona can still read it. Omit to leave the row out of the menu. */
  onHide?: (path: string) => void
}) {
  const isNote = node.type === "note"
  const stem = isNote ? node.name.replace(/\.md$/i, "") : node.name

  const {
    renaming,
    setRenaming,
    setPendingRename,
    busy,
    inputRef,
    onMenuOpenChangeComplete: enterRenameAfterClose,
    handleInputFocus,
    handleInputBlur,
    handleInputKeyDown,
    runDelete,
  } = useVaultNoteActions({
    kind: isNote ? "note" : "folder",
    path: node.path,
    persona,
    stem,
    onRenamed: (newPath) => (isNote ? onRenamed(node.path, newPath) : onFolderRenamed?.(node.path, newPath)),
    onDeleted: () => onDeleted(node.path),
    beforeRename: onBeforeFolderRename,
  })

  const runDeleteFolder = async () => {
    const res = await deleteVaultFolder(node.path, persona)
    if (res.ok) {
      onDeleted(node.path)
      notify.success(res.detail)
    } else {
      notify.error(res.error)
    }
  }

  // "Folder colour" (docs/decisions/090): only a folder below a top-level one; the top-level folders have Folder settings.
  const [colorSetup, setColorSetup] = React.useState<{
    path: string
    start: { accent: string | null; accentDark: string | null }
  } | null>(null)
  const openFolderColor = async () => {
    const found = await fetchFolderColor(node.path, persona)
    if (!found) {
      notify.error("Couldn't read the folder. Check that Sympose is running, then try again.")
      return
    }
    if (!found.editable) {
      notify.info(`${node.name} has no colour to set: it isn't in one of your own folders.`)
      return
    }
    setColorSetup({ path: node.path, start: { accent: found.accent, accentDark: found.accentDark } })
  }

  const newNoteHere = async () => {
    // `node.path` is the folder; try Untitled, then Untitled 2, 3, … past clashes.
    for (let n = 1; n <= 30; n++) {
      const name = n === 1 ? "Untitled" : `Untitled ${n}`
      const res = await createVaultNote(`${node.path}/${name}`, persona)
      if (res.ok) {
        onCreated(`${node.path}/${name}.md`)
        notify.success(`Created ${name}`)
        return
      }
      if (!res.error.toLowerCase().includes("already exists")) {
        notify.error(res.error)
        return
      }
    }
    notify.error("Couldn't find a free “Untitled” name")
  }

  // One row list, rendered into both the `⋯` dropdown and the context menu —
  // `ContextMenu.Item` is `Menu.Item`, so the same parts serve both.
  const items = isNote ? (
    <>
      {onTogglePin && (
        <DropdownMenuItem onClick={() => onTogglePin(node.path)}>
          <HugeiconsIcon icon={pinned ? PinOffIcon : PinIcon} />
          {pinned ? "Unpin note" : "Pin note"}
        </DropdownMenuItem>
      )}
      {onRemoveFromRecents && (
        <DropdownMenuItem onClick={onRemoveFromRecents}>
          <HugeiconsIcon icon={Cancel01Icon} />
          Remove from recents
        </DropdownMenuItem>
      )}
      {onHide && (
        <DropdownMenuItem onClick={() => onHide(node.path)}>
          <HugeiconsIcon icon={ViewOffIcon} />
          Hide from view
        </DropdownMenuItem>
      )}
      <DropdownMenuItem onClick={() => setPendingRename(true)}>
        <HugeiconsIcon icon={Edit01Icon} />
        Rename
      </DropdownMenuItem>
      <DropdownMenuItem
        variant="destructive"
        onClick={() =>
          confirm({
            message: `Move “${stem}” to the bin?`,
            description: "You can restore it from the vault bin later.",
            confirmLabel: "Move to bin",
            onConfirm: runDelete,
          })
        }
      >
        <HugeiconsIcon icon={Delete02Icon} />
        Delete
      </DropdownMenuItem>
    </>
  ) : (
    <>
      <DropdownMenuItem onClick={newNoteHere}>
        <HugeiconsIcon icon={NoteAddIcon} />
        New note here
      </DropdownMenuItem>
      {onHide && (
        <DropdownMenuItem onClick={() => onHide(node.path)}>
          <HugeiconsIcon icon={ViewOffIcon} />
          Hide from view
        </DropdownMenuItem>
      )}
      {onFolderColored && node.path.includes("/") && (
        <DropdownMenuItem onClick={() => void openFolderColor()}>
          <HugeiconsIcon icon={PaintBoardIcon} />
          Folder colour
        </DropdownMenuItem>
      )}
      {onFolderRenamed && (
        <DropdownMenuItem onClick={() => setPendingRename(true)}>
          <HugeiconsIcon icon={Edit01Icon} />
          Rename
        </DropdownMenuItem>
      )}
      <DropdownMenuItem
        variant="destructive"
        onClick={() => {
          // An empty folder holds nothing to lose — skip the confirm step
          // and delete it outright, same low-friction feel as the create
          // side. Anything with content in it confirms first, like a note.
          if ((node.children?.length ?? 0) === 0) {
            void runDeleteFolder()
            return
          }
          confirm({
            message: `Delete “${node.name}” and everything inside it?`,
            description: "Any notes inside will move to the vault bin.",
            confirmLabel: "Delete folder",
            onConfirm: runDeleteFolder,
          })
        }}
      >
        <HugeiconsIcon icon={Delete02Icon} />
        Delete
      </DropdownMenuItem>
    </>
  )

  return (
    <ContextMenu onOpenChangeComplete={enterRenameAfterClose}>
      <ContextMenuTrigger
        className={cn("group/row relative flex items-center", className)}
      >
        {children}

        {renaming !== null && (
          <input
            ref={inputRef}
            value={renaming}
            disabled={busy}
            aria-label={`Rename ${stem}`}
            onChange={(e) => setRenaming(e.target.value)}
            onFocus={handleInputFocus}
            onBlur={handleInputBlur}
            onClick={(e) => e.stopPropagation()}
            onKeyDown={(e) => {
              e.stopPropagation()
              handleInputKeyDown(e)
            }}
            style={{ paddingLeft: `${paddingLeft + 20}px` }}
            className="absolute inset-y-0 right-1 left-0 my-auto h-6 rounded-md border border-border bg-background pr-2 font-mono text-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
          />
        )}

        <DropdownMenu
          modal={false}
          onOpenChangeComplete={enterRenameAfterClose}
        >
          <RowActionsTrigger
            aria-label={`${isNote ? "Note" : "Folder"} actions`}
            onClick={(e) => e.stopPropagation()}
          />
          <DropdownMenuContent align="end" className="duration-thumb ease-snappy">
            {items}
          </DropdownMenuContent>
        </DropdownMenu>
      </ContextMenuTrigger>

      <ContextMenuContent className="duration-thumb ease-snappy">
        {items}
      </ContextMenuContent>

      {/* Not inside the row's trigger, so a right-click in the dialog never opens the row's menu. */}
      {!isNote && (
        <FolderColorDialog
          setup={colorSetup}
          persona={persona}
          onClose={() => setColorSetup(null)}
          onSaved={() => onFolderColored?.()}
        />
      )}
    </ContextMenu>
  )
}

export { VaultRowMenu }
