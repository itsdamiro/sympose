// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { TogglePill } from "./toggle-pill"

afterEach(cleanup)

describe("TogglePill", () => {
  it("says whether it is on, and is outlined in the brand colour only then", () => {
    render(
      <>
        <TogglePill pressed>on one</TogglePill>
        <TogglePill pressed={false}>off one</TogglePill>
      </>
    )
    const on = screen.getByRole("button", { name: "on one" })
    const off = screen.getByRole("button", { name: "off one" })
    expect(on.getAttribute("aria-pressed")).toBe("true")
    expect(off.getAttribute("aria-pressed")).toBe("false")
    expect(on.className).toContain("border-brand")
    expect(off.className).not.toContain("border-brand")
  })

  it("passes its click and its title on", () => {
    const onClick = vi.fn()
    render(
      <TogglePill pressed={false} title="what it is" onClick={onClick}>
        x
      </TogglePill>
    )
    fireEvent.click(screen.getByRole("button", { name: "x" }))
    expect(onClick).toHaveBeenCalledTimes(1)
    expect(screen.getByTitle("what it is")).toBeTruthy()
  })
})
