import { describe, expect, it } from "vitest"

import { clashList, reachLine, suggestedName } from "./folder-move-wording"

const grace = { handle: "g", name: "Grace", gains: 12, loses: 0 }

describe("reachLine", () => {
  it("says what a persona gains", () => expect(reachLine(grace)).toBe("This gives Grace access to 12 notes."))
  it("says what she loses, singular for one", () => expect(reachLine({ ...grace, gains: 0, loses: 1 })).toBe("This takes 1 note away from Grace."))
  it("says both when a move does both", () =>
    expect(reachLine({ ...grace, gains: 1, loses: 3 })).toBe("This gives Grace access to 1 note and takes 3 notes away from Grace."))
})

describe("clashList", () => {
  it("shows them all when there are few", () => expect(clashList(["a", "b"])).toEqual({ shown: ["a", "b"], more: 0 }))
  it("shows the first few and counts the rest", () => {
    const files = Array.from({ length: 11 }, (_, i) => `f${i}`)
    expect(clashList(files)).toEqual({ shown: files.slice(0, 8), more: 3 })
  })
})

it("suggests a numbered name", () => expect(suggestedName("People")).toBe("People (2)"))
