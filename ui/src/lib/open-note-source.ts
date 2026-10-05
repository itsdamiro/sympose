/**
 * The note open in the editor, as the editor holds it, for the chat to send with a message (docs/decisions/072): its
 * path and its current text, which can be ahead of the file. The note editor registers itself while a vault note is
 * open and clears it when it goes; a module-level slot because there is one editor and the chat sits far from it
 * (the same shape as `unsaved-guard`).
 */
export interface OpenNote {
  path: string
  text: string
}

let source: (() => OpenNote | null) | null = null

export function setOpenNoteSource(next: (() => OpenNote | null) | null): void {
  source = next
}

export function getOpenNote(): OpenNote | null {
  return source ? source() : null
}
