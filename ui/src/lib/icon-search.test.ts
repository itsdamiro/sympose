import { describe, expect, it } from "vitest"

import { searchIcons } from "./icon-search"
import { ICON_SET } from "./persona-icons"

describe("searchIcons", () => {
  it("gives the whole set, alphabetically, for nothing typed", () => {
    expect(searchIcons("")).toEqual(Object.keys(ICON_SET).sort())
    expect(searchIcons("   ")).toEqual(Object.keys(ICON_SET).sort())
  })

  it("finds an icon by the start of its name, case aside", () => {
    expect(searchIcons("FILM")[0]).toBe("film-roll")
  })

  it("puts a name that starts with the query before one that only contains it, then keyword matches", () => {
    const found = searchIcons("book")
    expect(found.slice(0, 3)).toEqual(["book", "book-open", "bookmark"])
  })

  it("puts names that start with the query before names that contain it, before words people use", () => {
    expect(searchIcons("he").slice(0, 2)).toEqual(["health", "heart"]) // "chef" contains "he" but sorts first
    const found = searchIcons("ar") // archive starts with it, chart and heart contain it, paintbrush has the word "art"
    expect(found[0]).toBe("archive")
    expect(found.indexOf("chart")).toBeLessThan(found.indexOf("paintbrush"))
    expect(found.indexOf("heart")).toBeLessThan(found.indexOf("paintbrush"))
  })

  it("finds an icon by a word people use for it", () => {
    expect(searchIcons("food")).toEqual(expect.arrayContaining(["chef", "chef-hat"]))
    expect(searchIcons("travel")).toContain("airplane")
    expect(searchIcons("money")).toEqual(expect.arrayContaining(["coins", "wallet"]))
  })

  it("finds nothing for a word no icon answers to", () => {
    expect(searchIcons("zzzz")).toEqual([])
  })

  it("never returns a name the set does not have", () => {
    for (const q of ["a", "e", "o", "work", "fit"]) {
      for (const name of searchIcons(q)) expect(Object.hasOwn(ICON_SET, name)).toBe(true)
    }
  })

  it("does not mistake a property of Object for an icon", () => {
    expect(searchIcons("constructor")).toEqual([])
  })
})
