// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react"
import { afterEach, describe, expect, it } from "vitest"

import { SlackDot } from "./slack-dot"

afterEach(cleanup)

describe("SlackDot", () => {
  it("is a green dot and the word, the size and look of the Files chip", () => {
    const { container } = render(<SlackDot />)
    const chip = container.querySelector("[data-slot=slack-dot]") as HTMLElement
    expect(chip.textContent).toBe("Slack")
    for (const token of ["h-5", "bg-chip", "uppercase", "tracking-wide"]) expect(chip.className).toContain(token)
    expect(chip.querySelector(".bg-ok")).not.toBeNull()
  })

  it("is not something to press", () => {
    render(<SlackDot />)
    expect(screen.queryByRole("button")).toBeNull()
  })
})
