import type { EditorView } from "@codemirror/view"
import type { ToolbarCustomItem } from "@damiro/stylo"
import { HugeiconsIcon } from "@hugeicons/react"
import { CancelCircleIcon, CheckmarkCircle02Icon } from "@hugeicons/core-free-icons"

import { acceptChanges, hasPending, pendingIds, proposalCount } from "@/lib/review-extensions"

/**
 * The editor toolbar's two buttons for the whole note (docs/decisions/042): accept every suggested change that is
 * still in the text, which also saves the note to the vault, or decline every one. Each change also has its own
 * Accept and Decline in the text. The caller adds them to the toolbar only while the note has suggestions.
 */
export function reviewToolbarItems({
  onAcceptNote,
  onDeclineNote,
}: {
  /** Accepting is the editor's own change to the text, so this is told it is done and saves the note. */
  onAcceptNote: () => void
  onDeclineNote: () => void
}): ToolbarCustomItem[] {
  return [
    {
      id: "review-accept",
      title: "Accept all suggested changes and save",
      icon: <HugeiconsIcon icon={CheckmarkCircle02Icon} className="size-4" />,
      run: (view: EditorView) => {
        if (acceptChanges(view, pendingIds(view.state)).length > 0) onAcceptNote()
      },
      disabled: (state) => !hasPending(state),
    },
    {
      id: "review-decline",
      title: "Decline all suggested changes",
      icon: <HugeiconsIcon icon={CancelCircleIcon} className="size-4" />,
      run: () => onDeclineNote(),
      disabled: (state) => proposalCount(state) === 0,
    },
  ]
}
