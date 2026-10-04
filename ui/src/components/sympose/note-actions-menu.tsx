import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Delete02Icon,
  Edit01Icon,
  MoreHorizontalIcon,
  PinIcon,
  PinOffIcon,
} from "@hugeicons/core-free-icons"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import type { EditorView } from "@codemirror/view"
import type { ToolbarCustomItem } from "@damiro/stylo"
import { useReviewMenu } from "@/components/sympose/review-menu"
import { confirm } from "@/lib/confirm-store"
import { useVaultNoteActions } from "@/lib/use-vault-note-actions"

/**
 * The `⋯` menu on the editor toolbar — Pin/Unpin (local-only prep, same as
 * the vault-tree row menu), Rename / Delete for the open note.
 * Rename swaps the button for an inline field (Enter commits, Esc /
 * blur cancels); Delete asks first via `confirm()` (dialog / inline / none, per
 * the Notifications preference). Owns
 * the API calls itself; the parent is only told the note moved so it can
 * repoint `selectedNote` and refresh the tree.
 */
function NoteActionsMenu({
  path,
  persona,
  onRenamed,
  onDeleted,
  pinned = false,
  onTogglePin,
  reviewItems,
  getView,
}: {
  /** Vault-relative path of the open note. */
  path: string
  persona: string
  /** Called with the note's new vault-relative path after a rename. */
  onRenamed: (newPath: string) => void
  /** Called after the note is moved to trash. */
  onDeleted: () => void
  /** Is the open note currently pinned. */
  pinned?: boolean
  /** Toggle the open note's pinned state. Omit to hide the row. */
  onTogglePin?: (path: string) => void
  /** The editor's review buttons (comment, accept all, decline all), listed first in the menu; omit in read mode. */
  reviewItems?: ToolbarCustomItem[]
  getView?: () => EditorView | null | undefined
}) {
  const review = useReviewMenu(reviewItems, () => getView?.())
  const stem = React.useMemo(() => {
    const base = path.split("/").pop() ?? path
    return base.replace(/\.md$/i, "")
  }, [path])

  const {
    renaming,
    setRenaming,
    setPendingRename,
    busy,
    inputRef,
    onMenuOpenChangeComplete,
    runDelete,
    handleInputFocus,
    handleInputBlur,
    handleInputKeyDown,
  } = useVaultNoteActions({ path, persona, stem, onRenamed, onDeleted })

  if (renaming !== null) {
    return (
      <input
        ref={inputRef}
        value={renaming}
        disabled={busy}
        aria-label="New note name"
        onChange={(e) => setRenaming(e.target.value)}
        onFocus={handleInputFocus}
        onBlur={handleInputBlur}
        onKeyDown={handleInputKeyDown}
        className="h-7 w-44 rounded-md border border-border bg-background px-2 text-xs outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 disabled:opacity-50"
      />
    )
  }

  return (
    <>
      <DropdownMenu modal={false} onOpenChange={review.onOpenChange} onOpenChangeComplete={onMenuOpenChangeComplete}>
        <DropdownMenuTrigger
          aria-label="Note actions"
          className="grid size-7 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-accent hover:text-foreground data-popup-open:bg-accent data-popup-open:text-foreground"
        >
          <HugeiconsIcon icon={MoreHorizontalIcon} className="size-4" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="duration-thumb ease-snappy">
          {review.entries}
          {onTogglePin && (
            <DropdownMenuItem onClick={() => onTogglePin(path)}>
              <HugeiconsIcon icon={pinned ? PinOffIcon : PinIcon} />
              {pinned ? "Unpin note" : "Pin note"}
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
        </DropdownMenuContent>
      </DropdownMenu>
    </>
  )
}

export { NoteActionsMenu }
