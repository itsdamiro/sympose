import { describe, expect, it } from "vitest"

import { MAX_COOKIE_VALUE, readList, remapPath, writeList } from "./cookie-list"

describe("readList / writeList", () => {
  it("round-trips a path with a comma as one entry", () => {
    const list = ["Notes, 2026.md", "b.md"]
    expect(readList(writeList(list))).toEqual(list)
  })

  it("still reads the older comma-joined form", () => {
    expect(readList("a.md,b/c.md")).toEqual(["a.md", "b/c.md"])
  })

  it("reads nothing from an empty, broken or non-list value", () => {
    expect(readList(null)).toEqual([])
    expect(readList("")).toEqual([])
    expect(readList("[broken")).toEqual([])
    expect(readList('["a.md", 3, null, ""]')).toEqual(["a.md"])
  })

  it("trims the oldest from the front of an insertion-ordered list", () => {
    const list = Array.from({ length: 400 }, (_, i) => `folder/note-${i}.md`)
    const out = readList(writeList(list))
    expect(encodeURIComponent(writeList(list)).length).toBeLessThanOrEqual(
      MAX_COOKIE_VALUE
    )
    expect(out.length).toBeLessThan(list.length)
    expect(out[out.length - 1]).toBe("folder/note-399.md")
    expect(out[0]).not.toBe("folder/note-0.md")
  })

  it("trims the oldest from the end of a newest-first list", () => {
    const list = Array.from({ length: 400 }, (_, i) => `folder/note-${i}.md`)
    const out = readList(writeList(list, true))
    expect(out[0]).toBe("folder/note-0.md")
    expect(out.length).toBeLessThan(list.length)
  })

  it("leaves a list that fits untouched", () => {
    expect(readList(writeList(["a.md", "b.md"]))).toEqual(["a.md", "b.md"])
  })
})

describe("remapPath", () => {
  it("replaces the old path in place", () => {
    expect(remapPath(["a.md", "b.md", "c.md"], "b.md", "x/b.md")).toEqual([
      "a.md",
      "x/b.md",
      "c.md",
    ])
  })

  it("returns the same list when the path is not in it", () => {
    const list = ["a.md"]
    expect(remapPath(list, "z.md", "y.md")).toBe(list)
  })

  it("drops a duplicate when the new path is already there", () => {
    expect(remapPath(["a.md", "b.md"], "a.md", "b.md")).toEqual(["b.md"])
  })
})
