import { Attachment01Icon, Cancel01Icon } from "@hugeicons/core-free-icons"
import { HugeiconsIcon } from "@hugeicons/react"

import { detach, useAttachments } from "@/lib/attachments"

/**
 * The chips under the text in the message box (docs/decisions/076): what the user attached to the next message with the
 * paperclip on a tracked change or a comment. Each shows a snippet of the attached words and has its own button to take it
 * off. Nothing is drawn when nothing is attached; there is no chip for what goes with every message.
 */
function AttachedChips() {
  const attached = useAttachments()
  if (attached.length === 0) return null
  return (
    <div data-slot="attached-chips" role="group" aria-label="Attached to your next message" className="flex flex-wrap items-center gap-1.5 px-2.5 pb-2.5">
      {attached.map((a) => (
        <span key={a.id} className="inline-flex h-7 max-w-full items-center gap-1.5 rounded-full border border-border bg-background ps-2.5 pe-1 text-xs">
          <HugeiconsIcon icon={Attachment01Icon} className="size-3.5 shrink-0 text-fg-muted" aria-hidden />
          <span className="max-w-[16rem] truncate" title={a.quote}>
            {a.quote}
          </span>
          <button
            type="button"
            onClick={() => detach(a.id)}
            title="Remove"
            aria-label={`Remove “${a.quote}” from this message`}
            className="grid size-5 shrink-0 place-items-center rounded-full text-fg-muted hover:bg-muted hover:text-foreground"
          >
            <HugeiconsIcon icon={Cancel01Icon} className="size-3" />
          </button>
        </span>
      ))}
    </div>
  )
}

export { AttachedChips }
