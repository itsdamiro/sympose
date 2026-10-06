import { afterEach, describe, expect, it } from "vitest"

import { attach, setAttachmentsNote, takeAttached } from "./attachments"

const words = { quote: "three times", before: "I run ", after: " a week" }

afterEach(() => {
  setAttachmentsNote(undefined)
  takeAttached()
})

describe("attachments", () => {
  it("hands over what was attached once, then nothing", () => {
    setAttachmentsNote("a.md")
    attach(words)
    expect(takeAttached()).toEqual([words])
    expect(takeAttached()).toEqual([])
  })

  it("attaches the same words once and different words each", () => {
    setAttachmentsNote("a.md")
    attach(words)
    attach({ ...words })
    attach({ quote: "raised", before: "", after: "" })
    expect(takeAttached().map((a) => a.quote)).toEqual(["three times", "raised"])
  })

  it("attaches nothing with no note open or no words", () => {
    attach(words)
    setAttachmentsNote("a.md")
    attach({ quote: "", before: "", after: "" })
    expect(takeAttached()).toEqual([])
  })

  it("drops what was attached when another note opens", () => {
    setAttachmentsNote("a.md")
    attach(words)
    setAttachmentsNote("b.md")
    expect(takeAttached()).toEqual([])
  })
})
