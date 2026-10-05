import { afterEach, describe, expect, it } from "vitest"

import { getOpenNote, setOpenNoteSource } from "./open-note-source"

afterEach(() => setOpenNoteSource(null))

describe("the open note slot", () => {
  it("is empty until an editor registers", () => {
    expect(getOpenNote()).toBeNull()
  })

  it("reads the note as the editor holds it at the moment of asking, not as it was when registered", () => {
    let text = "one"
    setOpenNoteSource(() => ({ path: "a.md", text }))

    text = "one two"

    expect(getOpenNote()).toEqual({ path: "a.md", text: "one two" })
  })

  it("is empty again once the editor clears it", () => {
    setOpenNoteSource(() => ({ path: "a.md", text: "x" }))
    setOpenNoteSource(null)

    expect(getOpenNote()).toBeNull()
  })
})
