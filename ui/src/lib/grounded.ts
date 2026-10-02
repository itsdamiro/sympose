import type { SentNote, SentRecord } from "@/lib/chat-types"

/** The built-in reference library, as a note's `source`: not a file in the user's vault. */
export const REFERENCE_SOURCE = "sympose"

/** How a note was found, in the same words the terminal chat's `/grounded` uses. */
const VIA_LABELS: Record<NonNullable<SentNote["via"]>, string> = {
  embedding: "by meaning",
  name: "named in full",
  value: "by a property value",
  search: "found by search",
  opened: "opened by a lookup",
}

/** The notes that grounded a reply, in the order recorded; empty when nothing did. */
export function groundedNotes(sent: SentRecord | null | undefined): SentNote[] {
  return sent?.notes ?? []
}

export const isReference = (note: SentNote) => note.source === REFERENCE_SOURCE

/** A note's name as a reader knows it: the file name without its folder or `.md`. */
export function noteTitle(path: string): string {
  const file = path.split("/").pop() ?? path
  return file.replace(/\.md$/i, "")
}

/** How many exchanges of earlier conversations reached the model, word for word (ADR 056). */
export function groundedChats(sent: SentRecord | null | undefined): number {
  return sent?.chats?.length ?? 0
}

export const groundedChatsLine = (count: number) =>
  `${count} ${count === 1 ? "exchange" : "exchanges"} from earlier conversations, word for word`

/** The collapsed line: the note's name when one note grounded the reply, else how many; earlier exchanges follow.
 *  Notes count once each however many passages of them were used. */
export function groundedSummary(notes: SentNote[], chats = 0): string {
  const files = [...new Set(notes.map((n) => n.path))]
  const parts: string[] = []
  if (files.length === 1) parts.push(isReference(notes[0]) ? "the Sympose reference library" : noteTitle(files[0]))
  else if (files.length > 1) parts.push(`${files.length} notes`)
  if (chats > 0) parts.push(`${chats} earlier ${chats === 1 ? "exchange" : "exchanges"}`)
  return `Based on ${parts.join(" and ")}`
}

/** Small print after a note in the expanded list: how it was found, where it is from, how close it was. */
export function noteDetail(note: SentNote): string {
  const bits = [
    note.via ? VIA_LABELS[note.via] : null,
    isReference(note) ? "the Sympose reference library" : null,
    note.similarity !== undefined ? `similarity ${note.similarity.toFixed(2)}` : null,
  ]
  return bits.filter(Boolean).join(" · ")
}
