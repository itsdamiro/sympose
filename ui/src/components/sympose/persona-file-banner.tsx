import * as React from "react"

import { cn } from "@/lib/utils"
import { confirm } from "@/lib/confirm-store"
import { notify } from "@/lib/notify"
import { resetPersonaSoul, type PersonaFileInfo } from "@/lib/persona-files-api"
import { PendingRewriteDialog } from "@/components/sympose/pending-rewrite-dialog"
import { toolbarButtonClass } from "@/components/sympose/panel-collapse-button"

function Bar({ title, children, action }: { title: string; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md bg-chip px-3 py-2 text-xs text-fg-muted">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate font-mono text-foreground">{title}</span>
        <span>{children}</span>
      </div>
      {action}
    </div>
  )
}

const actionClass = cn(toolbarButtonClass, "size-auto h-6 px-2 text-xs text-foreground")

/**
 * The strip at the top of the persona file open in the editor (docs/decisions/061): which file it is, since the
 * editor's toolbar does not say, and what is particular to it. For the soul, whether it is the shipped one (saving
 * makes the user's own copy, the shipped file is never written) or the user's own (with Reset to default, which asks
 * first and keeps the user's text aside); for the profile and the context, a rewrite she proposed, with Review;
 * otherwise what the file is.
 * `onChanged` says the file or the list of files changed under the editor, so it is read again.
 */
export function PersonaFileBanner({
  title,
  handle,
  name,
  info,
  onChanged,
}: {
  /** The file's name for the reader, `Samantha · profile.md`. */
  title: string
  handle: string
  name: string
  info: PersonaFileInfo | undefined
  onChanged: () => void
}) {
  const [reviewing, setReviewing] = React.useState(false)

  if (name === "soul.md") {
    if (!info?.local) {
      return <Bar title={title}>This is the shipped soul. Saving makes your own copy of it; the shipped file is not changed.</Bar>
    }
    const reset = () =>
      confirm({
        message: "Put the shipped soul back?",
        description: "Your own version is kept as soul.local.md.bak, and the shipped soul is used again.",
        confirmLabel: "Reset to default",
        onConfirm: async () => {
          if ((await resetPersonaSoul(handle)) === null) return notify.error("Couldn't put the shipped soul back.")
          notify.success("The shipped soul is back; your own version is kept aside.")
          onChanged()
        },
      })
    return (
      <Bar
        title={title}
        action={
          <button type="button" onClick={reset} className={actionClass}>
            Reset to default
          </button>
        }
      >
        You are using your own version of the soul.
      </Bar>
    )
  }

  if (!info?.pending) return <Bar title={title}>{info?.description ?? ""}</Bar>
  return (
    <>
      <Bar
        title={title}
        action={
          <button type="button" onClick={() => setReviewing(true)} className={actionClass}>
            Review
          </button>
        }
      >
        She proposed changes to this file.
      </Bar>
      <PendingRewriteDialog handle={handle} name={name} open={reviewing} onClose={() => setReviewing(false)} onResolved={onChanged} />
    </>
  )
}
