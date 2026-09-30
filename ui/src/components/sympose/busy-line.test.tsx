// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { BusyLine } from "./busy-line"

const PHRASES = ["Alpha one…", "Beta two…"]
const shown = () => (document.querySelector('[data-slot="busy-line"] [aria-hidden]') as HTMLElement).textContent ?? ""
const advance = (ms: number) => act(() => void vi.advanceTimersByTime(ms))

beforeEach(() => {
  vi.useFakeTimers()
  vi.stubGlobal("matchMedia", () => ({ matches: false }))
})
afterEach(() => {
  cleanup()
  vi.useRealTimers()
  vi.unstubAllGlobals()
})

describe("BusyLine", () => {
  it("types the phase's text out one letter at a time", () => {
    render(<BusyLine phase="searching" phrases={PHRASES} typing />)
    expect(shown().slice(2)).toBe("S")
    advance(200)
    const partial = shown().slice(2)
    expect("Searching your notes…".startsWith(partial) && partial.length > 3 && partial.length < 20).toBe(true)
    advance(2000)
    expect(shown().slice(2)).toBe("Searching your notes…")
  })

  it("rotates to one of the persona's phrases after three seconds, and back to the literal text after six", () => {
    render(<BusyLine phase="reading" phrases={PHRASES} typing={false} />)
    advance(2900)
    expect(shown().slice(2)).toBe("Reading a note…")
    advance(200)
    expect(PHRASES).toContain(shown().slice(2))
    advance(3000)
    expect(shown().slice(2)).toBe("Reading a note…")
  })

  it("shows each phrase whole when typing is off", () => {
    render(<BusyLine phase="asking" phrases={PHRASES} typing={false} />)
    expect(shown().slice(2)).toBe("Thinking about your message…")
  })

  it("shows each phrase whole for a browser that asks for reduced motion, whatever the setting says", () => {
    vi.stubGlobal("matchMedia", () => ({ matches: true }))
    render(<BusyLine phase="asking" phrases={PHRASES} typing />)
    expect(shown().slice(2)).toBe("Thinking about your message…")
  })

  it("uses the phrases it is given now, so ones that arrive mid-wait are used", () => {
    const { rerender } = render(<BusyLine phase="asking" phrases={["Generic…"]} typing={false} />)
    rerender(<BusyLine phase="asking" phrases={["Own phrase…"]} typing={false} />)
    advance(3100)
    expect(shown().slice(2)).toBe("Own phrase…")
  })

  it("follows a change of phase and starts its rotation again", () => {
    const { rerender } = render(<BusyLine phase="searching" phrases={PHRASES} typing={false} />)
    advance(3100)
    expect(PHRASES).toContain(shown().slice(2))
    rerender(<BusyLine phase="reading" phrases={PHRASES} typing={false} />)
    advance(100)
    expect(shown().slice(2)).toBe("Reading a note…")
  })

  it("tells a screen reader the phase's own text once, not every letter as it is typed", () => {
    render(<BusyLine phase="searching" phrases={PHRASES} typing />)
    expect(screen.getByRole("status").querySelector(".sr-only")?.textContent).toBe("Searching your notes…")
    expect(screen.getByRole("status").querySelector("[aria-hidden]")).not.toBeNull()
  })

  it("stops its timer when it goes away", () => {
    const { unmount } = render(<BusyLine phase="asking" phrases={PHRASES} typing />)
    unmount()
    expect(vi.getTimerCount()).toBe(0)
  })
})
