import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowRight01Icon, Delete02Icon, DeletePutBackIcon, Folder01Icon } from "@hugeicons/core-free-icons"
import { cn } from "@/lib/utils"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyMedia,
  EmptyTitle,
} from "@/components/ui/empty"
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

/** "3d ago" / "2h ago" / "just now" from an epoch-seconds timestamp. */
function ago(epochSeconds: number): string {
  const secs = Math.max(0, Math.round(Date.now() / 1000 - epochSeconds))
  if (secs < 60) return "just now"
  const mins = Math.floor(secs / 60)
  if (mins < 60) return `${mins}m ago`
  const hrs = Math.floor(mins / 60)
  if (hrs < 24) return `${hrs}h ago`
  return `${Math.floor(hrs / 24)}d ago`
}

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
          <EmptyTitle>Bin is empty</EmptyTitle>
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
      <div key={row.trash_path} className="group/row flex items-center gap-2 rounded-md py-1 pr-1">
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate font-mono text-sm">
            {dir ? <span className="text-fg-muted">{dir}</span> : null}
            {name}
          </span>
          <span className="text-xs text-fg-muted">deleted {ago(row.deleted_at)}</span>
        </div>
        <button
          type="button"
          disabled={rowBusy}
          onClick={() => void restore(row)}
          aria-label={`Restore ${name}`}
          className="grid size-7 shrink-0 place-items-center rounded-md text-fg-muted opacity-0 transition-opacity group-hover/row:opacity-100 hover:bg-accent hover:text-foreground focus-visible:opacity-100 disabled:opacity-50"
        >
          <HugeiconsIcon icon={DeletePutBackIcon} className="size-4" />
        </button>
        <button
          type="button"
          disabled={rowBusy}
          onClick={() => purge(row)}
          aria-label={`Delete ${name} permanently`}
          className="grid size-7 shrink-0 place-items-center rounded-md text-fg-muted opacity-0 transition-opacity group-hover/row:opacity-100 hover:bg-destructive/10 hover:text-destructive focus-visible:opacity-100 disabled:opacity-50"
        >
          <HugeiconsIcon icon={Delete02Icon} className="size-4" />
        </button>
      </div>
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
            <div className="group/row flex items-center gap-2 rounded-md py-1 pr-1">
              <button
                type="button"
                onClick={() => toggle(entry.folder.trash_dir)}
                aria-expanded={open.has(entry.folder.trash_dir)}
                aria-label={`${open.has(entry.folder.trash_dir) ? "Hide" : "Show"} the files of ${entry.folder.original_path}`}
                className="flex min-w-0 flex-1 items-center gap-2 text-left"
              >
                <HugeiconsIcon
                  icon={ArrowRight01Icon}
                  className={cn("size-3.5 shrink-0 text-fg-muted transition-transform", open.has(entry.folder.trash_dir) && "rotate-90")}
                />
                <HugeiconsIcon icon={Folder01Icon} className="size-4 shrink-0 text-fg-muted" />
                <span className="flex min-w-0 flex-col">
                  <span className="truncate font-mono text-sm">{entry.folder.original_path}/</span>
                  <span className="text-xs text-fg-muted">
                    {entry.folder.count} file{entry.folder.count === 1 ? "" : "s"}, deleted {ago(entry.folder.deleted_at)}
                  </span>
                </span>
              </button>
              <button
                type="button"
                disabled={busy === entry.folder.trash_dir}
                onClick={() => void restoreFolder(entry.folder)}
                aria-label={`Restore folder ${entry.folder.original_path}`}
                className="shrink-0 rounded-md px-2 py-1 text-xs text-fg-muted transition-colors hover:bg-accent hover:text-foreground disabled:opacity-50"
              >
                Restore folder
              </button>
            </div>
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
