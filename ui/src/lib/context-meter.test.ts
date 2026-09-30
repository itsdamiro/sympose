import { describe, expect, it } from "vitest"

import { ERROR_AT, WARN_AT, explanation, level, percent, tokens } from "./context-meter"

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
    expect(lines[1]).toContain("100% is where your next message starts leaving the oldest turns out")
    expect(lines[2]).toContain("leans a little high")
  })

  it("says an estimate is one, that it leans low, and that the next reply replaces it", () => {
    const lines = explanation({ used: 3812, limit: 6144, estimated: true })
    expect(lines[0]).toBe("3,812 of 6,144 tokens (estimated)")
    expect(lines[2]).toContain("leans low")
    expect(lines[2]).toContain("replaces it")
  })
})
