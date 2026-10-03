import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowRight01Icon, Delete02Icon, DeletePutBackIcon, File01Icon, Folder01Icon } from "@hugeicons/core-free-icons"
import { cn } from "@/lib/utils"
import { ago } from "@/lib/ago"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
import { BinRow } from "@/components/sympose/bin-row"
import { confirm } from "@/lib/confirm-store"
import { notify } from "@/lib/notify"
import {
  emptyTrash,
  fetchTrash,
  purgeTrashNote,
  restoreTrashFolder,
  restoreTrashNote,
  type Trash,
  type TrashedFolder,
  type TrashedNote,
} from "@/lib/vault-trash-api"

function splitPath(rel: string): { dir: string; name: string } {
  const i = rel.lastIndexOf("/")
  const name = (i === -1 ? rel : rel.slice(i + 1)).replace(/\.md$/i, "")
  return { dir: i === -1 ? "" : rel.slice(0, i + 1), name }
}

/**
 * The vault bin — a flat list of every file `delete_note` and `delete_folder` moved to
 * `<vault>/.trash/` (the folder keeps Obsidian's name; the UI says "Bin"): notes and everything
 * else a deleted folder held, attachments included (docs/decisions/045). Each is restorable to its
 * original path or deletable for good; a note shows without its `.md`, any other file with its name. Shown in place
 * of `<VaultTree>` when the main-menu Bin row is the active section. Owns its
 * own fetch; `refreshKey` lets the shell force a re-pull after an outside
 * change (e.g. a fresh delete from the editor).
 */
function TrashList({
  persona,
  refreshKey = 0,
  onRestored,
  className,
}: {
  persona: string
  refreshKey?: number
  /** A file was restored to `originalPath` — the shell refreshes the tree. */
  onRestored?: (originalPath: string) => void
  className?: string
}) {
  const [bin, setBin] = React.useState<Trash | null>(null)
  const [failed, setFailed] = React.useState(false)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [open, setOpen] = React.useState<Set<string>>(() => new Set())
  const [localKey, setLocalKey] = React.useState(0)

  React.useEffect(() => {
    let live = true
    fetchTrash(persona).then((next) => {
      if (!live) return
      setFailed(next === null)
      if (next) setBin(next) // a failed load keeps the bin that was shown, and says so
    })
    return () => {
      live = false
    }
  }, [persona, refreshKey, localKey])

  const reload = () => setLocalKey((k) => k + 1)

  const restore = async (row: TrashedNote) => {
    setBusy(row.trash_path)
    const res = await restoreTrashNote(row.trash_path, persona)
    setBusy(null)
    if (res.ok) {
      notify.success(res.detail)
      onRestored?.(row.original_path)
      reload()
    } else {
      notify.error(res.error)
    }
  }

  // A deleted folder, whole: what is free goes back, and what was in the way is named, never overwritten.
  const restoreFolder = async (folder: TrashedFolder) => {
    setBusy(folder.trash_dir)
    const res = await restoreTrashFolder(folder.trash_dir, persona)
    setBusy(null)
    if (!res.ok) {
      notify.error(res.error)
      return
    }
    if (res.skipped.length > 0) notify.warning(res.detail)
    else notify.success(res.detail)
    if (res.restored.length > 0) onRestored?.(res.restored[0])
    reload()
  }

  const toggle = (dir: string) =>
    setOpen((prev) => {
      const next = new Set(prev)
      if (!next.delete(dir)) next.add(dir)
      return next
    })

  // Permanent — always confirmed through the dialog (`permanent: true`),
  // regardless of the "Delete confirmation" preference.
  const purge = (row: TrashedNote) =>
    confirm({
      message: `Delete “${splitPath(row.original_path).name}” forever?`,
      description: "This removes the file from disk. It cannot be undone.",
      confirmLabel: "Delete forever",
      permanent: true,
      onConfirm: async () => {
        const res = await purgeTrashNote(row.trash_path, persona)
        if (res.ok) {
          notify.success(res.detail)
          reload()
        } else {
          notify.error(res.error)
        }
      },
    })

  const empty = (count: number) =>
    confirm({
      message: "Empty the bin?",
      description: `Permanently deletes everything in the bin (${count} item${
        count === 1 ? "" : "s"
      }) from disk. This cannot be undone.`,
      confirmLabel: "Empty bin",
      permanent: true,
      onConfirm: async () => {
        const res = await emptyTrash(persona)
        if (res.ok) {
          notify.success(res.detail)
          reload()
        } else {
          notify.error(res.error)
        }
      },
    })

  if (bin === null) {
    return failed ? (
      <div className={cn("flex flex-col items-start gap-2 text-sm text-fg-muted", className)}>
        <p>Couldn&apos;t load the bin. Is the backend running?</p>
        <button type="button" onClick={reload} className="rounded-md px-2 py-1 text-xs hover:bg-accent hover:text-foreground">
          Try again
        </button>
      </div>
    ) : (
      <p className={cn("text-sm text-fg-muted", className)}>Loading bin…</p>
    )
  }

  const { items, folders } = bin
  if (items.length === 0) {
    return (
      <Empty className={cn("border-0 p-8", className)}>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <HugeiconsIcon icon={Delete02Icon} />
          </EmptyMedia>
          <EmptyTitle>No deleted notes</EmptyTitle>
          <EmptyDescription>
            Deleted notes and files land here and can be restored to where they were.
          </EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  const renderRow = (row: TrashedNote) => {
    const { dir, name } = splitPath(row.original_path)
    const rowBusy = busy === row.trash_path
    return (
      <BinRow
        key={row.trash_path}
        icon={File01Icon}
        title={name}
        detail={`${dir ? `${dir} · ` : ""}deleted ${ago(row.deleted_at)}`}
        label={name}
        actions={[
          { label: "Restore", icon: DeletePutBackIcon, disabled: rowBusy, onSelect: () => void restore(row) },
          { label: "Delete permanently", icon: Delete02Icon, destructive: true, disabled: rowBusy, onSelect: () => purge(row) },
        ]}
      />
    )
  }

  // Folders deleted as a unit are one row each, their files inside; a file deleted alone is a row of its own.
  // Newest deletion first, the two kinds together.
  const grouped = new Set(folders.map((f) => f.trash_dir))
  const entries = [
    ...folders.map((folder) => ({ kind: "folder" as const, at: folder.deleted_at, folder })),
    ...items.filter((row) => !row.folder || !grouped.has(row.folder)).map((row) => ({ kind: "file" as const, at: row.deleted_at, row })),
  ].sort((a, b) => b.at - a.at)

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {failed && <p className="pb-1 text-xs text-destructive">Couldn&apos;t refresh the bin — showing what was loaded before.</p>}
      <div className="flex items-center justify-between pb-1">
        <span className="text-xs text-fg-muted">
          {items.length} item{items.length === 1 ? "" : "s"}
        </span>
        <button
          type="button"
          onClick={() => empty(items.length)}
          className="text-xs text-fg-muted transition-colors hover:text-destructive"
        >
          Empty bin
        </button>
      </div>

      {entries.map((entry) =>
        entry.kind === "folder" ? (
          <div key={`folder:${entry.folder.trash_dir}`} className="flex flex-col">
            <BinRow
              icon={Folder01Icon}
              title={`${entry.folder.original_path}/`}
              detail={`${entry.folder.count} file${entry.folder.count === 1 ? "" : "s"}, deleted ${ago(entry.folder.deleted_at)}`}
              label={`folder ${entry.folder.original_path}`}
              onClick={() => toggle(entry.folder.trash_dir)}
              expanded={open.has(entry.folder.trash_dir)}
              trailing={
                <HugeiconsIcon
                  icon={ArrowRight01Icon}
                  aria-hidden
                  className={cn("mt-0.5 size-3.5 shrink-0 text-fg-muted transition-transform", open.has(entry.folder.trash_dir) && "rotate-90")}
                />
              }
              actions={[
                { label: "Restore folder", icon: DeletePutBackIcon, disabled: busy === entry.folder.trash_dir, onSelect: () => void restoreFolder(entry.folder) },
              ]}
            />
            {open.has(entry.folder.trash_dir) && (
              <div className="ml-6 flex flex-col border-l border-border pl-2">
                {items.filter((row) => row.folder === entry.folder.trash_dir).map(renderRow)}
              </div>
            )}
          </div>
        ) : (
          renderRow(entry.row)
        )
      )}
    </div>
  )
}

export { TrashList }
