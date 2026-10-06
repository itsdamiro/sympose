// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { ContextMeter } from "./context-meter"

afterEach(cleanup)

const figure = (used: number, estimated = false) => ({ used, limit: 1000, estimated })
const meter = () => screen.getByRole("meter")
const fillLength = () => Number((meter().querySelector('[data-part="fill"]') as SVGElement).getAttribute("stroke-dasharray")?.split(" ")[0])

describe("ContextMeter", () => {
  it("shows the percentage as a number beside the ring, and gives the meter its value for a screen reader", () => {
    render(<ContextMeter figure={figure(620)} />)
    expect(meter().textContent).toBe("62%")
    expect(meter().getAttribute("aria-valuenow")).toBe("62")
    expect(meter().getAttribute("aria-valuemin")).toBe("0")
    expect(meter().getAttribute("aria-valuemax")).toBe("100")
    expect(meter().getAttribute("aria-valuetext")).toBe("62% of the context used")
  })

  it("fills the ring in proportion to the percentage", () => {
    const { rerender } = render(<ContextMeter figure={figure(0)} />)
    expect(fillLength()).toBe(0)
    rerender(<ContextMeter figure={figure(500)} />)
    const half = fillLength()
    rerender(<ContextMeter figure={figure(1000)} />)
    const full = fillLength()
    expect(half).toBeGreaterThan(0)
    expect(full).toBeCloseTo(half * 2, 5)
  })

  it("draws a full ring, exactly once round, at 100%", () => {
    render(<ContextMeter figure={figure(1000)} />)
    const r = Number((meter().querySelector('[data-part="fill"]') as SVGElement).getAttribute("r"))
    expect(fillLength()).toBeCloseTo(2 * Math.PI * r, 5)
  })

  it("is normal below 70%, a warning from 70% and an error from 90%", () => {
    const levels = [690, 700, 894, 900].map((used) => {
      const { unmount } = render(<ContextMeter figure={figure(used)} />)
      const level = meter().getAttribute("data-level")
      unmount()
      return level
    })
    expect(levels).toEqual(["ok", "warn", "warn", "error"])
  })

  it("marks an estimate with a ~ and a dashed track, and a real figure with neither", () => {
    const { rerender } = render(<ContextMeter figure={figure(620, true)} />)
    expect(meter().textContent).toBe("~62%")
    expect(meter().getAttribute("data-estimated")).toBe("true")
    expect(meter().querySelector('[data-part="track"]')?.getAttribute("stroke-dasharray")).toBe("2 2")
    rerender(<ContextMeter figure={figure(620)} />)
    expect(meter().textContent).toBe("62%")
    expect(meter().getAttribute("data-estimated")).toBeNull()
    expect(meter().querySelector('[data-part="track"]')?.getAttribute("stroke-dasharray")).toBeNull()
  })

  it("shows nothing without a figure", () => {
    const { container } = render(<ContextMeter figure={null} />)
    expect(container.textContent).toBe("")
    expect(screen.queryByRole("meter")).toBeNull()
  })

  it("is reachable with the keyboard, and shows the figures in full when focused", async () => {
    render(<ContextMeter figure={{ used: 3812, limit: 6144, estimated: false }} />)
    expect(meter().tabIndex).toBe(0)
    fireEvent.focus(meter())
    expect(await screen.findByText("3,812 of 6,144 tokens")).toBeTruthy()
    expect(screen.getByText(/100% is where the oldest messages start to be left out/)).toBeTruthy()
  })

  it("says in the tooltip when the figure is an estimate", async () => {
    render(<ContextMeter figure={{ used: 3812, limit: 6144, estimated: true }} />)
    fireEvent.focus(meter())
    expect(await screen.findByText("3,812 of 6,144 tokens (estimated)")).toBeTruthy()
  })
})
