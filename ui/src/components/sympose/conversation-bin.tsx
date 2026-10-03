import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Delete02Icon, DeletePutBackIcon, Message01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { ago } from "@/lib/ago"
import { ResultText } from "@/components/sympose/result-text"
import { rowActionClass } from "@/components/sympose/row-actions"
import { confirm } from "@/lib/confirm-store"
import { notify } from "@/lib/notify"
import {
  emptyBinnedSessions,
  fetchBinnedSessions,
  purgeSession,
  restoreSession,
  type BinnedSession,
} from "@/lib/sessions-api"
import { Empty, EmptyDescription, EmptyHeader, EmptyMedia, EmptyTitle } from "@/components/ui/empty"

/**
 * The deleted conversations of the active persona, in the Bin and apart from the notes (ADR 057). Each can be put
 * back, to the persona's list as it was (pinned or not), or deleted for good, which always asks. Owns its own
 * fetch; `refreshKey` lets the shell force a re-pull when a conversation was just deleted from the list, and
 * `onRestored` tells the shell to re-read the list.
 */
function ConversationBin({
  persona,
  refreshKey = 0,
  onRestored,
  className,
}: {
  persona: string
  refreshKey?: number
  onRestored?: () => void
  className?: string
}) {
  // The rows remember whose they are: another persona's are never shown, nor acted on (Restore, Empty), while its own load.
  const [loaded, setLoaded] = React.useState<{ persona: string; rows: BinnedSession[] } | null>(null)
  const rows = loaded && loaded.persona === persona ? loaded.rows : null
  const [failed, setFailed] = React.useState(false)
  const [busy, setBusy] = React.useState<string | null>(null)
  const [localKey, setLocalKey] = React.useState(0)
  const reload = () => setLocalKey((k) => k + 1)

  React.useEffect(() => {
    let live = true
    void fetchBinnedSessions(persona).then((next) => {
      if (!live) return
      setFailed(next === null)
      if (next) setLoaded({ persona, rows: next }) // a failed load keeps this persona's list that was shown, and says so
    })
    return () => {
      live = false
    }
  }, [persona, refreshKey, localKey])

  const restore = async (row: BinnedSession) => {
    setBusy(row.id)
    const out = await restoreSession(persona, row.id)
    setBusy(null)
    if (out.ok) {
      notify.success(`Restored “${row.title || "the conversation"}”`)
      onRestored?.()
      reload()
    } else {
      notify.error(out.error)
    }
  }

  const purge = (row: BinnedSession) =>
    confirm({
      message: `Delete “${row.title || "this conversation"}” forever?`,
      description: "This removes the conversation from disk. It cannot be undone.",
      confirmLabel: "Delete forever",
      permanent: true,
      onConfirm: async () => {
        const out = await purgeSession(persona, row.id)
        if (out.ok) reload()
        else notify.error(out.error)
      },
    })

  const empty = (count: number) =>
    confirm({
      message: "Delete every deleted conversation?",
      description: `Permanently deletes ${count} conversation${count === 1 ? "" : "s"} from disk. This cannot be undone.`,
      confirmLabel: "Empty",
      permanent: true,
      onConfirm: async () => {
        const out = await emptyBinnedSessions(persona)
        if (out.ok) {
          notify.success(`Deleted ${out.value} conversation${out.value === 1 ? "" : "s"} for good`)
          reload()
        } else {
          notify.error(out.error)
        }
      },
    })

  if (rows === null) {
    return failed ? (
      <div className={cn("flex flex-col items-start gap-2 text-sm text-fg-muted", className)}>
        <p>Couldn&apos;t load the deleted conversations. Is the backend running?</p>
        <button type="button" onClick={reload} className="rounded-md px-2 py-1 text-xs hover:bg-accent hover:text-foreground">
          Try again
        </button>
      </div>
    ) : (
      <p className={cn("text-sm text-fg-muted", className)}>Loading…</p>
    )
  }

  if (rows.length === 0) {
    return (
      <Empty className={cn("border-0 p-8", className)}>
        <EmptyHeader>
          <EmptyMedia variant="icon">
            <HugeiconsIcon icon={Delete02Icon} />
          </EmptyMedia>
          <EmptyTitle>No deleted conversations</EmptyTitle>
          <EmptyDescription>A conversation you delete lands here and can be put back.</EmptyDescription>
        </EmptyHeader>
      </Empty>
    )
  }

  return (
    <div className={cn("flex flex-col gap-1", className)}>
      {failed && <p className="pb-1 text-xs text-destructive">Couldn&apos;t refresh — showing what was loaded before.</p>}
      <div className="flex items-center justify-between pb-1">
        <span className="text-xs text-fg-muted">
          {rows.length} conversation{rows.length === 1 ? "" : "s"}
        </span>
        <button type="button" onClick={() => empty(rows.length)} className="text-xs text-fg-muted transition-colors hover:text-destructive">
          Empty
        </button>
      </div>
      {rows.map((row) => (
        <div key={row.id} className="group/row flex items-center gap-2 rounded-md py-1 pr-1">
          <div className="min-w-0 flex-1">
            <ResultText
              icon={Message01Icon}
              title={row.title || "Untitled conversation"}
              detail={`${row.turns} turn${row.turns === 1 ? "" : "s"} · deleted ${ago(row.deleted_at)}`}
            />
          </div>
          <button
            type="button"
            disabled={busy === row.id}
            onClick={() => void restore(row)}
            aria-label={`Restore ${row.title || "the conversation"}`}
            className={cn(rowActionClass, "disabled:opacity-50")}
          >
            <HugeiconsIcon icon={DeletePutBackIcon} className="size-3.5" />
          </button>
          <button
            type="button"
            disabled={busy === row.id}
            onClick={() => purge(row)}
            aria-label={`Delete ${row.title || "the conversation"} permanently`}
            className={cn(rowActionClass, "hover:bg-destructive/10 hover:text-destructive disabled:opacity-50")}
          >
            <HugeiconsIcon icon={Delete02Icon} className="size-3.5" />
          </button>
        </div>
      ))}
    </div>
  )
}

export { ConversationBin }
