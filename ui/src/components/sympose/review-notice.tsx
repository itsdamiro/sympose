import * as React from "react"
import type { EditorView } from "@codemirror/view"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown01Icon, ArrowUp01Icon } from "@hugeicons/core-free-icons"

import { EditorNotice, noticeActionClass } from "@/components/sympose/editor-notice"
import { toolbarButtonClass } from "@/components/sympose/panel-collapse-button"
import { getCookieBool, setCookieBool } from "@/lib/cookies"
import { acceptChanges, pendingIds } from "@/lib/review-extensions"

/**
 * Accepts every suggested change that is still in the text, as one ordinary edit the user can undo, and says whether
 * any was: the caller then saves the note to the vault (docs/decisions/042).
 */
export function acceptAllIn(view: EditorView): boolean {
  return acceptChanges(view, pendingIds(view.state)).length > 0
}

const FOLDED_COOKIE = "sympose:review_notice_folded"

/**
 * The editor's notice for the changes a persona suggested to the open note (docs/decisions/042): how many are waiting
 * in the text, and Accept all and Decline all for the whole note. Each change also has its own Accept and Decline in
 * the text. Nothing is drawn when none is waiting. The chevron folds it to a short line with the buttons tucked away,
 * for a note that is meant to be read first; the choice is the viewer's own, kept in a cookie like the other layout
 * preferences (docs/decisions/092).
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
  const [folded, setFolded] = React.useState(() => getCookieBool(FOLDED_COOKIE, false))
  if (count === 0) return null
  const toggle = () => {
    setFolded(!folded)
    setCookieBool(FOLDED_COOKIE, !folded)
  }
  const label = folded ? "Show the buttons" : "Fold"
  return (
    <EditorNotice
      role="status"
      compact={folded}
      title={`${personaName} suggested ${count} ${count === 1 ? "change" : "changes"}`}
      actions={
        <>
          {folded ? null : (
            <>
              <button type="button" className={noticeActionClass} onClick={onDecline}>
                Decline all
              </button>
              <button type="button" className={noticeActionClass} onClick={onAccept}>
                Accept all
              </button>
            </>
          )}
          <button type="button" aria-label={label} title={label} aria-expanded={!folded} className={toolbarButtonClass} onClick={toggle}>
            <HugeiconsIcon icon={folded ? ArrowDown01Icon : ArrowUp01Icon} className="size-4" />
          </button>
        </>
      }
    />
  )
}
