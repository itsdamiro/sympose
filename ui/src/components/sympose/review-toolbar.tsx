import type { EditorView } from "@codemirror/view"
import type { InPlaceConfig, ToolbarCustomItem } from "@damiro/stylo"
import { HugeiconsIcon } from "@hugeicons/react"
import { CancelCircleIcon, CheckmarkCircle02Icon, Comment01Icon } from "@hugeicons/core-free-icons"

import { acceptChanges, hasPending, pendingIds, proposalCount, selectionTarget, type CommentTarget } from "@/lib/review-extensions"

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

/**
 * The toolbar's "Comment" button (docs/decisions/069): it opens the box for a new comment on what is selected, and is
 * greyed while nothing is. Unlike the two above it is always there, since a note can be commented on whether or not
 * the persona has suggested anything.
 */
export function commentToolbarItem(onCompose: (target: CommentTarget) => void): ToolbarCustomItem {
  return {
    id: "review-comment",
    title: "Comment on the selected text",
    icon: <HugeiconsIcon icon={Comment01Icon} className="size-4" />,
    run: (view: EditorView) => {
      const target = selectionTarget(view)
      if (target) onCompose(target)
    },
    disabled: (state) => state.selection.main.empty,
  }
}

/** One entry of the editor's right-click menu (stylo does not export the type by name). */
type ContextMenuItem = NonNullable<Exclude<InPlaceConfig["contextMenu"], boolean | undefined>["items"]>[number]

/**
 * The right-click menu's "Comment" (docs/decisions/069), the same as the toolbar's button but where the user's hand
 * already is: it shows only when words are selected, and also in a note being read, since a comment is kept apart
 * from the text.
 */
export function commentMenuItem(onCompose: (target: CommentTarget) => void): ContextMenuItem {
  return {
    id: "review-comment",
    title: "Comment",
    icon: <HugeiconsIcon icon={Comment01Icon} className="size-4" />,
    when: "selection",
    readOnlySafe: true,
    run: (view: EditorView) => {
      const target = selectionTarget(view)
      if (target) onCompose(target)
    },
  }
}
