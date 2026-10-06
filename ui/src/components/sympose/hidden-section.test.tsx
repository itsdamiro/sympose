// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { HiddenSection } from "./hidden-section"

beforeEach(() => {
  // The section starts closed and remembers that in a cookie; open it for each test.
  document.cookie = "sympose:pref.section.hidden-from-view=1"
})
afterEach(() => {
  cleanup()
  document.cookie = "sympose:pref.section.hidden-from-view=; max-age=0"
})

function setup(overrides: Partial<Parameters<typeof HiddenSection>[0]> = {}) {
  const onUnhide = vi.fn()
  const onShowDefinitionNotes = vi.fn()
  render(
    <HiddenSection
      hidden={["Drafts", "Journal/Secret.md"]}
      showDefinitionNotes={false}
      onUnhide={onUnhide}
      onShowDefinitionNotes={onShowDefinitionNotes}
      {...overrides}
    />
  )
  return { onUnhide, onShowDefinitionNotes }
}

describe("HiddenSection", () => {
  it("says that hiding is for the view only and the persona can still read it", () => {
    setup()
    expect(
      screen.getByText(/Hidden from view only; the persona can still read them/)
    ).toBeTruthy()
  })

  it("lists every hidden path with its own Unhide button", () => {
    const { onUnhide } = setup()
    expect(screen.getByText("Drafts")).toBeTruthy()
    expect(screen.getByText("Journal/Secret.md")).toBeTruthy()
    fireEvent.click(screen.getByRole("button", { name: "Unhide Journal/Secret.md" }))
    expect(onUnhide).toHaveBeenCalledExactlyOnceWith("Journal/Secret.md")
  })

  it("says nothing is hidden, and how to hide something, when the list is empty", () => {
    setup({ hidden: [] })
    expect(screen.getByText(/Nothing is hidden/)).toBeTruthy()
    expect(document.querySelector('[data-slot="empty"]')).not.toBeNull() // the app's empty placeholder
    expect(screen.queryByRole("button", { name: /^Unhide/ })).toBeNull()
  })

  it("shows the definition-notes switch as it stands and reports a change", () => {
    const { onShowDefinitionNotes } = setup({ showDefinitionNotes: false })
    const group = screen.getByRole("radiogroup", { name: "Show folder description notes" })
    expect(group.querySelector('[aria-checked="true"]')?.textContent).toBe("Hidden")
    fireEvent.click(screen.getByRole("radio", { name: "Shown" }))
    expect(onShowDefinitionNotes).toHaveBeenCalledExactlyOnceWith(true)
  })
})
