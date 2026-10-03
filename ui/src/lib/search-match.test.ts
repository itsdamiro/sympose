import { describe, expect, it } from "vitest"

import { matchesQuery } from "./search-match"

describe("matchesQuery", () => {
  it("matches everything for an empty or blank query", () => {
    expect(matchesQuery("Autosave", "")).toBe(true)
    expect(matchesQuery("Autosave", "   ")).toBe(true)
  })

  it("ignores case and matches inside a word", () => {
    expect(matchesQuery("Feedback messages", "BACK")).toBe(true)
    expect(matchesQuery("Feedback messages", "sage")).toBe(true)
  })

  it("needs every word, in any order, and not just one", () => {
    expect(matchesQuery("Delete confirmation dialog", "dialog delete")).toBe(true)
    expect(matchesQuery("Delete confirmation dialog", "delete autosave")).toBe(false)
  })
})
