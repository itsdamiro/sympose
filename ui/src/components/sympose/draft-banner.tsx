import { EditorNotice, noticeActionClass } from "@/components/sympose/editor-notice"

/**
 * The notice at the top of a new-note draft in the editor (docs/decisions/071): that the note does not exist yet, and
 * the two ways out. Accept makes the file; Decline forgets the proposal. Either way nothing else in the vault changes.
 */
export function DraftBanner({ name, onAccept, onDecline }: { name: string; onAccept: () => void; onDecline: () => void }) {
  return (
    <EditorNotice
      title={name}
      actions={
        <>
          <button type="button" className={noticeActionClass} onClick={onDecline}>
            Decline
          </button>
          <button type="button" className={noticeActionClass} onClick={onAccept}>
            Accept
          </button>
        </>
      }
    >
      A note proposed for you. It is not in your vault until you accept it.
    </EditorNotice>
  )
}
