import { describe, expect, it } from "vitest"

import type { SentNote } from "@/lib/chat-types"
import { cloudWords, hasCloudSent, groundedChats, groundedChatsLine, groundedContext, groundedLookups, groundedNotes, hasFooterRow, rowSummary, groundedSummary, isReference, noteDetail, noteTitle } from "./grounded"

const note = (extra: Partial<SentNote> = {}): SentNote => ({ path: "Projects/Atlas.md", heading: "", source: "vault", ...extra })

describe("grounded notes", () => {
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
    expect(groundedSummary([reference])).toBe("Based on the Sympose reference library")
  })

  it("says how a note was found, in the terminal's words, and how close a meaning match was", () => {
    expect(noteDetail(note({ via: "embedding", similarity: 0.8123 }))).toBe("by meaning · similarity 0.81")
    expect(noteDetail(note({ via: "name" }))).toBe("named in full")
    expect(noteDetail(note({ via: "value" }))).toBe("by a property value")
    expect(noteDetail(note({ via: "search" }))).toBe("found by search")
    expect(noteDetail(note({ via: "opened" }))).toBe("opened by a lookup")
    expect(noteDetail(note({ source: "sympose" }))).toBe("the Sympose reference library")
    expect(noteDetail(note())).toBe("")
  })

  it("shows a similarity of 0 rather than dropping it", () => {
    expect(noteDetail(note({ via: "embedding", similarity: 0 }))).toBe("by meaning · similarity 0.00")
  })

  it("counts the earlier-conversation exchanges that reached the model, and says so in the terminal's words", () => {
    const chat = { session: "s1", turn: 3, how: "auto" }
    expect(groundedChats(null)).toBe(0)
    expect(groundedChats({ notes: [] })).toBe(0)
    expect(groundedChats({ notes: [], chats: [chat, { ...chat, turn: 4 }] })).toBe(2)
    expect(groundedChatsLine(1)).toBe("1 exchange from earlier conversations, word for word")
    expect(groundedChatsLine(2)).toBe("2 exchanges from earlier conversations, word for word")
  })

  it("names the exchanges in the summary, alone or beside notes", () => {
    expect(groundedSummary([], 2)).toBe("Based on 2 earlier exchanges")
    expect(groundedSummary([], 1)).toBe("Based on 1 earlier exchange")
    expect(groundedSummary([note()], 2)).toBe("Based on Atlas and 2 earlier exchanges")
    expect(groundedSummary([note(), note({ path: "Projects/Beta.md" })], 1)).toBe("Based on 2 notes and 1 earlier exchange")
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

  it("says when ask could not be used and Sympose searched instead, for notes and for earlier conversations", () => {
    expect(groundedLookups({ ...base, mode: "auto" })).toEqual(["You chose ask, but this model can't call tools, so Sympose searched for the message."])
    expect(groundedLookups({ ...base, chats_mode: "auto" })).toEqual([
      "You chose ask for earlier conversations, but this model can't call tools, so Sympose searched for the message.",
    ])
  })

  it("says she looked nothing up when ask was on and she did not", () => {
    expect(groundedLookups({ ...base, mode: "ask", lookups: [] })).toEqual(["Looked nothing up for this message."])
    expect(groundedLookups(base)).toEqual([])
    expect(groundedLookups(null)).toEqual([])
  })

  it("lists the standing context: recaps, her memory files, the follow-up query and the turns left out", () => {
    expect(
      groundedContext({ ...base, recaps: ["s1", "s2"], memory: ["profile", "decisions"], searched: "atlas database", history_dropped: 3 })
    ).toEqual(["2 earlier-conversation recaps", "her memory (profile.md, decisions.md)", "Searched for “atlas database”", "3 older turns left out of context"])
    expect(groundedContext({ ...base, recaps: ["s1"], history_dropped: 1 })).toEqual(["1 earlier-conversation recap", "1 older turn left out of context"])
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
    expect(hasFooterRow({ ...base, mode: "auto" })).toBe(true)
    expect(hasFooterRow(null)).toBe(false)
  })

  it("names the closed row by what the reply used, and by what she did when she found nothing", () => {
    const note = { path: "Projects/Atlas.md", heading: "", source: "vault" }
    expect(rowSummary({ notes: [note] })).toBe("Based on Atlas")
    expect(rowSummary({ notes: [note], chats: [{ session: "s", turn: 1, how: "auto" }] })).toBe("Based on Atlas and 1 earlier exchange")
    expect(rowSummary({ ...base, lookups: [{ tool: "search_notes", query: "x", found: 0 }, { tool: "search_notes", query: "y", found: 0 }] })).toBe("Looked up 2 things")
    expect(rowSummary({ ...base, lookups: [{ tool: "search_notes", query: "x", found: 0 }] })).toBe("Looked up one thing")
    expect(rowSummary({ ...base, lookups: [{ tool: "remember", saved: true }] })).toBe("Remembered something")
    expect(rowSummary({ ...base, lookups: [{ tool: "remember", saved: false }] })).toBe("Tried to remember something")
    expect(rowSummary({ ...base, mode: "auto" })).toBe("Sympose searched for the message")
    expect(rowSummary(base)).toBeNull()
  })

  it("puts the categories a cloud model was sent or refused in plain words", () => {
    expect(cloudWords(["notes", "vault_map", "chats", "properties", "connections", "memory", "recaps"])).toEqual([
      "notes", "vault map", "earlier conversations", "note properties", "note connections", "her memory", "recaps",
    ])
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

