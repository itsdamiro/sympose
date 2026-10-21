import { cn } from "@/lib/utils"
import { toolbarButtonClass } from "@/components/sympose/panel-collapse-button"

const actionClass = cn(toolbarButtonClass, "size-auto h-6 px-2 text-xs text-foreground")

/**
 * The strip at the top of a new-note draft in the editor (docs/decisions/071): that the note does not exist yet, and
 * the two ways out. It is drawn as the properties card's sibling block (same fill, corners and content gutter, set by the panel in `--gutter`). Accept makes the file; Decline forgets the proposal. Either way nothing else in the vault changes.
 */
export function DraftBanner({ name, onAccept, onDecline }: { name: string; onAccept: () => void; onDecline: () => void }) {
  return (
    <div className="sy-frontmatter-panel flex items-center justify-between gap-4 rounded-lg px-(--gutter,1rem) py-4 text-xs text-fg-muted">
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate font-medium text-foreground">{name}</span>
        <span>A note proposed for you. It is not in your vault until you accept it.</span>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        <button type="button" className={actionClass} onClick={onDecline}>
          Decline
        </button>
        <button type="button" className={actionClass} onClick={onAccept}>
          Accept
        </button>
      </div>
    </div>
  )
}
