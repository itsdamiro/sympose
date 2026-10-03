// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { RecentNotesFooter } from "./recent-notes-footer"
import type { VaultNode } from "./vault-tree"

beforeEach(() => {
  document.cookie = "sympose:footer.recent.open=; max-age=0; path=/"
})
afterEach(cleanup)

const note = (path: string): VaultNode => ({ type: "note", name: path.split("/").pop()!, path }) as VaultNode
const nodes = [note("a.md"), note("b.md")]

function setup(over: Partial<React.ComponentProps<typeof RecentNotesFooter>> = {}) {
  const onSelect = vi.fn()
  render(<RecentNotesFooter nodes={nodes} actions={{ persona: "samantha" }} hideExtension={false} onSelect={onSelect} {...over} />)
  return { onSelect }
}

describe("RecentNotesFooter", () => {
  it("lists the recent notes under a Recent caption, and opens one on a click", () => {
    const { onSelect } = setup()
    expect(document.querySelector('[data-slot="group-caption"]')?.textContent).toBe("Recent")
    fireEvent.click(screen.getByText("b.md"))
    expect(onSelect).toHaveBeenCalledWith(nodes[1])
  })

  it("can be folded away down to its caption, on any screen, and the choice is remembered", () => {
    setup()
    expect(screen.getByRole("button", { name: "Fold recent notes" }).getAttribute("aria-expanded")).toBe("true")
    fireEvent.click(screen.getByRole("button", { name: "Fold recent notes" }))
    expect(screen.queryByText("a.md")).toBeNull()
    expect(screen.getByText("Recent")).toBeTruthy() // the caption stays, with the way back
    cleanup()
    setup()
    expect(screen.queryByText("a.md")).toBeNull() // still folded: it was kept
    fireEvent.click(screen.getByRole("button", { name: "Show recent notes" }))
    expect(screen.getByText("a.md")).toBeTruthy()
  })
})
