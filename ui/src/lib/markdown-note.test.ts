import { describe, expect, it } from "vitest"

import { joinNote, syncInlineTags } from "./markdown-note"

describe("joinNote", () => {
  it("is the body alone when the note had no frontmatter", () => {
    expect(joinNote(null, "Body\n", null, false)).toBe("Body\n")
  })

  it("splices the body onto the file's exact original prefix while the card was not edited", () => {
    const prefix = "---\r\ntitle:   'x'\r\n---\r\n"
    expect(joinNote("title:   'x'", "New body\r\n", prefix, false)).toBe(prefix + "New body\r\n")
  })

  it("re-serialises the block once the card was edited", () => {
    expect(joinNote("title: y\n", "Body", "---\ntitle: x\n---\n", true)).toBe("---\ntitle: y\n---\n\nBody")
  })
})

describe("syncInlineTags", () => {
  it("leaves a note with no frontmatter alone", () => {
    expect(syncInlineTags(null, "A #tag")).toEqual({ frontmatter: null, changed: false })
  })

  it("adds a body tag the frontmatter lacks, lower-cased, and never removes one", () => {
    const out = syncInlineTags("tags: [a]\n", "text #B and #a")
    expect(out.changed).toBe(true)
    expect(out.frontmatter).toMatch(/tags:[\s\S]*a[\s\S]*b/)
  })

  it("changes nothing when every body tag is already there, whatever its case", () => {
    expect(syncInlineTags("tags: [Alpha]\n", "see #alpha")).toEqual({ frontmatter: "tags: [Alpha]\n", changed: false })
  })
})
