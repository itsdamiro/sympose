import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { ArrowDown01Icon, BookOpen01Icon, CloudIcon } from "@hugeicons/core-free-icons"

import { cn } from "@/lib/utils"
import type { SentRecord } from "@/lib/chat-types"
import {
  cloudWords,
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
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover"

interface ReplyFooterProps extends React.ComponentProps<"div"> {
  sent: SentRecord | null | undefined
  /** The references end of the row (the terminal's `show_grounding`). */
  showReferences?: boolean
  /** The cloud icon (a web display choice; what is sent is `/share`'s, never this). */
  showCloud?: boolean
  /** Opens a note of the user's own vault; a note from the built-in reference library is never offered. */
  onOpenNote?: (path: string) => void
}

const hasCloud = (sent: SentRecord | null | undefined) => (sent?.cloud?.length ?? 0) > 0 || (sent?.withheld?.length ?? 0) > 0

/** A small heading over a group of lines in the opened row. */
function Group({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <p className="font-medium text-fg-muted">{title}</p>
      {children}
    </div>
  )
}

/**
 * What a cloud model was sent from the user's vault and what was held back (ADR 031), behind an icon: it opens on
 * hover or keyboard focus, and on a tap on a touch screen. An amber mark says something was held back, so that case
 * shows without opening it.
 */
function CloudSummary({ sent }: { sent: SentRecord }) {
  const sentWords = cloudWords(sent.cloud)
  const heldWords = cloudWords(sent.withheld)
  const held = heldWords.length > 0
  return (
    <Popover>
      <PopoverTrigger
        openOnHover
        delay={150}
        aria-label="What was sent to the cloud model"
        data-held={held || undefined}
        className="relative ml-auto grid size-6 shrink-0 place-items-center rounded text-fg-muted outline-none transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
      >
        <HugeiconsIcon icon={CloudIcon} aria-hidden className="size-3.5" />
        {held && <span aria-hidden className="absolute top-0.5 right-0.5 size-1.5 rounded-full bg-amber-500" />}
      </PopoverTrigger>
      <PopoverContent side="top" align="end" className="space-y-1">
        {sentWords.length > 0 && <p>Sent to the cloud model: {sentWords.join(", ")}</p>}
        {held && <p>Held back: {heldWords.join(", ")}</p>}
      </PopoverContent>
    </Popover>
  )
}

/**
 * The one quiet row under a persona's reply (docs/decisions/060). Its left end is what the reply used, closed to a
 * single truncating line and opening to the full list as the terminal's `/grounded` gives it; its right end, on a
 * cloud model's replies, is the cloud icon. The standing context (her memory, the recaps, turns left out) is listed
 * only inside an open row, so a plain reply carries nothing.
 */
function ReplyFooter({ className, sent, showReferences = true, showCloud = true, onOpenNote, ...props }: ReplyFooterProps) {
  const [open, setOpen] = React.useState(false)
  const references = showReferences && hasFooterRow(sent)
  const cloud = showCloud && hasCloud(sent)
  if (!references && !cloud) return null

  const notes = groundedNotes(sent)
  const chats = groundedChats(sent)
  const lookups = groundedLookups(sent)
  const context = groundedContext(sent)

  return (
    <div data-slot="reply-footer" className={cn("pt-0.5 text-xs", className)} {...props}>
      <div className="flex min-w-0 items-center gap-2">
        {references && (
          <button
            type="button"
            aria-expanded={open}
            onClick={() => setOpen(!open)}
            className="-mx-1 inline-flex min-w-0 items-center gap-1.5 rounded px-1 py-0.5 text-fg-muted transition-colors hover:bg-accent hover:text-foreground"
          >
            <HugeiconsIcon icon={BookOpen01Icon} aria-hidden className="size-3.5 shrink-0" />
            <span className="truncate">{rowSummary(sent)}</span>
            <HugeiconsIcon
              icon={ArrowDown01Icon}
              aria-hidden
              className={cn("size-3 shrink-0 transition-transform", open && "rotate-180")}
            />
          </button>
        )}
        {cloud && sent && <CloudSummary sent={sent} />}
      </div>
      {references && open && (
        <div className="mt-1.5 max-h-48 space-y-2.5 overflow-y-auto border-l border-border pl-3">
          {(notes.length > 0 || chats > 0) && (
            <Group title="Used">
              <ul className="space-y-1.5">
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
              </ul>
            </Group>
          )}
          {lookups.length > 0 && (
            <Group title="Looked up">
              <ul className="space-y-1">
                {lookups.map((line, i) => (
                  <li key={`${line}-${i}`} className="text-fg-muted">
                    {line}
                  </li>
                ))}
              </ul>
            </Group>
          )}
          {context.length > 0 && (
            <Group title="Also in her context">
              <ul className="space-y-1">
                {context.map((line, i) => (
                  <li key={`${line}-${i}`} className="text-fg-muted">
                    {line}
                  </li>
                ))}
              </ul>
            </Group>
          )}
        </div>
      )}
    </div>
  )
}

export { ReplyFooter }
