import * as React from "react"

import { cn } from "@/lib/utils"
import { notify } from "@/lib/notify"
import { fetchPendingRewrite, resolvePendingRewrite, type PendingRewrite } from "@/lib/persona-files-api"
import { Button } from "@/components/ui/button"
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog"

/** One line of a unified diff, told apart by what it does: the file headers and hunk marks are quiet, an addition
 *  and a removal take the app's success and destructive tones. */
function lineClass(line: string): string {
  if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("@@")) return "text-fg-muted"
  if (line.startsWith("+")) return "text-ok"
  if (line.startsWith("-")) return "text-destructive"
  return "text-foreground"
}

interface Props {
  handle: string
  name: string
  onClose: () => void
  /** The proposal was accepted or discarded: the file or the list of files changed. */
  onResolved: () => void
}

/** The dialog's content: mounted only while it is open, so it reads the proposal afresh each time it opens. */
function Body({ handle, name, onClose, onResolved }: Props) {
  const [rewrite, setRewrite] = React.useState<PendingRewrite | null | undefined>(undefined) // undefined: still loading
  const [busy, setBusy] = React.useState(false)

  React.useEffect(() => {
    let live = true
    void fetchPendingRewrite(handle, name).then((found) => live && setRewrite(found))
    return () => {
      live = false
    }
  }, [handle, name])

  const resolve = async (action: "accept" | "discard") => {
    setBusy(true)
    const out = await resolvePendingRewrite(handle, name, action)
    setBusy(false)
    if (!out.ok) return notify.error(out.error)
    notify.success(action === "accept" ? `Applied the proposed changes to ${name}.` : "Discarded the proposed changes.")
    onResolved()
    onClose()
  }

  return (
    <>
      <DialogHeader>
        <DialogTitle>Proposed changes to {name}</DialogTitle>
        <DialogDescription>
          The persona wrote this after your chats. Nothing changes until you accept it, and your current version is saved as a backup.
        </DialogDescription>
      </DialogHeader>
      {rewrite === undefined && <p className="text-fg-muted">Loading…</p>}
      {rewrite === null && <p className="text-fg-muted">Nothing is waiting for this file.</p>}
      {rewrite && (
        <>
          <div className="max-h-80 overflow-auto rounded-md bg-chip p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap">
            {rewrite.diff.split("\n").map((line, i) => (
              <div key={i} className={cn(lineClass(line))}>
                {line || " "}
              </div>
            ))}
          </div>
          <DialogFooter>
            <Button variant="secondary" disabled={busy} onClick={() => void resolve("discard")}>
              Discard
            </Button>
            <Button disabled={busy} onClick={() => void resolve("accept")}>
              Accept
            </Button>
          </DialogFooter>
        </>
      )}
    </>
  )
}

/**
 * The web's `/memory review` (docs/decisions/061, 041): a rewrite of the profile or the context that the engine
 * staged, shown as a diff against the file as it is now, with Accept (applies it, keeping the old file as `.bak`)
 * and Discard (removes the proposal). Nothing changes until the user chooses; a failure is said and the dialog stays.
 */
export function PendingRewriteDialog({ open, ...props }: Props & { open: boolean }) {
  return (
    <Dialog open={open} onOpenChange={(next) => !next && props.onClose()}>
      <DialogContent className="sm:max-w-xl">
        <Body {...props} />
      </DialogContent>
    </Dialog>
  )
}
