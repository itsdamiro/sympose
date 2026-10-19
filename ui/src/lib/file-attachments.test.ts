import { describe, expect, it } from "vitest"

import { MAX_BYTES, MAX_FILES, freeName, marker, named, take, toBase64, withMarkers, type PendingFile } from "./file-attachments"

const file = (name: string, size = 10) => new File([new Uint8Array(size)], name)
const pending = (name: string, size = 10): PendingFile => ({ name, file: file(name, size) })

describe("take", () => {
  it("takes the kinds the server reads, whatever the case of the ending", () => {
    const got = take([file("A.PDF"), file("b.jpeg"), file("c.m4a"), file("d.mov")], [])
    expect(got.ok).toBe(false) // four files: one over the limit
    const three = take([file("A.PDF"), file("b.jpeg"), file("c.m4a")], [])
    expect(three.ok && three.added.map((p) => p.name)).toEqual(["A.PDF", "b.jpeg", "c.m4a"])
  })

  it("says what is read when a file is not one of those, and adds none of the others", () => {
    expect(take([file("a.pdf"), file("notes.txt")], [])).toEqual({
      ok: false,
      error: "Can't attach notes.txt: Sympose reads PDFs, images, sounds and videos.",
    })
  })

  it("refuses an empty file, more than the limit, and more bytes than the limit together", () => {
    expect(take([file("a.pdf", 0)], [])).toMatchObject({ ok: false, error: "Can't attach a.pdf: it is empty." })
    expect(take([file("b.pdf")], [pending("a.pdf"), pending("c.pdf"), pending("d.pdf")])).toEqual({
      ok: false,
      error: `At most ${MAX_FILES} files can go with one message.`,
    })
    expect(take([file("b.pdf", 2)], [pending("a.pdf", MAX_BYTES - 1)])).toMatchObject({ ok: false, error: expect.stringContaining("over 50 MB") })
  })

  it("numbers a name already waiting, so each marker names one file", () => {
    const got = take([file("a.pdf"), file("a.pdf")], [pending("a.pdf")])
    expect(got.ok && got.added.map((p) => p.name)).toEqual(["a (2).pdf", "a (3).pdf"])
    expect(freeName("a", ["a"])).toBe("a (2)")
  })
})

describe("the marker in the words", () => {
  it("goes in at the caret on a space of its own, or at the end", () => {
    const added = [pending("a.pdf")]
    expect(withMarkers("read this", added, null)).toBe("read this [attached: a.pdf]")
    expect(withMarkers("read this please", added, 9)).toBe("read this [attached: a.pdf] please")
    expect(withMarkers("", added, 0)).toBe("[attached: a.pdf]")
    expect(withMarkers("a\n", added, 2)).toBe("a\n[attached: a.pdf]")
    expect(withMarkers("x", added, 99)).toBe("x [attached: a.pdf]")
  })

  it("is how a file is kept or taken back: only a file still named in the text goes", () => {
    const waiting = [pending("a.pdf"), pending("b.png")]
    expect(named(`what is ${marker("b.png")}?`, waiting).map((p) => p.name)).toEqual(["b.png"])
    expect(named("nothing", waiting)).toEqual([])
  })
})

describe("toBase64", () => {
  it("encodes every byte, also past the size it is encoded in pieces of", async () => {
    const bytes = Uint8Array.from({ length: 0x8000 * 2 + 5 }, (_, i) => i % 256)
    const decoded = Uint8Array.from(atob(await toBase64(new File([bytes], "a.mp4"))), (c) => c.charCodeAt(0))
    expect(decoded).toEqual(bytes)
  })
})
