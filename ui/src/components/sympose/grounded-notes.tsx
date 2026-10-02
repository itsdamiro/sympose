import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown01Icon, BookOpen01Icon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { SentRecord } from "@/lib/chat-types"
import { groundedChats, groundedChatsLine, groundedNotes, groundedSummary, isReference, noteDetail } from "@/lib/grounded"

interface GroundedNotesProps extends React.ComponentProps<"div"> {
  sent: SentRecord | null | undefined
  /** Opens a note of the user's own vault; a note from the built-in reference library is never offered. */
  onOpenNote?: (path: string) => void
}

/**
 * What a reply was based on, under the reply: one quiet line ("Based on Atlas", "Based on 3 notes") that opens
 * to the full list, as the terminal chat's `/grounded` does. Shows nothing when no note or earlier exchange was used, so a plain
 * conversational reply carries no line; when one was used, the reader can always see which.
 */
function GroundedNotes({ className, sent, onOpenNote, ...props }: GroundedNotesProps) {
  const [open, setOpen] = React.useState(false)
  const notes = groundedNotes(sent)
  const chats = groundedChats(sent)
  if (notes.length === 0 && chats === 0) return null

  return (
    <div data-slot="grounded-notes" className={cn("pt-0.5 text-xs", className)} {...props}>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="-mx-1 inline-flex max-w-full items-center gap-1.5 rounded px-1 py-0.5 text-fg-muted transition-colors hover:bg-accent hover:text-foreground"
      >
        <HugeiconsIcon icon={BookOpen01Icon} aria-hidden className="size-3.5 shrink-0" />
        <span className="truncate">{groundedSummary(notes, chats)}</span>
        <HugeiconsIcon
          icon={ArrowDown01Icon}
          aria-hidden
          className={cn("size-3 shrink-0 transition-transform", open && "rotate-180")}
        />
      </button>
      {open && (
        <ul className="mt-1.5 space-y-1.5 border-l border-border pl-3">
          {notes.map((note, i) => (
            <li key={`${note.path}-${note.heading}-${i}`} className="min-w-0">
              {onOpenNote && !isReference(note) ? (
                <button
                  type="button"
                  onClick={() => onOpenNote(note.path)}
                  className="max-w-full truncate text-left text-foreground underline-offset-2 hover:underline"
                >
                  {note.path}
                </button>
              ) : (
                <span className="text-foreground">{note.path}</span>
              )}
              {note.heading && <span className="text-fg-muted"> — {note.heading}</span>}
              {noteDetail(note) && <div className="text-fg-muted">{noteDetail(note)}</div>}
            </li>
          ))}
          {chats > 0 && <li className="text-fg-muted">{groundedChatsLine(chats)}</li>}
          {sent?.searched && <li className="text-fg-muted">Searched for “{sent.searched}”</li>}
        </ul>
      )}
    </div>
  )
}

export { GroundedNotes }
