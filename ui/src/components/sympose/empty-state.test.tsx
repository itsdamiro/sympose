// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react"
import { Folder01Icon } from "@hugeicons/core-free-icons"
import { afterEach, describe, expect, it, vi } from "vitest"

import { EmptyAction, EmptyState } from "./empty-state"

afterEach(cleanup)

describe("EmptyState", () => {
  it("is an icon tile, a title and a line under it, with no border of its own", () => {
    const { container } = render(<EmptyState icon={Folder01Icon} title="This folder is empty" description="Add a note." />)
    expect(screen.getByText("This folder is empty")).toBeTruthy()
    expect(screen.getByText("Add a note.")).toBeTruthy()
    expect(container.querySelector('[data-slot="empty-icon"] svg')).not.toBeNull()
    expect(container.querySelector('[data-slot="empty"]')?.className).toContain("border-0")
  })

  it("draws the line and the action only when given", () => {
    const { container } = render(<EmptyState icon={Folder01Icon} title="Nothing" />)
    expect(container.querySelector('[data-slot="empty-description"]')).toBeNull()
    expect(screen.queryByRole("button")).toBeNull()
  })

  it("colours the tile for a persona's own accent, and offers an action", () => {
    const onClick = vi.fn()
    const { container } = render(
      <EmptyState icon={Folder01Icon} title="Ask Ada anything" accent="rgb(1, 2, 3)" action={<EmptyAction onClick={onClick}>Try again</EmptyAction>} />
    )
    expect((container.querySelector('[data-slot="empty-icon"]') as HTMLElement).style.background).toContain("rgb(1, 2, 3)")
    fireEvent.click(screen.getByRole("button", { name: "Try again" }))
    expect(onClick).toHaveBeenCalled()
  })

  it("takes less room when compact, for a list inside another panel", () => {
    const { container } = render(<EmptyState compact icon={Folder01Icon} title="x" />)
    expect(container.querySelector('[data-slot="empty"]')?.className).toContain("p-4")
  })
})
