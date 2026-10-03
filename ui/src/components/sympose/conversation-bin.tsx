import * as React from "react"
import { Alert02Icon, Delete02Icon, DeletePutBackIcon, Message01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { ago } from "@/lib/ago"
import { BinRow } from "@/components/sympose/bin-row"
import { confirm } from "@/lib/confirm-store"
import { notify } from "@/lib/notify"
import {
  emptyBinnedSessions,
  fetchBinnedSessions,
  purgeSession,
  restoreSession,
  type BinnedSession,
} from "@/lib/sessions-api"
import { EmptyAction, EmptyState } from "@/components/sympose/empty-state"

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
      <EmptyState
        className={className}
        icon={Alert02Icon}
        title="Couldn't load the deleted conversations"
        description="Is the backend running?"
        action={<EmptyAction onClick={reload}>Try again</EmptyAction>}
      />
    ) : (
      <p className={cn("text-sm text-fg-muted", className)}>Loading…</p>
    )
  }

  if (rows.length === 0) {
    return (
      <EmptyState
        className={className}
        icon={Delete02Icon}
        title="No deleted conversations"
        description="A conversation you delete lands here and can be put back."
      />
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
        <BinRow
          key={row.id}
          icon={Message01Icon}
          title={row.title || "Untitled conversation"}
          detail={`${row.turns} turn${row.turns === 1 ? "" : "s"} · deleted ${ago(row.deleted_at)}`}
          label={row.title || "the conversation"}
          actions={[
            { label: "Restore", icon: DeletePutBackIcon, disabled: busy === row.id, onSelect: () => void restore(row) },
            { label: "Delete permanently", icon: Delete02Icon, destructive: true, disabled: busy === row.id, onSelect: () => purge(row) },
          ]}
        />
      ))}
    </div>
  )
}

export { ConversationBin }
