import { describe, expect, it } from "vitest"

import type { SentNote } from "@/lib/chat-types"
import { cloudWords, hasCloudSent, groundedChats, groundedChatsLine, groundedContext, groundedLookups, groundedNotes, hasFooterRow, rowSummary, groundedSummary, isReference, noteDetail, noteTitle } from "./grounded"

const note = (extra: Partial<SentNote> = {}): SentNote => ({ path: "Projects/Atlas.md", heading: "", source: "vault", ...extra })

describe("grounded notes", () => {
  it("adds no row for a persona she proposed: the card under the reply is its sign", () => {
    expect(hasFooterRow({ notes: [], lookups: [{ tool: "propose_persona", saved: true, request: "r1" }] })).toBe(false)
    expect(rowSummary({ notes: [], lookups: [{ tool: "propose_persona", saved: false }] })).toBeNull()
  })

  it("has no notes when nothing grounded the reply, or when the record is missing", () => {
    expect(groundedNotes(null)).toEqual([])
    expect(groundedNotes(undefined)).toEqual([])
    expect(groundedNotes({ notes: [] })).toEqual([])
  })

  it("names a note as a reader knows it: no folder, no .md", () => {
    expect(noteTitle("Projects/Atlas.md")).toBe("Atlas")
    expect(noteTitle("Atlas.MD")).toBe("Atlas")
    expect(noteTitle("Projects/Notes.md.md")).toBe("Notes.md")
  })

  it("summarizes one note by its name and several by their number", () => {
    expect(groundedSummary([note()])).toBe("Based on Atlas")
    expect(groundedSummary([note(), note({ path: "Projects/Beta.md" })])).toBe("Based on 2 notes")
  })

  it("counts a note once however many of its passages were used", () => {
    expect(groundedSummary([note({ heading: "Goals" }), note({ heading: "Risks" })])).toBe("Based on Atlas")
  })

  it("does not call the reference library a note of the user's", () => {
    const reference = note({ path: "Sympose/Settings.md", source: "sympose" })
    expect(isReference(reference)).toBe(true)
    expect(isReference(note())).toBe(false)
    expect(groundedSummary([reference])).toBe("Based on Sympose's built-in help")
  })

  it("says how a note was found, in the terminal's words, and how close a meaning match was", () => {
    expect(noteDetail(note({ via: "embedding", similarity: 0.8123 }))).toBe("found by topic · close match")
    expect(noteDetail(note({ via: "name" }))).toBe("named in full")
    expect(noteDetail(note({ via: "value" }))).toBe("by a property value")
    expect(noteDetail(note({ via: "search" }))).toBe("found by search")
    expect(noteDetail(note({ via: "opened" }))).toBe("opened by a lookup")
    expect(noteDetail(note({ source: "sympose" }))).toBe("Sympose's built-in help")
    expect(noteDetail(note())).toBe("")
  })

  it("shows a similarity of 0 as a partial match rather than dropping it", () => {
    expect(noteDetail(note({ via: "embedding", similarity: 0 }))).toBe("found by topic · partial match")
  })

  it("counts the earlier-conversation exchanges that reached the model, and says so in the terminal's words", () => {
    const chat = { session: "s1", turn: 3, how: "auto" }
    expect(groundedChats(null)).toBe(0)
    expect(groundedChats({ notes: [] })).toBe(0)
    expect(groundedChats({ notes: [], chats: [chat, { ...chat, turn: 4 }] })).toBe(2)
    expect(groundedChatsLine(1)).toBe("1 message from earlier chats, quoted exactly")
    expect(groundedChatsLine(2)).toBe("2 messages from earlier chats, quoted exactly")
  })

  it("says which skill she took up, and that a skill is not a lookup", () => {
    const sent = {
      ...{ notes: [] },
      mode: "ask",
      lookups: [
        { tool: "use_skill", query: "deriving-a-persona-soul", found: 1 },
        { tool: "use_skill", query: "nope", found: 0 },
      ],
    }
    expect(groundedLookups(sent)).toEqual([
      "Looked nothing up for this message.",
      'followed the skill "deriving-a-persona-soul"',
      'asked for a skill that does not exist ("nope")',
    ])
  })

  it("names the exchanges in the summary, alone or beside notes", () => {
    expect(groundedSummary([], 2)).toBe("Based on 2 earlier messages")
    expect(groundedSummary([], 1)).toBe("Based on 1 earlier message")
    expect(groundedSummary([note()], 2)).toBe("Based on Atlas and 2 earlier messages")
    expect(groundedSummary([note(), note({ path: "Projects/Beta.md" })], 1)).toBe("Based on 2 notes and 1 earlier message")
  })

  const base = { notes: [] }

  it("says what she looked up herself in the terminal's words, and what she remembered", () => {
    const sent = {
      ...base,
      mode: "ask",
      lookups: [
        { tool: "search_notes", query: "atlas", found: 3 },
        { tool: "open_note", path: "Projects/Atlas.md", found: 1 },
        { tool: "search_chats", query: "that budget", found: 0 },
        { tool: "remember", saved: true },
        { tool: "remember", saved: false },
      ],
    }
    expect(groundedLookups(sent)).toEqual([
      'searched "atlas" (3 found)',
      'opened "Projects/Atlas.md" (1 found)',
      'searched earlier conversations for "that budget" (0 found)',
      "remembered something",
      "tried to remember something and could not save it",
    ])
  })

  it("says what she did to a note in words, not as a lookup", () => {
    const sent = {
      ...base,
      lookups: [
        { tool: "propose_edit", saved: true },
        { tool: "propose_edit", saved: false },
        { tool: "propose_note", saved: true },
        { tool: "comment_on", saved: true },
      ],
    }
    expect(groundedLookups(sent)).toEqual([
      "proposed a change",
      "tried to propose a change and could not place it",
      "proposed a new note",
      "left a comment",
    ])
  })

  it("says when ask could not be used and Sympose searched instead, for notes and for earlier conversations", () => {
    expect(groundedLookups({ ...base, mode: "auto" })).toEqual(["This model can't look things up on its own, so Sympose searched your notes for you."])
    expect(groundedLookups({ ...base, chats_mode: "auto" })).toEqual([
      "This model can't look things up on its own, so Sympose searched your earlier chats for you.",
    ])
  })

  it("says she looked nothing up when ask was on and she did not", () => {
    expect(groundedLookups({ ...base, mode: "ask", lookups: [] })).toEqual(["Looked nothing up for this message."])
    expect(groundedLookups(base)).toEqual([])
    expect(groundedLookups(null)).toEqual([])
  })

  it("lists the standing context: recaps, the persona's memory files, the follow-up query and the turns left out", () => {
    expect(
      groundedContext({ ...base, recaps: ["s1", "s2"], memory: ["profile", "decisions"], searched: "atlas database", history_dropped: 3 })
    ).toEqual(["2 earlier-conversation recaps", "the persona's memory (profile.md, decisions.md)", "Also searched for “atlas database”", "3 older messages didn't fit in this chat"])
    expect(groundedContext({ ...base, recaps: ["s1"], history_dropped: 1 })).toEqual(["1 earlier-conversation recap", "1 older message didn't fit in this chat"])
    expect(groundedContext(base)).toEqual([])
    expect(groundedContext(undefined)).toEqual([])
  })

  it("has a row only when something specific to the reply was used, never for the standing context alone", () => {
    expect(hasFooterRow({ ...base, recaps: ["s1"], memory: ["profile"], history_dropped: 2 })).toBe(false)
    expect(hasFooterRow({ ...base, mode: "ask", lookups: [] })).toBe(false) // she chose not to look: shown only inside a row that exists
    expect(hasFooterRow({ notes: [{ path: "A.md", heading: "", source: "vault" }] })).toBe(true)
    expect(hasFooterRow({ ...base, chats: [{ session: "s", turn: 1, how: "auto" }] })).toBe(true)
    expect(hasFooterRow({ ...base, lookups: [{ tool: "search_notes", query: "x", found: 0 }] })).toBe(true)
    expect(hasFooterRow({ ...base, lookups: [{ tool: "remember", saved: true }] })).toBe(true)
    expect(hasFooterRow({ ...base, lookups: [{ tool: "propose_edit", saved: true }] })).toBe(true)
    expect(hasFooterRow({ ...base, mode: "auto" })).toBe(true)
    expect(hasFooterRow(null)).toBe(false)
  })

  it("names the closed row by what the reply used, and by what she did when she found nothing", () => {
    const note = { path: "Projects/Atlas.md", heading: "", source: "vault" }
    expect(rowSummary({ notes: [note] })).toBe("Based on Atlas")
    expect(rowSummary({ notes: [note], chats: [{ session: "s", turn: 1, how: "auto" }] })).toBe("Based on Atlas and 1 earlier message")
    expect(rowSummary({ ...base, lookups: [{ tool: "search_notes", query: "x", found: 0 }, { tool: "search_notes", query: "y", found: 0 }] })).toBe("Looked up 2 things")
    expect(rowSummary({ ...base, lookups: [{ tool: "search_notes", query: "x", found: 0 }] })).toBe("Looked up one thing")
    expect(rowSummary({ ...base, lookups: [{ tool: "remember", saved: true }] })).toBe("Remembered something")
    expect(rowSummary({ ...base, lookups: [{ tool: "remember", saved: false }] })).toBe("Tried to remember something")
    expect(rowSummary({ ...base, lookups: [{ tool: "propose_edit", saved: true }] })).toBe("Proposed a change")
    expect(rowSummary({ ...base, lookups: [{ tool: "propose_edit", saved: true }, { tool: "propose_edit", saved: true }] })).toBe("Proposed 2 changes")
    expect(rowSummary({ ...base, lookups: [{ tool: "propose_edit", saved: true }, { tool: "comment_on", saved: true }] })).toBe("Proposed a change and left a comment")
    expect(rowSummary({ ...base, lookups: [{ tool: "propose_edit", saved: false }] })).toBe("Could not place a change")
    expect(rowSummary({ ...base, lookups: [{ tool: "comment_on", saved: true }] })).toBe("Left a comment")
    expect(rowSummary({ ...base, lookups: [{ tool: "propose_note", saved: true }] })).toBe("Proposed a new note")
    expect(rowSummary({ ...base, mode: "auto" })).toBe("Sympose searched for the message")
    expect(rowSummary(base)).toBeNull()
  })

  it("puts the categories a cloud model was sent or refused in plain words", () => {
    expect(cloudWords(["notes", "vault_map", "chats", "properties", "connections", "memory", "recaps"])).toEqual([
      "notes", "vault map", "earlier conversations", "note properties", "note connections", "the persona's memory", "recaps",
    ])
    expect(cloudWords(["open_note", "annotations"])).toEqual(["the open note", "your comments"])
    expect(cloudWords(["something_new"])).toEqual(["something new"])
    expect(cloudWords(undefined)).toEqual([])
  })

  it("knows a reply came from a cloud model by its record naming what was sent or held back", () => {
    expect(hasCloudSent({ notes: [], cloud: ["notes"] })).toBe(true)
    expect(hasCloudSent({ notes: [], cloud: [], withheld: ["memory"] })).toBe(true)
    expect(hasCloudSent({ notes: [], cloud: [], withheld: [] })).toBe(false)
    expect(hasCloudSent({ notes: [] })).toBe(false)
    expect(hasCloudSent(null)).toBe(false)
  })
})


describe("opening a note for the user", () => {
  it("adds nothing to a reply's footer: the editor showing it is the sign", () => {
    const sent = { notes: [], lookups: [{ tool: "show_note", path: "Projects/Atlas.md", saved: true }] }

    expect(hasFooterRow(sent)).toBe(false)
    expect(groundedLookups(sent)).toEqual([])
  })
})
