import { describe, expect, it } from "vitest"

import type { SentNote } from "@/lib/chat-types"
import { groundedNotes, groundedSummary, isReference, noteDetail, noteTitle } from "./grounded"

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
})
