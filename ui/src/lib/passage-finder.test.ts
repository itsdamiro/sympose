import { describe, expect, it } from "vitest"

import { captureContext, locate } from "./passage-finder"

const NOTE = "I run three times a week. The beds are raised.\n\n- Pack charger\n- Phone\n\n## Electronics\n\n- Pack charger\n"

describe("locate", () => {
  it("finds a passage that occurs once, where it is", () => {
    const found = locate(NOTE, "three times")
    expect(found.status).toBe("one")
    if (found.status === "one") expect(NOTE.slice(found.start, found.end)).toBe("three times")
  })

  it("says none for a passage that is not there and for an empty quote", () => {
    expect(locate(NOTE, "four times").status).toBe("none")
    expect(locate(NOTE, "").status).toBe("none")
  })

  it("says many for a passage twice with no context", () => {
    expect(locate(NOTE, "- Pack charger").status).toBe("many")
  })

  it("uses the context to pick which of two it was", () => {
    const at = NOTE.lastIndexOf("- Pack charger")
    const [before, after] = captureContext(NOTE, at, at + 14)
    expect(locate(NOTE, "- Pack charger", before, after)).toEqual({ status: "one", start: at, end: at + 14 })
  })

  it("still picks the right one after text is typed before both", () => {
    const at = NOTE.indexOf("- Pack charger")
    const [before, after] = captureContext(NOTE, at, at + 14)
    const edited = "XX " + NOTE
    expect(locate(edited, "- Pack charger", before, after)).toMatchObject({ status: "one", start: edited.indexOf("- Pack charger") })
  })

  it("is many when the context fits both equally or fits neither", () => {
    expect(locate("alpha\nsame\nalpha\nsame\n", "same", "alpha\n", "\n").status).toBe("many")
    expect(locate(NOTE, "- Pack charger", "unrelated", "unrelated").status).toBe("many")
  })

  it("lets the better fitting context win even if neither is perfect", () => {
    const at = NOTE.lastIndexOf("- Pack charger")
    const [before, after] = captureContext(NOTE, at, at + 14)
    const edited = NOTE.replace("## Electronics", "## Gadgets")
    expect(locate(edited, "- Pack charger", before, after)).toMatchObject({ status: "one", start: edited.lastIndexOf("- Pack charger") })
  })

  it("counts overlapping occurrences as many", () => {
    expect(locate("aaa", "aa").status).toBe("many")
  })

  it("does not compare a passage at the very start with the end of the note", () => {
    expect(locate("a b a z", "a", "z", "").status).toBe("many")
  })

  it("is none for a passage edited in place", () => {
    const at = NOTE.indexOf("three times")
    const [before, after] = captureContext(NOTE, at, at + 11)
    expect(locate(NOTE.replace("three times", "five times"), "three times", before, after).status).toBe("none")
  })
})

describe("captureContext", () => {
  it("takes text from either side, bounded", () => {
    const text = "0123456789".repeat(20)
    expect(captureContext(text, 100, 105, 7)).toEqual([text.slice(93, 100), text.slice(105, 112)])
  })

  it("keeps what there is near the edges of the note", () => {
    expect(captureContext("abc", 0, 3, 10)).toEqual(["", ""])
    expect(captureContext("abcdefgh", 3, 5, 10)).toEqual(["abc", "fgh"])
  })
})
