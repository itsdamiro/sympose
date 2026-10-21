import { Button } from "@/components/ui/button"
import { EditorNotice } from "@/components/sympose/editor-notice"
import type { Proposal } from "@/lib/persona-changes-api"

/**
 * The persona's suggested changes that can no longer be shown in the text because the note changed where they were
 * written (docs/decisions/070): the passage she quoted is gone, or cannot be told from another. They cannot be
 * accepted; the user declines them, or asks her to redo them. Nothing is drawn when there are none.
 */
export function OutdatedChanges({ proposals, onDecline }: { proposals: Proposal[]; onDecline: (ids: string[]) => void }) {
  if (proposals.length === 0) return null
  return (
    <EditorNotice
      role="status"
      title={proposals.length === 1 ? "A suggested change no longer fits" : `${proposals.length} suggested changes no longer fit`}
      below={
        <ul className="mt-2 flex flex-col gap-1">
          {proposals.map((p) => (
            <li key={p.id} className="flex items-center gap-2">
              <span className="min-w-0 flex-1 truncate text-foreground" title={p.say ? `${p.find} — ${p.say}` : p.find}>
                {p.find}
              </span>
              <Button type="button" variant="ghost" size="xs" onClick={() => onDecline([p.id])}>
                Decline
              </Button>
            </li>
          ))}
        </ul>
      }
    >
      The note changed where {proposals.length === 1 ? "it was" : "they were"} written.
    </EditorNotice>
  )
}
