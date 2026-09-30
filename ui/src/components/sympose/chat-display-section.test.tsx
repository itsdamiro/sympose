// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { ChatDisplaySection } from "./chat-display-section"

beforeEach(() => {
  document.cookie = "sympose:pref.section.chat=1"
})
afterEach(() => {
  cleanup()
  document.cookie = "sympose:pref.section.chat=; max-age=0"
})

describe("ChatDisplaySection", () => {
  it("shows the grounded-notes switch as it is and sets it from the other side", () => {
    const setPref = vi.fn()
    render(<ChatDisplaySection prefs={{ showGrounding: true, typeStatus: true }} setPref={setPref} />)
    const group = screen.getByRole("radiogroup", { name: "Notes a reply was based on" })
    expect(group.querySelector('[aria-checked="true"]')?.textContent).toBe("On")
    fireEvent.click(group.querySelector('[aria-checked="false"]') as HTMLElement)
    expect(setPref).toHaveBeenCalledWith("showGrounding", false)
  })

  it("shows the typing switch as it is and sets it from the other side, leaving the grounding one alone", () => {
    const setPref = vi.fn()
    render(<ChatDisplaySection prefs={{ showGrounding: true, typeStatus: false }} setPref={setPref} />)
    const group = screen.getByRole("radiogroup", { name: "Type the busy line out by letters" })
    expect(group.querySelector('[aria-checked="true"]')?.textContent).toBe("Off")
    fireEvent.click(group.querySelector('[aria-checked="false"]') as HTMLElement)
    expect(setPref).toHaveBeenCalledTimes(1)
    expect(setPref).toHaveBeenCalledWith("typeStatus", true)
  })
})
