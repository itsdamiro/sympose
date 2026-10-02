import { describe, expect, it } from "vitest"

import type { SentNote } from "@/lib/chat-types"
import { groundedChats, groundedChatsLine, groundedNotes, groundedSummary, isReference, noteDetail, noteTitle } from "./grounded"

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
})
