import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Delete02Icon,
  Edit01Icon,
  Message01Icon,
  PinIcon,
  PinOffIcon,
  Search01Icon,
} from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { agoIso } from "@/lib/ago"
import { matchesQuery } from "@/lib/search-match"
import { EmptyState } from "@/components/sympose/empty-state"
import { GroupCaption } from "@/components/sympose/group-caption"
import { ResultText } from "@/components/sympose/result-text"
import { RowActionsTrigger } from "@/components/sympose/row-actions"
import type { ListedSession } from "@/lib/use-session-list"
import {
  ContextMenu,
  ContextMenuContent,
  ContextMenuTrigger,
} from "@/components/ui/context-menu"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu"

/** The longest title a conversation may be given (the backend's `MAX_TITLE`). */
const MAX_TITLE = 80

interface ConversationListProps {
  sessions: ListedSession[]
  onOpen: (id: string) => void
  onRename: (id: string, title: string) => Promise<boolean>
  onPin: (id: string, pinned: boolean) => void
  onDelete: (row: ListedSession) => void
  /** What the toolbar's search field holds (docs/decisions/065): only the conversations whose title has every word. */
  query?: string
  className?: string
}

function ConversationRow({
  row,
  onOpen,
  onRename,
  onPin,
  onDelete,
}: {
  row: ListedSession
} & Pick<ConversationListProps, "onOpen" | "onRename" | "onPin" | "onDelete">) {
  const [renaming, setRenaming] = React.useState<string | null>(null)
  const [pendingRename, setPendingRename] = React.useState(false)
  const inputRef = React.useRef<HTMLInputElement>(null)
  const sawFocus = React.useRef(false)
  const title = row.title || "New conversation"
  const pinned = row.pinned_at !== null

  // The field is focused by hand on the next frame, and a blur before it has held focus is ignored: the focus the
  // closing menu hands back would otherwise cancel the rename the moment it starts (as in a note's rename).
  const renameActive = renaming !== null
  React.useEffect(() => {
    if (!renameActive) return
    sawFocus.current = false
    const id = requestAnimationFrame(() => {
      inputRef.current?.focus()
      inputRef.current?.select()
    })
    return () => cancelAnimationFrame(id)
  }, [renameActive])

  // A menu item closes the menu first; only then does the field open.
  const enterRenameAfterClose = (open: boolean) => {
    if (open || !pendingRename) return
    setPendingRename(false)
    setRenaming(row.title)
  }

  const finish = async (commit: boolean) => {
    const next = renaming?.trim() ?? ""
    setRenaming(null)
    if (commit && next && next !== row.title && next.length <= MAX_TITLE) await onRename(row.id, next)
  }

  const items = (
    <>
      <DropdownMenuItem onClick={() => onPin(row.id, !pinned)}>
        <HugeiconsIcon icon={pinned ? PinOffIcon : PinIcon} />
        {pinned ? "Unpin conversation" : "Pin conversation"}
      </DropdownMenuItem>
      <DropdownMenuItem onClick={() => setPendingRename(true)}>
        <HugeiconsIcon icon={Edit01Icon} />
        Rename
      </DropdownMenuItem>
      <DropdownMenuItem
        variant="destructive"
        disabled={row.replying}
        title={row.replying ? "A reply is being written: stop it first" : undefined}
        onClick={() => onDelete(row)}
      >
        <HugeiconsIcon icon={Delete02Icon} />
        Delete
      </DropdownMenuItem>
    </>
  )

  const when = agoIso(row.updated_at)
  return (
    <li>
      <ContextMenu onOpenChangeComplete={enterRenameAfterClose}>
        <ContextMenuTrigger className="group/row relative flex items-center">
          <button
            type="button"
            onClick={() => onOpen(row.id)}
            aria-current={row.current ? "true" : undefined}
            className={cn(
              "group/result flex min-w-0 flex-1 rounded-md py-1 pr-8 text-left",
              "focus-visible:ring-[3px] focus-visible:ring-ring/50 focus-visible:outline-none"
            )}
          >
            <ResultText
              icon={pinned ? PinIcon : Message01Icon}
              iconLabel={pinned ? "Pinned" : undefined}
              title={title}
              emphasized={row.current}
              trailing={
                <>
                  {row.replying && (
                    <span className="shrink-0 text-xs text-fg-muted" role="status">
                      replying…
                    </span>
                  )}
                  {row.unread && !row.replying && (
                    <span className="mt-1 size-2 shrink-0 rounded-full bg-(--persona-accent) dark:bg-(--persona-accent-dark)" role="status" aria-label="New reply" />
                  )}
                </>
              }
              detail={`${row.turns} turn${row.turns === 1 ? "" : "s"}${when ? ` · ${when}` : ""}`}
            />
          </button>

          {renaming !== null && (
            <input
              ref={inputRef}
              value={renaming}
              maxLength={MAX_TITLE}
              aria-label={`Rename ${title}`}
              onChange={(e) => setRenaming(e.target.value)}
              onFocus={() => (sawFocus.current = true)}
              onBlur={() => sawFocus.current && setRenaming(null)}
              onKeyDown={(e) => {
                e.stopPropagation()
                if (e.key === "Enter") void finish(true)
                if (e.key === "Escape") void finish(false)
              }}
              className="absolute inset-y-0 right-1 left-0 my-auto h-7 rounded-md border border-border bg-background px-2 text-sm outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50"
            />
          )}

          <DropdownMenu modal={false} onOpenChangeComplete={enterRenameAfterClose}>
            <RowActionsTrigger aria-label={`Actions for ${title}`} />
            <DropdownMenuContent align="end" className="duration-thumb ease-snappy">
              {items}
            </DropdownMenuContent>
          </DropdownMenu>
        </ContextMenuTrigger>
        <ContextMenuContent className="duration-thumb ease-snappy">{items}</ContextMenuContent>
      </ContextMenu>
    </li>
  )
}

/** The rows, pinned first. When there are both pinned and recent ones they are set apart by the folder list's own
 *  captions ("Pinned", "All conversations"); with only one kind there is nothing to set apart. Its rows are two lines each, ten
 *  pixels apart, so "All conversations" takes 32 px above it (a folder list's groups, of single-line rows, are 12 apart): wide
 *  enough to read as a break and not as one more row. */
function ConversationGroups({
  sessions,
  rowProps,
}: {
  sessions: ListedSession[]
  rowProps: Pick<ConversationListProps, "onOpen" | "onRename" | "onPin" | "onDelete">
}) {
  const pinned = sessions.filter((row) => row.pinned_at !== null)
  const recent = sessions.filter((row) => row.pinned_at === null)
  const list = (rows: ListedSession[]) => (
    <ul className="flex flex-col gap-0.5">
      {rows.map((row) => (
        <ConversationRow key={row.id} row={row} {...rowProps} />
      ))}
    </ul>
  )
  if (pinned.length === 0 || recent.length === 0) return list(sessions)
  return (
    <div className="flex flex-col">
      <GroupCaption icon={PinIcon} label="Pinned" paddingLeft={0} />
      {list(pinned)}
      <GroupCaption icon={Message01Icon} label="All conversations" paddingLeft={0} className="pt-8" />
      {list(recent)}
    </div>
  )
}

/**
 * The persona's conversations, on its profile (ADR 057): the pinned ones first, then the rest with the one last
 * used on top. A click opens one in the chat, also while a reply is being written in another; a row shows
 * `replying…` while a reply is being written into it and a dot when one has landed that nobody has read. Pin,
 * Rename and Delete are on the row's `⋯` and on a right-click (a delete goes to the Bin). The list is only its
 * conversations, with no title line and no New button: a new one starts from the icon under the message box.
 */
function ConversationList({ sessions, onOpen, onRename, onPin, onDelete, query = "", className }: ConversationListProps) {
  const shown = query.trim() ? sessions.filter((row) => matchesQuery(row.title || "New conversation", query)) : sessions
  return (
    <section className={cn("flex flex-col gap-2", className)} aria-label="Conversations">
      {sessions.length === 0 ? (
        <EmptyState compact icon={Message01Icon} title="No conversations yet" />
      ) : shown.length === 0 ? (
        <EmptyState compact icon={Search01Icon} title={`No conversations match "${query.trim()}"`} />
      ) : (
        <ConversationGroups sessions={shown} rowProps={{ onOpen, onRename, onPin, onDelete }} />
      )}
    </section>
  )
}

export { ConversationList }
