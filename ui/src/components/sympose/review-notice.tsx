import type { EditorView } from "@codemirror/view"

import { EditorNotice, noticeActionClass } from "@/components/sympose/editor-notice"
import { acceptChanges, pendingIds } from "@/lib/review-extensions"

/**
 * Accepts every suggested change that is still in the text, as one ordinary edit the user can undo, and says whether
 * any was: the caller then saves the note to the vault (docs/decisions/042).
 */
export function acceptAllIn(view: EditorView): boolean {
  return acceptChanges(view, pendingIds(view.state)).length > 0
}

/**
 * The editor's notice for the changes a persona suggested to the open note (docs/decisions/042): how many are waiting
 * in the text, and Accept all and Decline all for the whole note. Each change also has its own Accept and Decline in
 * the text. Nothing is drawn when none is waiting.
 */
export function ReviewNotice({
  personaName,
  count,
  onAccept,
  onDecline,
}: {
  personaName: string
  /** How many suggested changes are in the text now (those that no longer fit are not counted). */
  count: number
  onAccept: () => void
  onDecline: () => void
}) {
  if (count === 0) return null
  return (
    <EditorNotice
      role="status"
      title={`${personaName} suggested ${count} ${count === 1 ? "change" : "changes"}`}
      actions={
        <>
          <button type="button" className={noticeActionClass} onClick={onDecline}>
            Decline all
          </button>
          <button type="button" className={noticeActionClass} onClick={onAccept}>
            Accept all
          </button>
        </>
      }
    />
  )
}
