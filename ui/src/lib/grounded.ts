import type { SentLookup, SentNote, SentRecord } from "@/lib/chat-types"

/** The built-in reference library, as a note's `source`: not a file in the user's vault. */
export const REFERENCE_SOURCE = "sympose"

/** How a note was found, in the same words the terminal chat's `/grounded` uses. */
const VIA_LABELS: Record<NonNullable<SentNote["via"]>, string> = {
  embedding: "found by topic",
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
  `${count} ${count === 1 ? "message" : "messages"} from earlier chats, quoted exactly`

/** The collapsed line: the note's name when one note grounded the reply, else how many; earlier exchanges follow.
 *  Notes count once each however many passages of them were used. */
export function groundedSummary(notes: SentNote[], chats = 0): string {
  const files = [...new Set(notes.map((n) => n.path))]
  const parts: string[] = []
  if (files.length === 1) parts.push(isReference(notes[0]) ? "Sympose's built-in help" : noteTitle(files[0]))
  else if (files.length > 1) parts.push(`${files.length} notes`)
  if (chats > 0) parts.push(`${chats} earlier ${chats === 1 ? "message" : "messages"}`)
  return `Based on ${parts.join(" and ")}`
}

/** Small print after a note in the expanded list: how it was found, where it is from, how close it was. */
export function noteDetail(note: SentNote): string {
  const bits = [
    note.via ? VIA_LABELS[note.via] : null,
    isReference(note) ? "Sympose's built-in help" : null,
    note.similarity !== undefined ? (note.similarity >= CLOSE_MATCH ? "close match" : "partial match") : null,
  ]
  return bits.filter(Boolean).join(" · ")
}

export interface NoteEntry {
  note: SentNote
  headings: string[]
  details: string[]
}

/** One entry per note: the passages, and the ways it was found (a lookup, a property, by meaning), of one path
 *  merge into a single item instead of one line each. */
export function noteEntries(notes: SentNote[]): NoteEntry[] {
  const byPath = new Map<string, NoteEntry>()
  for (const note of notes) {
    const entry = byPath.get(note.path) ?? { note, headings: [], details: [] }
    byPath.set(note.path, entry)
    if (note.heading && !entry.headings.includes(note.heading)) entry.headings.push(note.heading)
    for (const bit of noteDetail(note).split(" · ").filter(Boolean)) {
      if (!entry.details.includes(bit) && !(bit.endsWith(" match") && entry.details.some((d) => d.endsWith(" match")))) {
        entry.details.push(bit)
      }
    }
  }
  return [...byPath.values()]
}

/** A similarity at or above this reads as a close match, below it as a partial one. */
const CLOSE_MATCH = 0.75

const TOOL_LABELS: Record<string, string> = {
  search_notes: "searched",
  open_note: "opened",
  search_chats: "searched earlier conversations for",
  open_chat: "opened earlier conversation",
}
const MEMORY_FILES: Record<string, string> = { profile: "profile.md", context: "context.md", decisions: "decisions.md" }
const ASK_FALLBACK = "This model can't look things up on its own, so Sympose searched your notes for you."
const CHATS_ASK_FALLBACK = "This model can't look things up on its own, so Sympose searched your earlier chats for you."

const isRemember = (l: SentLookup) => l.tool === "remember"
// What she did to a note (docs/decisions/072), in the footer's words: not lookups.
const ACTS: Record<string, string> = {
  propose_edit: "proposed a change",
  propose_note: "proposed a new note",
  comment_on: "left a comment",
}
const isAct = (l: SentLookup) => l.tool in ACTS
// Opening a note for the user shows in the editor itself, and a persona she proposes is the card under the reply (ADR 078),
// so neither adds anything to the reply's footer.
const SHOWN_ELSEWHERE = ["show_note", "propose_persona"]
const calls = (sent: SentRecord | null | undefined) => (sent?.lookups ?? []).filter((l) => !SHOWN_ELSEWHERE.includes(l.tool))
const searches = (sent: SentRecord | null | undefined) => calls(sent).filter((l) => !isRemember(l) && !isAct(l) && l.tool !== "use_skill")
const fellBack = (sent: SentRecord | null | undefined) => sent?.mode === "auto" || sent?.chats_mode === "auto"

function lookupLine(l: SentLookup): string {
  if (isRemember(l)) return l.saved ? "remembered something" : "tried to remember something and could not save it"
  if (isAct(l)) return l.saved ? ACTS[l.tool] : `tried to ${l.tool === "comment_on" ? "comment" : "propose a " + (l.tool === "propose_note" ? "new note" : "change")} and could not place it`
  if (l.tool === "use_skill") return l.found ? `followed the skill "${l.query}"` : `asked for a skill that does not exist ("${l.query ?? ""}")`
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
  const made = calls(sent)
  if (searches(sent).length === 0 && (sent.mode === "ask" || sent.chats_mode === "ask")) lines.push("Looked nothing up for this message.")
  return [...lines, ...made.map(lookupLine)]
}

/** The standing context a reply carried, listed only inside an open row: recaps, her memory files, the follow-up
 *  query that found the notes, and how many older turns did not fit. */
export function groundedContext(sent: SentRecord | null | undefined): string[] {
  if (!sent) return []
  const lines: string[] = []
  const recaps = sent.recaps?.length ?? 0
  if (recaps > 0) lines.push(`${recaps} earlier-conversation ${recaps === 1 ? "recap" : "recaps"}`)
  const files = (sent.memory ?? []).map((m) => MEMORY_FILES[m]).filter(Boolean)
  if (files.length > 0) lines.push(`the persona's memory (${files.join(", ")})`)
  if (sent.searched) lines.push(`Also searched for “${sent.searched}”`)
  const dropped = sent.history_dropped ?? 0
  if (dropped > 0) lines.push(`${dropped} older ${dropped === 1 ? "message" : "messages"} didn't fit in this chat`)
  return lines
}

/** Whether a reply gets a row under it: something specific to it was used (a note, an earlier exchange, a lookup or
 *  a remember, the fallback). The standing context alone never makes one, so a plain reply stays clean. */
export function hasFooterRow(sent: SentRecord | null | undefined): boolean {
  return groundedNotes(sent).length > 0 || groundedChats(sent) > 0 || calls(sent).length > 0 || fellBack(sent)
}

/** "Proposed 2 changes", "Proposed a change and left a comment", or that none could be placed. */
function actsSummary(acts: SentLookup[]): string {
  const done = acts.filter((l) => l.saved)
  if (done.length === 0) return `Could not place ${acts.some((l) => l.tool === "comment_on") && acts.every((l) => l.tool === "comment_on") ? "a comment" : "a change"}`
  const changes = done.filter((l) => l.tool === "propose_edit").length
  const parts = [
    changes > 0 ? (changes === 1 ? "proposed a change" : `proposed ${changes} changes`) : "",
    done.some((l) => l.tool === "propose_note") ? "proposed a new note" : "",
    done.some((l) => l.tool === "comment_on") ? "left a comment" : "",
  ].filter(Boolean)
  const text = parts.join(" and ")
  return text.charAt(0).toUpperCase() + text.slice(1)
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
  const acts = calls(sent).filter(isAct)
  if (acts.length > 0) return actsSummary(acts)
  const remembered = calls(sent).filter(isRemember)
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
  memory: "the persona's memory",
  open_note: "the open note",
  annotations: "your comments",
}

/** The categories of the vault a cloud model was sent or refused, in plain words (ADR 031's names are the code's). */
export function cloudWords(names: string[] | undefined): string[] {
  return (names ?? []).map((n) => CLOUD_WORDS[n] ?? n.replace(/_/g, " "))
}

/** Whether the reply came from a cloud model: its record names what was sent to it or held back from it (ADR 031). */
export function hasCloudSent(sent: SentRecord | null | undefined): boolean {
  return (sent?.cloud?.length ?? 0) > 0 || (sent?.withheld?.length ?? 0) > 0
}

