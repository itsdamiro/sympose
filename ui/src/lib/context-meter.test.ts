import { describe, expect, it } from "vitest"

import { ERROR_AT, KEEP_TURNS, WARN_AT, condenseAdvised, explanation, level, percent, tokens } from "./context-meter"

describe("percent", () => {
  it("is the whole percent of the budget in use", () => {
    expect(percent(3812, 6144)).toBe(62)
    expect(percent(0, 6144)).toBe(0)
    expect(percent(1, 3)).toBe(33)
  })

  it("never goes above 100, and a hair under the budget reads 99", () => {
    expect(percent(9000, 6144)).toBe(100)
    expect(percent(6144, 6144)).toBe(100)
    expect(percent(6143, 6144)).toBe(99)
    expect(percent(6100, 6144)).toBe(99)
  })

  it("never goes below 0", () => {
    expect(percent(-5, 100)).toBe(0)
  })
})

describe("level", () => {
  it("is ok below 70, warn from 70 and error from 90", () => {
    expect([69, WARN_AT, 89, ERROR_AT, 100].map(level)).toEqual(["ok", "warn", "warn", "error", "error"])
    expect(WARN_AT).toBe(70)
    expect(ERROR_AT).toBe(90)
  })
})

describe("tokens", () => {
  it("groups thousands and does not go below zero", () => {
    expect(tokens(3812)).toBe("3,812")
    expect(tokens(812)).toBe("812")
    expect(tokens(-4)).toBe("0")
  })
})

describe("explanation", () => {
  it("gives the figures in full, what 100% means, and that a real figure leans high", () => {
    const lines = explanation({ used: 3812, limit: 6144, estimated: false })
    expect(lines[0]).toBe("3,812 of 6,144 tokens")
    expect(lines[1]).toContain("100% is where the oldest messages start to be left out")
    expect(lines[2]).toContain("leans a little high")
  })

  it("says an estimate is one, that it leans low, and that the next reply replaces it", () => {
    const lines = explanation({ used: 3812, limit: 6144, estimated: true })
    expect(lines[0]).toBe("3,812 of 6,144 tokens (estimated)")
    expect(lines[2]).toContain("leans low")
    expect(lines[2]).toContain("replaces it")
  })
})

describe("condenseAdvised", () => {
  const at = (pct: number) => ({ used: pct * 10, limit: 1000, estimated: false })
  const base = { answered: 8, condensed: 0, hasMore: false }

  it("is not advised while the meter is below its warning level, however long the conversation", () => {
    expect(condenseAdvised({ ...base, figure: at(WARN_AT - 1), answered: 40 })).toBe(false)
  })

  it("is advised from the warning level, once there is something to fold", () => {
    expect(condenseAdvised({ ...base, figure: at(WARN_AT) })).toBe(true)
    expect(condenseAdvised({ ...base, figure: at(ERROR_AT + 5) })).toBe(true)
  })

  it("has nothing to fold in the newest turns, which a condense leaves as they are", () => {
    expect(KEEP_TURNS).toBe(3) // the engine's own (compaction.py KEEP_TURNS)
    expect(condenseAdvised({ ...base, figure: at(95), answered: KEEP_TURNS })).toBe(false)
    expect(condenseAdvised({ ...base, figure: at(95), answered: KEEP_TURNS + 1 })).toBe(true)
  })

  it("does not count turns the notes already stand for", () => {
    expect(condenseAdvised({ ...base, figure: at(95), answered: 8, condensed: 5 })).toBe(false)
    expect(condenseAdvised({ ...base, figure: at(95), answered: 8, condensed: 4 })).toBe(true)
  })

  it("takes older turns that are not loaded yet as plenty to fold", () => {
    expect(condenseAdvised({ ...base, figure: at(95), answered: 2, hasMore: true })).toBe(true)
  })

  it("is not advised without a figure", () => {
    expect(condenseAdvised({ ...base, figure: null })).toBe(false)
  })
})

