import type { SentLookup, SentNote, SentRecord } from "@/lib/chat-types"

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

const TOOL_LABELS: Record<string, string> = {
  search_notes: "searched",
  open_note: "opened",
  search_chats: "searched earlier conversations for",
  open_chat: "opened earlier conversation",
}
const MEMORY_FILES: Record<string, string> = { profile: "profile.md", context: "context.md", decisions: "decisions.md" }
const ASK_FALLBACK = "You chose ask, but this model can't call tools, so Sympose searched for the message."
const CHATS_ASK_FALLBACK = "You chose ask for earlier conversations, but this model can't call tools, so Sympose searched for the message."

const isRemember = (l: SentLookup) => l.tool === "remember"
const searches = (sent: SentRecord | null | undefined) => (sent?.lookups ?? []).filter((l) => !isRemember(l))
const fellBack = (sent: SentRecord | null | undefined) => sent?.mode === "auto" || sent?.chats_mode === "auto"

function lookupLine(l: SentLookup): string {
  if (isRemember(l)) return l.saved ? "remembered something" : "tried to remember something and could not save it"
  return `${TOOL_LABELS[l.tool] ?? l.tool} "${l.query ?? l.path ?? l.id ?? ""}" (${l.found ?? 0} found)`
}

/** What she looked up or remembered herself, as the terminal's `/grounded` words it; or that `ask` could not be used
 *  and Sympose searched for her; or, when `ask` was on and she looked nothing up, that. */
export function groundedLookups(sent: SentRecord | null | undefined): string[] {
  if (!sent) return []
  const lines: string[] = []
  if (sent.mode === "auto") lines.push(ASK_FALLBACK)
  if (sent.chats_mode === "auto") lines.push(CHATS_ASK_FALLBACK)
  if (lines.length > 0) return lines
  const calls = sent.lookups ?? []
  if (searches(sent).length === 0 && (sent.mode === "ask" || sent.chats_mode === "ask")) lines.push("Looked nothing up for this message.")
  return [...lines, ...calls.map(lookupLine)]
}

/** The standing context a reply carried, listed only inside an open row: recaps, her memory files, the follow-up
 *  query that found the notes, and how many older turns did not fit. */
export function groundedContext(sent: SentRecord | null | undefined): string[] {
  if (!sent) return []
  const lines: string[] = []
  const recaps = sent.recaps?.length ?? 0
  if (recaps > 0) lines.push(`${recaps} earlier-conversation ${recaps === 1 ? "recap" : "recaps"}`)
  const files = (sent.memory ?? []).map((m) => MEMORY_FILES[m]).filter(Boolean)
  if (files.length > 0) lines.push(`her memory (${files.join(", ")})`)
  if (sent.searched) lines.push(`Searched for “${sent.searched}”`)
  const dropped = sent.history_dropped ?? 0
  if (dropped > 0) lines.push(`${dropped} older ${dropped === 1 ? "turn" : "turns"} left out of context`)
  return lines
}

/** Whether a reply gets a row under it: something specific to it was used (a note, an earlier exchange, a lookup or
 *  a remember, the fallback). The standing context alone never makes one, so a plain reply stays clean. */
export function hasFooterRow(sent: SentRecord | null | undefined): boolean {
  return groundedNotes(sent).length > 0 || groundedChats(sent) > 0 || (sent?.lookups?.length ?? 0) > 0 || fellBack(sent)
}

/** The closed row's text, or `null` when there is no row. By what the reply was based on; when it found nothing, by
 *  what she did. */
export function rowSummary(sent: SentRecord | null | undefined): string | null {
  if (!hasFooterRow(sent)) return null
  const notes = groundedNotes(sent)
  const chats = groundedChats(sent)
  if (notes.length > 0 || chats > 0) return groundedSummary(notes, chats)
  const looked = searches(sent).length
  if (looked > 0) return `Looked up ${looked === 1 ? "one thing" : `${looked} things`}`
  const remembered = (sent?.lookups ?? []).filter(isRemember)
  if (remembered.length > 0) return remembered.some((l) => l.saved) ? "Remembered something" : "Tried to remember something"
  return "Sympose searched for the message"
}

const CLOUD_WORDS: Record<string, string> = {
  notes: "notes",
  properties: "note properties",
  recaps: "recaps",
  chats: "earlier conversations",
  vault_map: "vault map",
  connections: "note connections",
  memory: "her memory",
}

/** The categories of the vault a cloud model was sent or refused, in plain words (ADR 031's names are the code's). */
export function cloudWords(names: string[] | undefined): string[] {
  return (names ?? []).map((n) => CLOUD_WORDS[n] ?? n.replace(/_/g, " "))
}
