import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown01Icon, InformationCircleIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"
import type { SentRecord } from "@/lib/chat-types"
import {
  groundedChats,
  groundedChatsLine,
  groundedContext,
  groundedLookups,
  groundedNotes,
  hasFooterRow,
  isReference,
  noteDetail,
  rowSummary,
} from "@/lib/grounded"

interface ReplyFooterProps extends React.ComponentProps<"div"> {
  sent: SentRecord | null | undefined
  /** The references end of the row (the terminal's `show_grounding`). */
  showReferences?: boolean
  /** Opens a note of the user's own vault; a note from the built-in reference library is never offered. */
  onOpenNote?: (path: string) => void
}

/** A small heading over a group of lines. */
function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="font-medium text-foreground">{title}</p>
      {children}
    </div>
  )
}

function Lines({ lines }: { lines: string[] }) {
  return (
    <ul className="space-y-1">
      {lines.map((line, i) => (
        <li key={`${line}-${i}`}>{line}</li>
      ))}
    </ul>
  )
}

/**
 * The one quiet row under a persona's reply (docs/decisions/060): what the reply used, closed to a single
 * truncating line. The notes open below it (the clickable part); everything that is only information (earlier
 * exchanges, what she looked up, her standing context: memory, recaps, turns left out) sits behind a small info icon
 * before the line, so an open row stays short. (A cloud model's reply is marked in its header, `CloudSentIcon`.)
 */
function ReplyFooter({ className, sent, showReferences = true, onOpenNote, ...props }: ReplyFooterProps) {
  const [open, setOpen] = React.useState(false)
  if (!showReferences || !hasFooterRow(sent)) return null

  const notes = groundedNotes(sent)
  const chats = groundedChats(sent)
  const lookups = groundedLookups(sent)
  const context = groundedContext(sent)
  const hasInfo = chats > 0 || lookups.length > 0 || context.length > 0
  const summary = rowSummary(sent)
  const lineClass = "inline-flex max-w-full min-w-0 items-center gap-1.5"

  return (
    <div data-slot="reply-footer" className={cn("pt-0.5 text-xs", className)} {...props}>
      <div className="flex min-w-0 items-center gap-1 text-fg-muted">
        {hasInfo && (
          <Popover>
            <PopoverTrigger
              openOnHover
              delay={150}
              aria-label="More about what she used"
              className="grid size-5 shrink-0 place-items-center rounded outline-none transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
            >
              <HugeiconsIcon icon={InformationCircleIcon} aria-hidden className="size-3.5" />
            </PopoverTrigger>
            <PopoverContent side="bottom" align="start" className="max-h-60 space-y-2.5 overflow-y-auto">
              {chats > 0 && <p>{groundedChatsLine(chats)}</p>}
              {lookups.length > 0 && (
                <Group title="Looked up">
                  <Lines lines={lookups} />
                </Group>
              )}
              {context.length > 0 && (
                <Group title="Also in her context">
                  <Lines lines={context} />
                </Group>
              )}
            </PopoverContent>
          </Popover>
        )}
        {notes.length > 0 ? (
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
            className={cn(lineClass, "rounded px-1 py-0.5 transition-colors hover:bg-accent hover:text-foreground")}
          >
            <span className="truncate">{summary}</span>
            <HugeiconsIcon
              icon={ArrowDown01Icon}
              aria-hidden
              className={cn("size-3 shrink-0 transition-transform", open && "rotate-180")}
            />
          </button>
        ) : (
          <span className={cn(lineClass, "px-1 py-0.5")}>
            <span className="truncate">{summary}</span>
          </span>
        )}
      </div>
      {open && notes.length > 0 && (
        <ul className="mt-1.5 max-h-48 space-y-1.5 overflow-y-auto border-l border-border pl-3">
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
        </ul>
      )}
    </div>
  )
}

export { ReplyFooter }
