// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { CloudSent } from "./cloud-sent"

afterEach(cleanup)

describe("CloudSent", () => {
  it("says what was sent and what was held back", () => {
    render(<CloudSent sent={{ notes: [], cloud: ["notes", "recaps"], withheld: ["properties"] }} />)
    expect(screen.getByText("Sent: notes, recaps · Held back: properties")).toBeTruthy()
  })

  it("says only the part that has something in it", () => {
    render(<CloudSent sent={{ notes: [], cloud: [], withheld: ["notes"] }} />)
    expect(screen.getByText("Held back: notes")).toBeTruthy()
  })

  it("shows nothing for a local reply or one that involved nothing of the vault", () => {
    const { container, rerender } = render(<CloudSent sent={{ notes: [] }} />)
    expect(container.textContent).toBe("")
    rerender(<CloudSent sent={{ notes: [], cloud: [], withheld: [] }} />)
    expect(container.textContent).toBe("")
    rerender(<CloudSent sent={null} />)
    expect(container.textContent).toBe("")
  })
})
