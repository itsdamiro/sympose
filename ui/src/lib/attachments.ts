import * as React from "react"

/**
 * The passages of the open note the user attached to their next chat message (docs/decisions/076): the user's own act, by the
 * paperclip on a tracked change or a comment, shown as chips in the composer and handed to the chat once, when the message is
 * sent. A module-level slot, like `open-note-source`, because the editor and the composer sit far apart. They belong to one
 * note: another note opening drops them.
 */
export interface Attachment {
  id: string
  path: string
  quote: string
  /** The text around the quote, to find it by (the editor's own, which can be ahead of the file). */
  before: string
  after: string
}

/** The words pointed at, and the text around them: what a message carries. */
export type Passage = Pick<Attachment, "quote" | "before" | "after">

let items: readonly Attachment[] = []
let openPath: string | undefined
const listeners = new Set<() => void>()
const emit = () => listeners.forEach((l) => l())
const subscribe = (cb: () => void) => {
  listeners.add(cb)
  return () => listeners.delete(cb)
}

/** The note now open (or none): what was attached to another note goes. */
export function setAttachmentsNote(path: string | undefined): void {
  if (path === openPath) return
  openPath = path
  if (items.length > 0) {
    items = []
    emit()
  }
}

/** Attaches the words, once: the same words again change nothing. */
export function attach(passage: { quote: string; before: string; after: string }): void {
  if (!openPath || !passage.quote) return
  if (items.some((a) => a.quote === passage.quote && a.before === passage.before && a.after === passage.after)) return
  items = [...items, { id: `${Date.now()}-${items.length}`, path: openPath, ...passage }]
  emit()
}

export function detach(id: string): void {
  items = items.filter((a) => a.id !== id)
  emit()
}

/** What the next message carries, and the end of it: the chips are cleared with the message. */
export function takeAttached(): { quote: string; before: string; after: string }[] {
  const taken = items.filter((a) => a.path === openPath).map(({ quote, before, after }) => ({ quote, before, after }))
  if (items.length > 0) {
    items = []
    emit()
  }
  return taken
}

export function useAttachments(): readonly Attachment[] {
  return React.useSyncExternalStore(subscribe, () => items, () => items)
}
