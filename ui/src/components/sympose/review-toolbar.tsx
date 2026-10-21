import type { EditorView } from "@codemirror/view"
import type { InPlaceConfig, ToolbarCustomItem } from "@damiro/stylo"
import { HugeiconsIcon } from "@hugeicons/react"
import { Comment01Icon } from "@hugeicons/core-free-icons"

import { selectionTarget, type CommentTarget } from "@/lib/review-extensions"

/**
 * The toolbar's "Comment" button (docs/decisions/069): it opens the box for a new comment on what is selected, and is
 * greyed while nothing is. It is always there, since a note can be commented on whether or not the persona has suggested anything
 * (the whole note's Accept and Decline are in `ReviewNotice`, above the text).
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
    // The rectangle comes from stylo, which knows where the words are in a table cell (the editor can only say where the table is).
    run: (view: EditorView, info?: { rect: DOMRect }) => {
      const target = selectionTarget(view, info?.rect)
      if (target) onCompose(target)
    },
  }
}
