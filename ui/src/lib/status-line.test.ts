// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest"

import { CHARS_PER_SECOND, PHASE_TEXT, StatusLine, typingSpeed } from "./status-line"

const PHRASES = ["Alpha one…", "Beta two…", "Gamma three…"]
const text = (line: string) => line.slice(2) // without the spinner
const sequence = (values: number[]) => {
  let i = 0
  return () => values[i++ % values.length]
}

afterEach(() => vi.unstubAllGlobals())

describe("the busy line's rotation", () => {
  it("shows the phase's literal text at first and nothing before a reply is in flight", () => {
    const line = new StatusLine()
    expect(line.line(null, PHRASES, 0, 0)).toBe("")
    expect(text(line.line("searching", PHRASES, 0, 0))).toBe(PHASE_TEXT.searching)
    expect(text(line.line("searching", PHRASES, 2.9, 0))).toBe(PHASE_TEXT.searching)
  })

  it("turns witty at 3 seconds, holds it for its slot, and brings the literal text back every other slot", () => {
    const line = new StatusLine()
    const at = (t: number) => text(line.line("reading", PHRASES, t, 0))
    at(0)
    const first = at(3)
    expect(PHRASES).toContain(first)
    expect(at(5.9)).toBe(first)
    expect(at(6)).toBe(PHASE_TEXT.reading)
    expect(at(8.9)).toBe(PHASE_TEXT.reading)
    expect(PHRASES).toContain(at(9))
    expect(at(12)).toBe(PHASE_TEXT.reading)
  })

  it("never shows the witty phrase it showed last, however the random pick falls", () => {
    const line = new StatusLine(() => 0) // would always pick the first candidate
    const at = (t: number) => text(line.line("asking", PHRASES, t, 0))
    at(0)
    const seen = [at(3), at(9), at(15), at(21), at(27)]
    expect(seen.every((p, i) => i === 0 || p !== seen[i - 1])).toBe(true)
    expect(new Set(seen).size).toBeGreaterThan(1)
  })

  it("uses the persona's one phrase again when it has only one, and the literal text when it has none", () => {
    const one = new StatusLine()
    one.line("asking", ["Only one…"], 0, 0)
    expect(text(one.line("asking", ["Only one…"], 3, 0))).toBe("Only one…")
    expect(text(one.line("asking", ["Only one…"], 9, 0))).toBe("Only one…")
    const none = new StatusLine()
    none.line("asking", [], 0, 0)
    expect(text(none.line("asking", [], 3, 0))).toBe(PHASE_TEXT.asking)
  })

  it("starts its rotation again from the moment the phase changes", () => {
    const line = new StatusLine()
    line.line("searching", PHRASES, 0, 0)
    line.line("searching", PHRASES, 3, 0)
    expect(text(line.line("reading", PHRASES, 100, 0))).toBe(PHASE_TEXT.reading)
    expect(text(line.line("reading", PHRASES, 102.9, 0))).toBe(PHASE_TEXT.reading)
    expect(PHRASES).toContain(text(line.line("reading", PHRASES, 103, 0)))
  })

  it("keeps typing the new phase's text through its first frames, the rotation slot starting at zero", () => {
    const line = new StatusLine()
    line.line("searching", PHRASES, 0, 10)
    line.line("searching", PHRASES, 3, 10) // a rotation slot has been reached
    expect(text(line.line("reading", PHRASES, 100, 10))).toBe("R")
    expect(text(line.line("reading", PHRASES, 100.5, 10))).toBe("Readin") // typed on, not started over
  })

  it("reads the phrases it is given each time, so ones that arrive mid-wait are used", () => {
    const line = new StatusLine()
    line.line("asking", ["Generic one…"], 0, 0)
    expect(text(line.line("asking", ["Own phrase…"], 3, 0))).toBe("Own phrase…")
  })

  it("picks with the random source it was given", () => {
    const line = new StatusLine(sequence([0.99]))
    line.line("asking", PHRASES, 0, 0)
    expect(text(line.line("asking", PHRASES, 3, 0))).toBe("Gamma three…")
  })
})

describe("the busy line's typing", () => {
  it("types a phrase out one letter at a time at the speed given, the first letter at once", () => {
    const line = new StatusLine()
    expect(text(line.line("asking", PHRASES, 0, 10))).toBe("T")
    expect(text(line.line("asking", PHRASES, 0.2, 10))).toBe("Thi")
    expect(text(line.line("asking", PHRASES, 0.5, 10))).toBe("Thinki")
    expect(text(line.line("asking", PHRASES, 2.9, 10))).toBe(PHASE_TEXT.asking) // whole once it has had time
  })

  it("starts typing again for each new phrase", () => {
    const line = new StatusLine()
    line.line("asking", PHRASES, 0, 10)
    expect(text(line.line("asking", PHRASES, 2.9, 10))).toBe(PHASE_TEXT.asking)
    expect(text(line.line("asking", PHRASES, 3, 10)).length).toBe(1)
    expect(text(line.line("asking", PHRASES, 3.5, 10)).length).toBe(6)
  })

  it("shows a phrase whole when the speed is 0", () => {
    const line = new StatusLine()
    expect(text(line.line("searching", PHRASES, 0, 0))).toBe(PHASE_TEXT.searching)
  })

  it("advances the spinner every third frame, whatever the typing speed", () => {
    const line = new StatusLine()
    const frames = Array.from({ length: 7 }, () => line.line("asking", PHRASES, 0, 0)[0])
    expect(frames[0]).toBe(frames[2])
    expect(frames[3]).not.toBe(frames[2])
    expect(frames[3]).toBe(frames[5])
    expect(frames[6]).not.toBe(frames[5])
  })
})

describe("typingSpeed", () => {
  it("is the typing speed while it is on and the browser has no reduced-motion preference", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: false }))
    expect(typingSpeed(true)).toBe(CHARS_PER_SECOND)
    expect(typingSpeed(false)).toBe(0)
  })

  it("is 0 for a browser that asks for reduced motion, whatever the setting says", () => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("reduce") }))
    expect(typingSpeed(true)).toBe(0)
  })

  it("works where the browser cannot answer the question", () => {
    vi.stubGlobal("matchMedia", undefined)
    expect(typingSpeed(true)).toBe(CHARS_PER_SECOND)
  })
})
